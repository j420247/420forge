#!/bin/bash
set -e

TMP_DIR=$(mktemp -d -t packer)
trap "rm -rf ${TMP_DIR}" EXIT

BASEDIR=$(dirname $0)
source ${BASEDIR}/atl-aws-functions.sh

function usage {
# -b specifies business unit, and -o specifies resource owner. These are silently available options used to tag AWS resources
cat << EOF
usage: $0 options

This script spins up a new EC2 AMI instance.

OPTIONS:
   -r The AWS region to use. If not supplied, the AWS_REGION environment variable must be set
   -a The AWS AMI to use. If not supplied, the AWS_AMI environment variable must be set
   -k The AWS SSH key name to use. If not supplied, the AWS_SSH_KEY environment variable must be set
   -p The product that corresponds to the AMI ID. If not supplied, 'Bitbucket' is assumed
   -s The AWS security group to use. If not supplied, the AWS_SECURITY_GROUP environment variable must be set
   -i The AWS instance type to use. If not supplied, the AWS_INSTANCE_TYPE environment variable must be set or else \"m4.large\" is assumed
   -l The location of the installer that should be downloaded when the AWS instance boots
   -d Enable debug logging in product (if it is supported) and install tools to enable debugging on the box
   -u Append the following entries to /etc/sysconfig/atl  
EOF
}

AWS_REGION=${AWS_REGION}
AWS_AMI=${AWS_AMI}
AWS_SSH_KEY=${AWS_SSH_KEY}
AWS_SECURITY_GROUP=${AWS_SECURITY_GROUP}
AWS_INSTANCE_TYPE=${AWS_INSTANCE_TYPE:-"m4.large"}
AWS_SUBNET_ID=${AWS_SUBNET_ID:-subnet-a005d2d7}
DEBUG=
INSTALLER_DOWNLOAD_URL=
ATL_ENTRIES=
ATL_PRODUCT="Bitbucket"

while getopts ":hr:a:k:s:i:l:du:p:b:o:" OPTION
do
     case $OPTION in
         h)
             usage
             exit 1
             ;;
         r)
             AWS_REGION="${OPTARG}"
             ;;
         a)
             AWS_AMI="${OPTARG}"
             ;;
         k)
             AWS_SSH_KEY="${OPTARG}"
             ;;
         p)
             ATL_PRODUCT="${OPTARG}"
             ;;
         s)
             AWS_SECURITY_GROUP="${OPTARG}"
             ;;
         i)
             AWS_INSTANCE_TYPE="${OPTARG}"
             ;;
         l)
             INSTALLER_DOWNLOAD_URL="${OPTARG}"
             ;;
         d)
             DEBUG=true
             ;;
         u)
             ATL_ENTRIES="${OPTARG}"
             ;;
        b)
            BUSINESS_UNIT="${OPTARG}"
            ;;
        o)
            RESOURCE_OWNER="${OPTARG}"
            ;;
         \?)
             usage
             exit
             ;;
     esac
done

ATL_PRODUCT_ID=$(echo "${ATL_PRODUCT}" | tr '[:upper:]' '[:lower:]')
AWS_REGION=$(echo "${AWS_REGION}" | tr [:upper:] [:lower:])
AWS_AMI=$(echo "${AWS_AMI}" | tr [:upper:] [:lower:])
AWS_INSTANCE_TYPE=$(echo "${AWS_INSTANCE_TYPE}" | tr [:upper:] [:lower:])

if [[ -z "${AWS_REGION}" ]]; then
    echo "Error: AWS region option not supplied (-r) nor defined as an env var (AWS_REGION)"
    echo
    usage
    exit 1
fi

if [[ -z "${AWS_AMI}" ]]; then
    echo "Error: AWS AMI option not supplied (-a) nor defined as an env var (AWS_AMI)"
    echo
    usage
    exit 1
fi

if [[ -z "${AWS_SSH_KEY}" ]]; then
    echo "Error: AWS SSH key name option not supplied (-k) nor defined as an env var (AWS_SSH_KEY)"
    echo
    usage
    exit 1
fi

if [[ -z "${AWS_SECURITY_GROUP}" ]]; then
    echo "Error: AWS security group option not supplied (-s) nor defined as an env var (AWS_SECURITY_GROUP)"
    echo
    usage
    exit 1
fi

if [[ -z "${AWS_ACCESS_KEY}" ]]; then
    echo "Error: AWS_ACCESS_KEY env var not defined"
    echo
    usage
    exit 1
fi

if [[ -z "${AWS_SECRET_KEY}" ]]; then
    echo "Error: AWS_SECRET_KEY env var not defined"
    echo
    usage
    exit 1
fi

cat <<EOT > "${TMP_DIR}/user-init"
#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

set -e

EOT

echo "Setting ${ATL_PRODUCT} specific parameters"
if [[ "bitbucket" = "${ATL_PRODUCT_ID}" ]]; then
    echo "echo ATL_ENABLED_PRODUCTS=Bitbucket | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
    if [[ -n "${DEBUG}" ]]; then
        echo "echo ATL_BITBUCKET_PROPERTIES=\"logging.logger.com.atlassian.bitbucket=DEBUG\" | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        echo "Enabled debug logging"
    fi
    if [[ -n "${INSTALLER_DOWNLOAD_URL}" ]]; then
        echo "echo ATL_BITBUCKET_INSTALLER_DOWNLOAD_URL=${INSTALLER_DOWNLOAD_URL} | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        echo "Set installer download URL"        
    fi
    if [[ -n "${ATL_ENTRIES}" ]]; then
        for entry in "${ATL_ENTRIES}"; do
            echo "echo \"${entry}\" | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        done
        echo "Appended atl sysconfig entries"                
    fi
fi
if [[ "jira" = "${ATL_PRODUCT_ID}" ]]; then
    echo "echo ATL_ENABLED_PRODUCTS=Jira | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
fi
if [[ "confluence" = "${ATL_PRODUCT_ID}" ]]; then
    echo "echo ATL_ENABLED_PRODUCTS=Confluence | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
    if [[ -n "${INSTALLER_DOWNLOAD_URL}" ]]; then
        echo "echo ATL_CONFLUENCE_INSTALLER_DOWNLOAD_URL=${INSTALLER_DOWNLOAD_URL} | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        echo "Set installer download URL"
    fi
    if [[ -n "${ATL_ENTRIES}" ]]; then
        for entry in "${ATL_ENTRIES}"; do
            echo "echo \"${entry}\" | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        done
        echo "Appended atl sysconfig entries"
    fi
fi
if [[ "synchrony" = "${ATL_PRODUCT_ID}" ]]; then
    echo "echo ATL_ENABLED_PRODUCTS=Synchrony | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
    if [[ -n "${INSTALLER_DOWNLOAD_URL}" ]]; then
        echo "echo ATL_CONFLUENCE_INSTALLER_DOWNLOAD_URL=${INSTALLER_DOWNLOAD_URL} | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        echo "Set installer download URL"
    fi
    if [[ -n "${ATL_ENTRIES}" ]]; then
        for entry in "${ATL_ENTRIES}"; do
            echo "echo \"${entry}\" | su -c \"tee -a /etc/sysconfig/atl\"" >> "${TMP_DIR}/user-init"
        done
        echo "Appended atl sysconfig entries"
    fi
fi

echo "Done setting ${ATL_PRODUCT} specific parameters"

echo "Spinning up new instance of ${AWS_AMI}"
echo
echo "user-init:"
echo "======================================="
echo "$(cat ${TMP_DIR}/user-init)"
echo "======================================="
echo

AWS_INSTANCE_ID=$(aws ec2 run-instances --region "${AWS_REGION}" --image-id "${AWS_AMI}" --key-name "${AWS_SSH_KEY}" --subnet-id "${AWS_SUBNET_ID}" --security-group-ids $AWS_SECURITY_GROUP --instance-type "${AWS_INSTANCE_TYPE}" --user-data "$(cat ${TMP_DIR}/user-init | base64)" | jq -r ".Instances[0].InstanceId")
echo "Instance ID: ${AWS_INSTANCE_ID}"

ATL_SVC_NAME="$(atl_createTag "service_name" "${ATL_PRODUCT} AMI")"
ATL_OWNER="$(atl_createTag "business_owner" "RD:Dev Tools Engineering")"
ALT_RES_OWNER="$(atl_createTag "resource_owner" $(whoami))"

aws ec2 create-tags --region "${AWS_REGION}" --resources "${AWS_INSTANCE_ID}" --tags "$(atl_createTag "Name" "Atlassian ${ATL_PRODUCT} (AMI: ${AWS_AMI})")" "${ATL_SVC_NAME}" "${ATL_OWNER}" "${ALT_RES_OWNER}"
for volume in `aws ec2 describe-instances --region "${AWS_REGION}" --instance-ids "${AWS_INSTANCE_ID}" | jq -r ".Reservations[].Instances[].BlockDeviceMappings[].Ebs.VolumeId"`; do
    aws ec2 create-tags --region "${AWS_REGION}" --resources ${volume} --tags "$(atl_createTag "Name" "For ${AWS_INSTANCE_ID} running Atlassian ${ATL_PRODUCT} (${AWS_AMI})")" "${ATL_SVC_NAME}" "${ATL_OWNER}" "${ALT_RES_OWNER}"
done

AWS_HOST_NAME=$(aws ec2 describe-instances --region "${AWS_REGION}" --instance-ids "${AWS_INSTANCE_ID}" | jq -r ".Reservations[0].Instances[0].PublicDnsName")
let RETRIES=10
while [[ "${RETRIES}" -gt 0 && (-z "${AWS_HOST_NAME}" || "xnull" == "x${AWS_HOST_NAME}") ]]; do
    echo "Waiting for public host name to be published"
    sleep 10
    AWS_HOST_NAME=$(aws ec2 describe-instances --region "${AWS_REGION}" --instance-ids "${AWS_INSTANCE_ID}" | jq -r ".Reservations[0].Instances[0].PublicDnsName")
    if [[ -z "${AWS_HOST_NAME}" || "xnull" == "x${AWS_HOST_NAME}" ]]; then
        AWS_HOST_NAME=$(aws ec2 describe-instances --region "${AWS_REGION}" --instance-ids "${AWS_INSTANCE_ID}" | jq -r ".Reservations[0].Instances[0].PublicIpAddress")
    fi
    let RETRIES=RETRIES-1
done

if [[ -z "${AWS_HOST_NAME}" && "xnull" != "x${AWS_HOST_NAME}" ]]; then
    PRIVATE_IP=$(aws ec2 describe-instances --region "${AWS_REGION}" --instance-ids "${AWS_INSTANCE_ID}" | jq -r ".Reservations[0].Instances[0].PrivateIpAddress")
    echo "Unable to determine the public host name - please use the AWS EC2 console for region ${AWS_REGION} to determine this"
    echo "try connecting via Private Ip address: ${PRIVATE_IP}"
else
    echo "The public host name of instance ${AWS_INSTANCE_ID} is ${AWS_HOST_NAME}"
fi
echo "Done"
