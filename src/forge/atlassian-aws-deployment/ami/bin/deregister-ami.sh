#!/bin/bash
set -e

TMP_DIR=$(mktemp -d -t bbaws)
trap "rm -rf ${TMP_DIR}" EXIT

function usage {
    cat << EOF
usage: $0 options

This script deregisters a product AMI optionally terminating any instances running for this image.

OPTIONS:
   -r The AWS region to use. If not supplied, the AWS_REGION environment variable must be set
   -a The AWS AMI to use. If not supplied, the AWS_AMI environment variable must be set
   -t Terminate any associated instances before deregistering the AMI
EOF
}

AWS_REGION=${AWS_REGION}
AWS_AMI=${AWS_AMI}
TERMINATE_INSTANCES=
while getopts “hr:a:t” OPTION
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
         t)
             TERMINATE_INSTANCES=true
             ;;
         ?)
             usage
             exit
             ;;
     esac
done

AWS_REGION=$(echo "${AWS_REGION}" | tr [:upper:] [:lower:])
AWS_AMI=$(echo "${AWS_AMI}" | tr [:upper:] [:lower:])

if [[ -z "${AWS_REGION}" ]]; then
    echo "Error: AWS region option not supplied (-r) nor defined as an env var (AWS_VPC)"
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

INSTANCES=$(aws ec2 describe-instances --region "${AWS_REGION}" | jq -r ".Reservations[].Instances[] | select(.ImageId == \"$ami\") | select(.State.Name != \"terminated\") | .InstanceId")
if [[ ${#INSTANCES[@]} -ne 0 ]]; then
    if [[ -n "${TERMINATE_INSTANCES}" ]]; then
        echo "Terminating instances $(printf " %s" "${INSTANCES[@]}")"
        aws ec2 terminate-instances --region ${AWS_REGION} --instance-ids $(printf " %s" "${INSTANCES[@]}") | jq -r ".TerminatingInstances[] | \"\(.InstanceId) \(.CurrentState.Name)\""
    else
        echo "The following instances must be terminated before deregistration of the AMI can proceed: $(printf " %s" "${INSTANCES[@]}")"
        exit 1
    fi
fi
echo "Deregistering AMI"
aws ec2 deregister-image --region "${AWS_REGION}" --image-id "${AWS_AMI}"

echo "Done"
