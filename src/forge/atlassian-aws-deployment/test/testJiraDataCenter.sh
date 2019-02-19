#!/bin/bash
set -e

BASEDIR=$(dirname $0)
source $BASEDIR/atl-aws-extensions.sh

DB_PASSWORD="jira"
DB_MASTER_PASSWORD="postgres"
JIRA_VERSION="7.3.0-SNAPSHOT"

PARAM_PUBLIC_IP=$(atl_param "AssociatePublicIpAddress" "true")
PARAM_JIRA_VERSION=$(atl_param "JiraVersion" "${JIRA_VERSION}")
PARAM_DB_MASTER_PW=$(atl_param "DBMasterUserPassword" "${DB_MASTER_PASSWORD}")
PARAM_DB_PW=$(atl_param "DBPassword" "${DB_PASSWORD}")

${BASEDIR}/create-stack.sh "JiraDataCenter.template.yaml" "${PARAM_PUBLIC_IP}~${PARAM_JIRA_VERSION}~${PARAM_DB_MASTER_PW}~${PARAM_DB_PW}"
