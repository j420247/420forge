#!/bin/bash

# End to end test that is launching AMI instance in AWS and verifying that Bitbucket is running in right version.
# You can override most of the parameters by specifying environment variables (see variable definition below).
# Test steps:
# 1. Create EC2 instance in AWS based on provided AMI (use AMI from BitbucketServer.template as default)
# 2. Verify that EC2 instance is running
# 3. Verify that while setting up requirements we are displaying static ngnix page
# 4. Verify that Bitbucket requirements are running
# 5. Verify that we can land on Bitbucket setup running correct version
# 6. Download log files from the instance
# 7. Teardown created instance (instance & volumes)
#
# How to run test locally:
# 1. Set ENV variables - see below
#    - the only required is ATL_BITBUCKET_VERSION (each major version since 3.8.0 is available in S3)
# 2. Run ./ami-smoke-test.sh

# AWS properties
AWS_AMI_ID=${AWS_AMI_ID}
AWS_INSTANCE_TYPE=${AWS_INSTANCE_TYPE:-"m4.xlarge"}
AWS_SECURITY_GROUP_NAME=${AWS_SECURITY_GROUP_NAME:-"aws-bitbucket-ami-smoke-test"}
AWS_REGION=${AWS_REGION:-"us-east-1"}

# Product properties
ATL_STASH_VERSION=${ATL_STASH_VERSION:-"latest"}
ATL_BITBUCKET_VERSION=${ATL_BITBUCKET_VERSION:-$ATL_STASH_VERSION}

# We are waiting 5 seconds in the loops - 5*60 retries = 5 minutes
WAIT_SECONDS=${WAIT_SECONDS:-"5"}
RETRIES=${RETRIES:-"60"}

# In case we are running from Bamboo deployment project we need to include log files directly in output
PRINT_LOGS=${PRINT_LOGS:-true}

TEMPLATE_LOCATION="../templates/BitbucketServer.template.yaml"
AWS_KEY_PAIR="build-temp-"`date +%s`

# Helper method - Tearing down the instance - pass instanceID
function teardown {
  TEARDOWN_EXIT_CODE=$?
  trap - EXIT
  if [ ${PUBLIC_DNS} ]; then
    echo "Downloading log files from the instance"
    mkdir -p ../artifacts
    rm ../artifacts/*.log 2> /dev/null
    TARGET_LOG_FILES="/var/log/atl.log /var/atlassian/application-data/bitbucket/log/atlassian-bitbucket.log"
    chmod 0400 ${AWS_KEY_PAIR}.pem
    scp -i ${AWS_KEY_PAIR}.pem -oStrictHostKeyChecking=no ec2-user@${PUBLIC_DNS}:"${TARGET_LOG_FILES}" ../artifacts/ &> /dev/null
    if [ ${PRINT_LOGS} = true ]; then
      echo ; echo "******************** Printing ouput of atl.log ********************"; echo
      cat ../artifacts/atl.log 2>&1
      echo ; echo "************* Printing ouput of atlassian-bitbucket.log ***************"; echo
      cat ../artifacts/atlassian-bitbucket.log 2>&1
      echo ; echo "************************** End of logs ****************************"; echo
    fi
  fi

  # Delete EC2 key pair
  aws ec2 delete-key-pair --region ${AWS_REGION} --key-name ${AWS_KEY_PAIR}
  rm -f ${AWS_KEY_PAIR}.pem

  if [ ${TEARDOWN_EXIT_CODE} -ne 0 ]; then
    log ">>>> TEST FAILURE <<<<"
    log ">>>> ${RESULT}" 1>&2
  else
    log ">>>> TEST SUCCESS <<<<"
    log ">>>> ${RESULT}"
  fi

  log "Tearing down the instance with ID [ ${INSTANCE_ID} ]"
  aws ec2 terminate-instances --region ${AWS_REGION} --instance-ids ${INSTANCE_ID} > /dev/null

  log "Delete attached EBS volumes [ ${EBS_VOLUME_1}, ${EBS_VOLUME_2} ]"
  RETRY_COUNTER_AMI_DOWN=0
  until (aws ec2 describe-instances --region ${AWS_REGION} --instance-ids ${INSTANCE_ID} --output text --query 'Reservations[0].Instances[0].State.Name' | grep 'terminated') || [ ${RETRY_COUNTER_AMI_DOWN} -eq ${RETRIES} ]; do
    echo -n .
    sleep ${WAIT_SECONDS}
    ((RETRY_COUNTER_AMI_DOWN++))
  done

  if [ ${RETRY_COUNTER_AMI_DOWN} -eq ${RETRIES} ]; then
    log "ERROR: timeout while tearing down the instance. You need to delete EBS volumes manually." 1>&2
    log ">>>> Please log into AWS console and delete these volumes:" 1>&2
    log ">>>> Region: [ ${AWS_REGION} ]; Volumes: [ ${EBS_VOLUME_1}, ${EBS_VOLUME_2} ]" 1>&2
    exit 1
  fi

  aws ec2 delete-volume --region ${AWS_REGION} --volume-id ${EBS_VOLUME_1}
  aws ec2 delete-volume --region ${AWS_REGION} --volume-id ${EBS_VOLUME_2}

  log "Deleting security group [ ${SECURITY_GROUP_ID} ]"
  aws ec2 delete-security-group --region ${AWS_REGION} --group-id ${SECURITY_GROUP_ID}
  log "Instance is terminated and volumes are deleted"

  ENDTIME=$(date +%s)
  log ">>>> Total time of the test $((${ENDTIME} - ${STARTTIME})) seconds"
}

function log {
  echo "$(date +'%Y-%m-%d %T'): $*"
}

log "Start of the test"

# Check prerequisites
if [[ -z "${AWS_AMI_ID}" ]]; then
    if [ ! -f "${TEMPLATE_LOCATION}" ]; then
        log "ERROR: AMI ID was not specified and could not find template file: ${TEMPLATE_LOCATION}" 1>&2
        exit 1
    fi
    if ! AWS_AMI_ID="$(perl -0777 -ne "print \"\$1\" if /\b${AWS_REGION}:\s+HVM64:\s*(ami-\w+)/" < "${TEMPLATE_LOCATION}")" || [ -z "${AWS_AMI_ID}" ]; then
        log "ERROR: AMI ID was not specified and ${TEMPLATE_LOCATION} could not be parsed" 1>&2
        exit 1
    fi
    log "Using ${AWS_AMI_ID} from $(basename "${TEMPLATE_LOCATION}")"
fi

# VPC and subnet need to be defined
if [[ -z "${AWS_VPC}" || -z "${AWS_SUBNET}" ]]; then
    log "ERROR: AWS_VPC and/or AWS_SUBNET were not defined. These are required parameters." 1>&2
    exit 1
fi

AWS_BIN=`which aws`
if [ $? != 0 ]; then
  pip install aws
  which aws > /dev/null
  if [ $? != 0 ]; then
    log "ERROR: AWS CLI cannot be installed" 1>&2
  fi
fi

# If we are running in Bamboo we need to get the credentials via assume-role STS command
if [[ -n "${BAMBOO_AGENT_ACCOUNT}" && -n "${BAMBOO_ASSUMED_ROLE}" && -n "${BAMBOO_SESSION_NAME}" ]] ; then
    CREDENTIALS=$(aws sts assume-role \
            --role-arn "arn:aws:iam::${BAMBOO_AGENT_ACCOUNT}:role/${BAMBOO_ASSUMED_ROLE}" \
            --role-session-name "${BAMBOO_SESSION_NAME}"
        )

    if [ $? != 0 ]; then
      log "ERROR: Cannot get AWS credentials from STS for role: [ ${BAMBOO_ASSUMED_ROLE} ] in the [ ${BAMBOO_AGENT_ACCOUNT} ] account"
      log ${CREDENTIALS}
      exit 1
    fi
    export AWS_ACCESS_KEY_ID="$(echo ${CREDENTIALS} | jq -r .Credentials.AccessKeyId)"
    export AWS_SECRET_ACCESS_KEY="$(echo ${CREDENTIALS} | jq -r .Credentials.SecretAccessKey)"
    export AWS_SESSION_TOKEN="$(echo ${CREDENTIALS} | jq -r .Credentials.SessionToken)"
    export AWS_SECURITY_TOKEN=${AWS_SESSION_TOKEN}
fi

log Running AMI test
STARTTIME=$(date +%s)

USER_DATA="#!/bin/bash
echo \"ATL_BITBUCKET_VERSION=${ATL_BITBUCKET_VERSION}\" > /etc/atl"

USER_DATA_ENCODED=`echo -n "${USER_DATA}" | base64 | tr -d '\n'`

# Create security group
SECURITY_GROUP_RESPONSE=`aws ec2 create-security-group --region ${AWS_REGION} --vpc-id ${AWS_VPC} --group-name ${AWS_SECURITY_GROUP_NAME} --description "Temporary security group for Bitbucket test"`

if [ $? != 0 ]; then
  log "ERROR: Security group [ ${AWS_SECURITY_GROUP_NAME} ] creation failed"
  log ${SECURITY_GROUP_RESPONSE}
  exit 1
fi

SECURITY_GROUP_ID=`echo "${SECURITY_GROUP_RESPONSE}" | jq -r .GroupId`


log "Created security group [ ${AWS_SECURITY_GROUP_NAME} ] with ID [ ${SECURITY_GROUP_ID} ]"

aws ec2 authorize-security-group-ingress --region ${AWS_REGION} --group-id ${SECURITY_GROUP_ID} --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region ${AWS_REGION} --group-id ${SECURITY_GROUP_ID} --protocol tcp --port 80 --cidr 0.0.0.0/0
log "For security group [ ${AWS_SECURITY_GROUP_NAME} ] allow ports [ 22, 80 ]."

# Create EC2 key pair
KEY_PAIR_RESPONSE=`aws ec2 create-key-pair --region ${AWS_REGION} --key-name ${AWS_KEY_PAIR}`
echo ${KEY_PAIR_RESPONSE} | jq -r ".KeyMaterial" > ${AWS_KEY_PAIR}.pem
log Created key pair: ${AWS_KEY_PAIR}

AWS_COMMAND="aws ec2 run-instances --region ${AWS_REGION} --image-id ${AWS_AMI_ID} --count 1 --instance-type ${AWS_INSTANCE_TYPE} --key-name ${AWS_KEY_PAIR} --security-group-ids ${SECURITY_GROUP_ID} --subnet-id ${AWS_SUBNET} --user-data ${USER_DATA_ENCODED} --associate-public-ip-address"

log "Running command [ ${AWS_COMMAND} ]"

STARTING_INSTANCE=`${AWS_COMMAND}`

if [ $? != 0 ]; then
    log "ERROR: AMI instance didn't start" 1>&2
    exit 1
fi

# Verify that instance spun up
INSTANCE_ID=$(echo "${STARTING_INSTANCE}" | jq -r ".Instances[0].InstanceId")
AMI_STARTED=$(echo "${STARTING_INSTANCE}" | jq -r ".Instances[0].ImageId")

# Kill the instance in case something goes wrong
trap "teardown" EXIT

if [ "${AMI_STARTED}" != "${AWS_AMI_ID}" ]; then
    RESULT="ERROR: Expected different AMI (got ${AMI_STARTED} instead of ${AWS_AMI_ID}), the machine didn't started correctly"
    exit 1
fi

# Tag the instance with name
INSTANCE_NAME="Atlassian Bitbucket (AMI: ${AWS_AMI_ID}; Bitbucket: ${ATL_BITBUCKET_VERSION}) - Automated Test"
aws ec2 create-tags --region ${AWS_REGION} --resources ${INSTANCE_ID} ${SECURITY_GROUP_ID} --tags "Key=Name,Value=\"${INSTANCE_NAME}\"" 'Key=business_unit,Value="RD:Dev Tools Engineering"' Key=resource_owner,Value=abrokes Key=service_name,Value=devtools-bamboo.internal.atlassian.com

log "Starting AMI instance with name: [ ${INSTANCE_NAME} ] and ID [ ${INSTANCE_ID} ]"

# Verify that instance is running (done initialization)

RETRY_COUNTER_AMI_UP=0
until (aws ec2 describe-instances --region ${AWS_REGION} --instance-ids ${INSTANCE_ID} --output text --query 'Reservations[0].Instances[0].State.Name' | grep 'running') || [ ${RETRY_COUNTER_AMI_UP} -eq ${RETRIES} ]; do
  echo -n .
  sleep ${WAIT_SECONDS}
  ((RETRY_COUNTER_AMI_UP++))
done

# Tag EBS volumes attached to the instance
DESCRIBE_INSTANCE=`aws ec2 describe-instances --instance-ids ${INSTANCE_ID} --region ${AWS_REGION}`
EBS_VOLUME_1=$(echo "${DESCRIBE_INSTANCE}" | jq -r ".Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId")
EBS_VOLUME_2=$(echo "${DESCRIBE_INSTANCE}" | jq -r ".Reservations[0].Instances[0].BlockDeviceMappings[1].Ebs.VolumeId")
aws ec2 create-tags --region ${AWS_REGION} --resources ${EBS_VOLUME_1} ${EBS_VOLUME_2} --tags "Key=Name,Value=\"${INSTANCE_NAME}\"" 'Key=business_unit,Value="RD:Dev Tools Engineering"' Key=resource_owner,Value=abrokes Key=service_name,Value=devtools-bamboo.internal.atlassian.com

if [ ${RETRY_COUNTER_AMI_UP} -eq ${RETRIES} ]; then
    RESULT="ERROR: Timeout while starting up instance"
    exit 1
fi

PUBLIC_DNS=$(aws ec2 describe-instances --region ${AWS_REGION} --instance-ids ${INSTANCE_ID} --output text --query 'Reservations[0].Instances[0].PublicDnsName')
log "Instance is up and running on: [ ${PUBLIC_DNS} ]"
log "Executing verification"

# Test if curl contains <title>Setup - Bitbucket</title>
# In future the setup should be done via properties passed via Automated Application Setup
SETUP_URL=http://${PUBLIC_DNS}/

log "Setting up all dependencies"
RETRY_COUNTER_CONN_REFUSED=0
while (curl -v ${SETUP_URL} 2>&1 | grep -q "Connection refused") && [ ${RETRY_COUNTER_CONN_REFUSED} -lt ${RETRIES} ]; do
  echo -n .
  sleep ${WAIT_SECONDS}
  ((RETRY_COUNTER_CONN_REFUSED++))
done

echo
if [ ${RETRY_COUNTER_CONN_REFUSED} -eq ${RETRIES} ]; then
    RESULT="ERROR: Timeout while starting up dependencies"
    exit 1
fi

log "Requirements are launched"

log "Starting up Bitbucket setup"
RETRY_COUNTER_SETUP_STARTING=0
while (curl -L -v ${SETUP_URL} 2>&1 | grep -q "/unavailable") && [ ${RETRY_COUNTER_SETUP_STARTING} -lt ${RETRIES} ]; do
  echo -n .
  sleep ${WAIT_SECONDS}
  ((RETRY_COUNTER_SETUP_STARTING++))
done

log "Displayed ngnix warming up page"
RETRY_COUNTER_SETUP_NGNX=0
while (curl -L ${SETUP_URL} 2>&1 | grep -q "Your Atlassian instance is starting") && [ ${RETRY_COUNTER_SETUP_NGNX} -lt ${RETRIES} ]; do
  echo -n .
  sleep ${WAIT_SECONDS}
  ((RETRY_COUNTER_SETUP_NGNX++))
done

echo
log "Connecting to Bitbucket setup and verifying we can land on it"
RETRY_COUNTER_SETUP_BITBUCKET=0
until (curl -L -q ${SETUP_URL} 2>&1 | grep -q "<title>Setup - Bitbucket</title>" &> /dev/null) || [ ${RETRY_COUNTER_SETUP_BITBUCKET} -eq ${RETRIES} ]; do
  echo -n .
  sleep ${WAIT_SECONDS}
  ((RETRY_COUNTER_SETUP_BITBUCKET++))
done

if [ ${RETRY_COUNTER_SETUP_BITBUCKET} -eq ${RETRIES} ]; then
  RESULT="ERROR: Bitbucket Setup was not displayed"
  exit 1
fi

if [ "${ATL_BITBUCKET_VERSION}" != "latest" ] && ! (curl -L -q ${SETUP_URL} 2>&1 | grep -q "${ATL_BITBUCKET_VERSION}" &> /dev/null); then
    RESULT='ERROR: Bitbucket started, but not in the right version'
    exit 1
fi

RESULT="Instance is running and Bitbucket version [ ${ATL_BITBUCKET_VERSION} ] is launched correctly"

# Tear it down
teardown

exit 0