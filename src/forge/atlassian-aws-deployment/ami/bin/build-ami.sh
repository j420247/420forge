#!/usr/bin/env bash
# shellcheck disable=SC1090,SC2034,SC2064

set -e

TMP_DIR=$(mktemp -d -t atlaws.XXXXXX)
echo "TMP_DIR = ${TMP_DIR}"
PACKER_LOG_PATH="${TMP_DIR}/packer.debug.log"
# comment out the trap if you want the debug output to persist after the run
trap "rm -rf ${TMP_DIR}" EXIT

BASEDIR=$(dirname "$0")
DEBUG_MODE=
source "${BASEDIR}/atl-aws-functions.sh"

function usage {
# -b specifies business unit, and -o specifies resource owner. These are silently available options used to tag AWS resources
    cat << EOF
usage: $0 options

This script generates an Atlassian AMI with Packer.

OPTIONS:
   -p The product to build an AMI for. If not supplied 'Bitbucket' is assumed
   -r The AWS region to use. If not supplied, the AWS_REGION environment variable must be set
   -v The AWS VPC to use in the supplied region. If not supplied, the AWS_VPC_ID environment variable must be set
   -s The AWS Subnet to use in the supplied VPC. If not supplied, the AWS_SUBNET_ID environment variable must be set
   -c Whether to copy the AMI to other AWS regions. Defaults to false
   -u Whether to update the CloudFormation templates' AMI mappings. Defaults to false
   -P make AMI public
   -d debug mode
EOF
}

function err_usage {
    echo "Error: $1"
    echo
    usage
    exit 1
}

export AWS_LINUX_VERSION="2018.03"
COPY_AMIS=
UPDATE_CLOUDFORMATION=
ATL_PRODUCT="Bitbucket"

while getopts ":dhPr:cv:s:p:ub:o:" OPTION
do
    case $OPTION in
        h)
            usage
            exit 1
            ;;
        p)
            ATL_PRODUCT="${OPTARG}"
            ;;
        r)
            AWS_REGION="${OPTARG}"
            ;;
        s)
            AWS_SUBNET_ID="${OPTARG}"
            ;;
        c)
            COPY_AMIS=true
            ;;
        P)
            PUBLIC_AMIS=true
            ;;
        u)
            UPDATE_CLOUDFORMATION=true
            ;;
        v)
            AWS_VPC_ID="${OPTARG}"
            ;;
        d)
            DEBUG_MODE="true"
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
case $ATL_PRODUCT_ID in
    bitbucket)
        ATL_PRODUCT="Bitbucket"
        ;;
    jira)
        ATL_PRODUCT="Jira"
        ;;
    confluence)
        ATL_PRODUCT="Confluence"
        ;;
    crowd)
        ATL_PRODUCT="Crowd"
        ;;
    *)
        echo "Unsupported product specified."
        exit 1

esac

AWS_REGION=$(echo "${AWS_REGION}" | tr "[:upper:]" "[:lower:]")
AWS_VPC_ID=$(echo "${AWS_VPC_ID}" | tr "[:upper:]" "[:lower:]")

if [[ -z "${AWS_REGION}" ]]; then
    err_usage "AWS region option not supplied (-r) nor defined as an env var (AWS_REGION)"
fi

if [[ -z "${AWS_VPC_ID}" ]]; then
    err_usage "AWS VPC option not supplied (-v) nor defined as an env var (AWS_VPC_ID)"
fi

if [[ -z "${AWS_SUBNET_ID}" ]]; then
    err_usage "AWS Subnet option not supplied (-s) nor defined as an env var (AWS_SUBNET_ID)"
fi

if [[ -z "${AWS_ACCESS_KEY:-$AWS_ACCESS_KEY_ID}" ]]; then
    err_usage "AWS_ACCESS_KEY and AWS_ACCESS_KEY_ID env var not defined"
fi

if [[ -z "${AWS_SECRET_KEY:-$AWS_SECRET_ACCESS_KEY}" ]]; then
    err_usage "AWS_SECRET_KEY and AWS_SECRET_ACCESS_KEY env var not defined"
fi

DEFAULT_BASE_AMI=$(atl_awsLinuxAmi "$AWS_REGION" "$AWS_LINUX_VERSION")
BASE_AMI="${BASE_AMI:-$DEFAULT_BASE_AMI}"
if [[ -z "${BASE_AMI}" ]]; then
    err_usage "BASE_AMI env var not defined and no mapping found to fall back on"
fi

export AWS_DEFAULT_REGION=${AWS_REGION}
export TZ=GMT
DATE=$(date '+%Y.%m.%d_%H%M')

echo "Building ${ATL_PRODUCT} in ${AWS_REGION}"

packer -machine-readable build \
    -var aws_access_key="${AWS_ACCESS_KEY}" \
    -var aws_secret_key="${AWS_SECRET_KEY}" \
    -var aws_session_token="${AWS_SESSION_TOKEN}" \
    -var vpc_id="${AWS_VPC_ID}" \
    -var base_ami="${BASE_AMI}" \
    -var business_unit="${BUSINESS_UNIT}" \
    -var resource_owner="${RESOURCE_OWNER}" \
    -var availability_zone="${AWS_AZ}" \
    -var subnet_id="${AWS_SUBNET_ID}" \
    -var aws_region="${AWS_REGION}" \
    -var aws_linux_version="${AWS_LINUX_VERSION}" \
    ${DEBUG_MODE:+ "-debug -on-error=abort"} \
    "$(dirname "$0")/../${ATL_PRODUCT_ID}.json" | tee "${TMP_DIR}/packer.log"

AWS_AMI=$(grep "amazon-ebs: AMI:" "${TMP_DIR}/packer.log" | awk '{ print $4 }')

if [[ -z "${AWS_AMI}" ]]; then
    echo "Packer failed to build the AMI"
    exit 1
fi
echo "AMI created: ${AWS_AMI}"

echo "Tagging AMI ${AWS_AMI} with name \"Atlassian ${ATL_PRODUCT} (${DATE})\""
NAME_TAG="$(atl_createTag "Name" "Atlassian ${ATL_PRODUCT} ${DATE}")"

aws ec2 create-tags --resource "${AWS_AMI}" --tags "${NAME_TAG}"

declare -a regionToAmi
i=0
regionToAmi[$i]="${AWS_REGION} ${AWS_AMI}"

if [[ -n "${COPY_AMIS}" ]]; then
    AWS_AMI_NAME=$(aws ec2 describe-images --region "${AWS_REGION}" --image-ids "${AWS_AMI}" | jq -r ".Images[0].Name")
    declare -a AWS_OTHER_REGIONS
    while IFS=$'\n' read -r line; do
        AWS_OTHER_REGIONS+=("$line");
    done < <(aws ec2 --region "${AWS_REGION}" describe-regions | jq --arg AWS_REGION "$AWS_REGION" -r '.Regions[] | select(.RegionName | contains($AWS_REGION) | not) | .RegionName')
    echo "Copying AMI ${AWS_AMI} to regions ${AWS_OTHER_REGIONS[*]}"
    for region in "${AWS_OTHER_REGIONS[@]}"; do
        ami=$(aws ec2 copy-image --source-region "${AWS_REGION}" --source-image-id "${AWS_AMI}" --region "${region}" --name "${AWS_AMI_NAME}" | jq -r ".ImageId")
        (
            echo "Copy to ${region} started (AMI ID: ${ami})"
            aws ec2 create-tags --region "${region}" --resource "${ami}" --tags "${NAME_TAG}"
        )
        i=$((i+1))
        regionToAmi[$i]="${region} ${ami}"
    done
fi

if [[ -n "${UPDATE_CLOUDFORMATION}" ]]; then
    echo "Updating ${ATL_PRODUCT} CloudFormation template AMI mapping(s)..."
    TEMPLATES=$(find "${BASEDIR}/../../templates" -iname "${ATL_PRODUCT}*.template.yaml" -maxdepth 1)
    for template in "${TEMPLATES[@]}"; do
        for regionami in "${regionToAmi[@]}"; do
            region=$(echo "$regionami" | cut -d' ' -f1)
            ami=$(echo "$regionami" | cut -d' ' -f2)
            echo "Update ami for region ${region} to ${ami} in template ${template}"
            atl_replaceAmiByRegion "${region}" "${ami}" "${template}"
        done
    done
fi

# this had to be done separate from the copies as the copy needs to have completed before it can be made public
if [[ -n "${PUBLIC_AMIS}" ]]; then
    echo "Making AMI Public in regions ${AWS_REGION} ${AWS_OTHER_REGIONS[*]}"
    aws ec2 modify-image-attribute --region "${AWS_REGION}" --image-id "${AWS_AMI}" --launch-permission "{\"Add\": [{\"Group\":\"all\"}]}"
    for regionami in "${regionToAmi[@]}"; do
        region=$(echo "$regionami" | cut -d' ' -f1)
        ami=$(echo "$regionami" | cut -d' ' -f2)
        echo "Make AMI ${ami} in region ${region} public"
        # make Public
        until aws ec2 modify-image-attribute --region "${region}" --image-id "${ami}" --launch-permission "{\"Add\": [{\"Group\":\"all\"}]}";
            do
                echo ... most likely waiting AWS ... retrying shortly
                sleep 30
            done
    done
fi
echo "Done"
