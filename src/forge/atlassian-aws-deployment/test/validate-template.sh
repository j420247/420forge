#!/bin/bash
# Validate Cloudformation templates that are located in /templates and /quickstart folders.
# The script requires AWS credentials to be set in the shell and connectivity to AWS.
#==============================================================================
BASEDIR=$(dirname $0)
S3_BUCKET="dc-deployments-temp-bamboo" # Make sure you have access to this bucket if you are validating large templates

cd ${BASEDIR}/..
ABSOLUTE_AWS_DIR=$(pwd)

TEMPLATE_NAME=${1:?"A template name must be specified."}

if [[ "$TEMPLATE_NAME" == *"quickstart-"* ]]; then
    TEMPLATES_PATH="${ABSOLUTE_AWS_DIR}/quickstarts"
else
    TEMPLATES_PATH="${ABSOLUTE_AWS_DIR}/templates"
fi

TEMPLATE_FULL_PATH=${TEMPLATES_PATH}/${TEMPLATE_NAME}

TEMPLATE_SIZE=$(wc -c < "${TEMPLATE_FULL_PATH}")

if [ "${TEMPLATE_SIZE}" -ge 51200 ]; then
    aws s3 cp ${TEMPLATE_FULL_PATH} s3://${S3_BUCKET}/${TEMPLATE_NAME}
    TEMPLATE_SOURCE="--template-url https://s3.amazonaws.com/dc-deployments-temp-bamboo/${TEMPLATE_NAME}"
else
    TEMPLATE_SOURCE="--template-body file://${TEMPLATE_FULL_PATH}"
fi


echo "Validating ${TEMPLATE_NAME}..."
VALIDATION_OUTPUT=$(aws cloudformation validate-template ${TEMPLATE_SOURCE} 2>&1)
VALIDATION_EXIT_CODE=$?

if [ ${VALIDATION_EXIT_CODE} -ne 0 ]; then
    ERROR_TO_DISPLAY=$(echo ${VALIDATION_OUTPUT} | tail -1)

    echo "[ERROR] ${TEMPLATE_NAME}"
    echo "[ERROR] ${ERROR_TO_DISPLAY}"
    exit 1
else
    echo "[OK]: ${TEMPLATE_NAME}"
    exit 0
fi