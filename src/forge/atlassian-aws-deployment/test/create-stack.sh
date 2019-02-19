#!/bin/bash
set -e

BASEDIR=$(dirname $0)
source $BASEDIR/atl-aws-extensions.sh

TEMPLATE_NAME=${1:?"A template name must be specified."}
PARAMETERS="$2"
DATA_CENTER=${3:-"true"}

STACK_NAME="$(atl_getStackName ${TEMPLATE_NAME})"

if [[ -z ${AWS_REGION} ]] 
then
  echo "Env variable AWS_REGION not set. Set it to your preferred AWS region!"
  exit 1
fi

echo "Starting '${TEMPLATE_NAME}' in region '${AWS_REGION}'..."

trap atl_runCleanup EXIT

KEY_PAIR=$(atl_getKeyName)
if [[ -z ${KEY_PAIR} ]]; then
  echo "No key pair found. Create one now for region '${AWS_REGION}'?"
  KEY_PAIR=$(atl_createKeyPair)
  if [[ -z ${KEY_PAIR} ]]; then
    echo "Env variable PEMFILE not set. Set it to your Key Pair name for region '${AWS_REGION}'"  
    atl_propUsage "key"
    exit 1
  fi
  atl_addProp "key" "${KEY_PAIR}"
  echo ''
  echo "Key pair '${KEY_PAIR}' created."
  echo ''
  echo "NOTE: you must set the permission on the key file:"
  echo "    chmod 400 ${HOME}/.aws/${KEY_PAIR}.pem"
fi

VPC_ID=${vpc:-$(atl_getVpcId)}
if [[ -z ${VPC_ID} ]]; then
  echo "No VPC ID found. Create one now for region '${AWS_REGION}'?"
  VPC_ID=$(atl_createVPC)
  if [[ -z ${VPC_ID} ]]; then
    echo "Env variable vpc not set. Set it to your VPC ID for region '${AWS_REGION}'"
    atl_propUsage "vpc"
    exit 1
  fi
  atl_addProp "vpc" "${VPC_ID}"
fi

atl_ensureInternetGatewayAttached "${VPC_ID}"

if [[ -z $(atl_getAvailabilityZones) ]]; then
    echo "Query and update Availability 1Zones"
    atl_queryAvailabilityZones
fi

SUBNETS=${subnet:-$(atl_getSubnets)}
if [[ -z ${SUBNETS} ]]; then
  echo "No subnet(s) found. Create subnets now for region '${AWS_REGION}'?"
  SUBNETS=$(atl_createSubnets "${VPC_ID}")
  if [[ -z ${SUBNETS} ]]; then
    echo "Env variable subnet not set. Set it to your Subnets for region '${AWS_REGION}'"
    atl_propUsage "subnet"
    exit 1
  fi
  atl_addProp "subnet" "${SUBNETS}"
fi
SUBNET="${SUBNETS%*\\,*}"

${BASEDIR}/validate-template.sh "${TEMPLATE_NAME}"

PARAMETERS_ARR=($(atl_param "KeyName" "${KEY_PAIR}") $(atl_param "VPC" "${VPC_ID}"))
if [[ "x${DATA_CENTER}" = "xtrue" ]]; then
  PARAMETERS_ARR+=($(atl_param "ExternalSubnets" "${SUBNETS}"))
  PARAMETERS_ARR+=($(atl_param "InternalSubnets" "${SUBNETS}"))
else
  PARAMETERS_ARR+=($(atl_param "Subnet" "${SUBNET}"))
fi
IFS=$'~' PARAMETERS_ARR+=(${PARAMETERS})

echo "Passing parameters ${PARAMETERS_ARR[@]}"

aws --region "${AWS_REGION}" cloudformation create-stack \
    --stack-name "${STACK_NAME}" \
    --template-body "file://templates/${TEMPLATE_NAME}" \
    --parameters ${PARAMETERS_ARR[@]} \
    --tags Key=Name,Value="${STACK_NAME}" \
     Key=business_unit,Value="RD:Dev Tools Engineering" \
     Key=resource_owner,Value="$(whoami)" \
     Key=service_name,Value="${TEMPLATE_NAME}" \
    --capabilities CAPABILITY_IAM

unset IFS  

atl_waitForStack "${STACK_NAME}"

echo ''
echo "===Stack Details==="
echo ''

BASE_URL=$(atl_getBaseUrl "${STACK_NAME}")
echo "Stack URL:    ${BASE_URL}"

CLUSTER_GROUP=$(aws --region "${AWS_REGION}" cloudformation list-stack-resources \
--stack-name ${STACK_NAME} | jq -r '.StackResourceSummaries[] | select (.LogicalResourceId=="ClusterNodeGroup") | .PhysicalResourceId')
if [[ -n ${CLUSTER_GROUP} ]]; then 
  echo "Cluster Node Group:    ${CLUSTER_GROUP}"
  
  CLUSTER_NODES=$(aws --region "${AWS_REGION}" autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names ${CLUSTER_GROUP} | jq -M -c '.AutoScalingGroups[0].Instances | map(.InstanceId)' | tr '[,"]' '    ')
  echo "Cluster Nodes:    ${CLUSTER_NODES}"

  CLUSTER_IPS=$(aws --region "${AWS_REGION}" ec2 describe-instances \
  --instance-ids ${CLUSTER_NODES} | jq -c -M '.Reservations | map (.Instances) | map (map (.PublicIpAddress))' | tr '[,"]' '    ')
  echo "Cluster Node IPs:    ${CLUSTER_IPS}"
fi

DB=$(aws --region "${AWS_REGION}" cloudformation list-stack-resources \
--stack-name ${STACK_NAME} | jq -r '.StackResourceSummaries[] | select (.LogicalResourceId=="DB") | .PhysicalResourceId')
if [[ -n ${DB} ]]; then
  echo "Database:    ${DB}"

  DB_ADDRESS=$(aws --region "${AWS_REGION}" rds describe-db-instances \
  --db-instance-identifier ${DB} --query 'DBInstances[0].Endpoint.Address')
  echo "Database Endpoint:    ${DB_ADDRESS}"
fi

echo ''
echo "Waiting for application to become available..."

WGET_OUT=$(wget --no-check-certificate --retry-connrefused -T 60 --tries=60 --waitretry=20 -q --output-document=- "${BASE_URL}")
if [ $? -eq 0 ]; then
  echo ''
  echo "'${STACK_NAME}' is now available at ${BASE_URL}"
else
  echo ''
  echo "'${STACK_NAME}' failed to become available. Check the EC2 instance(s) logs for details."
  echo "Output:"
  echo ''
  echo "${WGET_OUT}"
fi

