#!/usr/bin/env bash

function atl_createTag {
    local KEY=$1
    local VALUE=$2

    echo Key="${KEY}",Value="\"${VALUE}\""
}

function atl_toSentenceCase {
    echo "$(tr '[:lower:]' '[:upper:]' <<< ${1:0:1})${1:1}"
}

function atl_awsLinuxAmi {
    local REGION=${1:?"A region must be specified"}
    local AWS_LINUX_VERSION=${2:?"An AWS linux version must be specified"}
    aws --region "${REGION}" ec2 describe-images \
        --owners 137112412989 \
        --filters Name=virtualization-type,Values=hvm Name=description,Values="Amazon Linux AMI ${AWS_LINUX_VERSION}.* x86_64 HVM GP2" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --output text
}

function atl_replaceAmiByRegion {
    local REGION=${1:?"A region must be specified"}
    local AMI_ID=${2:?"A AMI ID must be specified"}
    local TEMPLATE_FILE=${3:?"A TEMPLATE FILE must be specified"}
    sed -i '' -e "/.*${REGION}/ {" -e "n; s/HVM64:.*/HVM64: ${AMI_ID}/" -e '}' ${TEMPLATE_FILE}
}
