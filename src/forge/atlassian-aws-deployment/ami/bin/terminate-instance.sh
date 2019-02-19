#!/bin/bash
set -e

TMP_DIR=$(mktemp -d -t packer)
trap "rm -rf ${TMP_DIR}" EXIT

function usage {
cat << EOF
usage: $0 options

This script terminates an AWS EC2 instance.

OPTIONS:
   -r The AWS region to use. If not supplied, the AWS_REGION environment variable must be set
   -i The AWS instance to terminate. If not supplied, the AWS_INSTANCE environment variable must be set
EOF
}

AWS_REGION=${AWS_REGION}
AWS_INSTANCE_ID=${AWS_INSTANCE_ID}
while getopts “hr:i:” OPTION
do
     case $OPTION in
         h)
             usage
             exit 1
             ;;
         r)
             AWS_REGION="${OPTARG}"
             ;;
         i)
             AWS_INSTANCE_ID="${OPTARG}"
             ;;
         ?)
             usage
             exit
             ;;
     esac
done

AWS_REGION=$(echo "${AWS_REGION}" | tr [:upper:] [:lower:])
AWS_INSTANCE_ID=$(echo "${AWS_INSTANCE_ID}" | tr [:upper:] [:lower:])

if [[ -z "${AWS_REGION}" ]]; then
    echo "Error: AWS region option not supplied (-r) nor defined as an env var (AWS_REGION)"
    echo
    usage
    exit 1
fi

if [[ -z "${AWS_INSTANCE_ID}" ]]; then
    echo "Error: AWS instance option not supplied (-i) nor defined as an env var (AWS_INSTANCE)"
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

echo "Terminating instance ${AWS_INSTANCE_ID}"
AWS_HOST_NAME=$(aws ec2 describe-instances --region "${AWS_REGION}" --instance-ids "${AWS_INSTANCE_ID}" | jq -r ".Reservations[0].Instances[0].PublicDnsName")
AWS_INSTANCE_STATUS=$(aws ec2 terminate-instances --region ${AWS_REGION} --instance-ids ${AWS_INSTANCE_ID} | jq -r ".TerminatingInstances[0].CurrentState.Name")
let RETRIES=10
while [[ "${RETRIES}" -gt 0 && (-z "${AWS_INSTANCE_STATUS}" || "xnull" == "x${AWS_INSTANCE_STATUS}") ]]; do
    echo "Waiting for instance to terminate"
    sleep 10
    let RETRIES=RETRIES-1
done
echo "${AWS_INSTANCE_ID}: ${AWS_INSTANCE_STATUS}"
echo "Done"