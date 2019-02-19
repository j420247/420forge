#!/bin/bash
set -e

BASEDIR=$(dirname $0)
source $BASEDIR/atl-aws-extensions.sh

CATALINA_OPTS="-Dcom.sun.management.jmxremote.port=3333 -Dcom.sun.management.jmxremote.ssl=false -Dcom.sun.management.jmxremote.authenticate=false -Dconfluence.hazelcast.jmx.enable=true -Dconfluence.hibernate.jmx.enable=true"
DB_PASSWORD="confluence"
DB_MASTER_PASSWORD="postgres"
CONFLUENCE_VERSION="6.1.0-rc1"
CONFLUENCE_DOWNLOAD_URL="https://s3-ap-southeast-2.amazonaws.com/aws-deployment-test/releases/confluence/atlassian-confluence-6.1.0-m09-linux-x64.bin"

PARAMS=$(atl_param "AssociatePublicIpAddress" "true")
PARAMS+="~$(atl_param "ConfluenceVersion" "${CONFLUENCE_VERSION}")"
PARAMS+="~$(atl_param "DBMasterUserPassword" "${DB_MASTER_PASSWORD}")"
PARAMS+="~$(atl_param "DBPassword" "${DB_PASSWORD}")"
PARAMS+="~$(atl_param "CatalinaOpts" "${CATALINA_OPTS}")"
PARAMS+="~$(atl_param "CidrBlock" "0.0.0.0/0")"

#PARAMS+="~$(atl_param "ClusterNodeInstanceType" "i2.xlarge")"
#PARAMS+="~$(atl_param "SynchronyNodeInstanceType" "i2.xlarge")"
#PARAMS+="~$(atl_param "ConfluenceDownloadUrl" "${CONFLUENCE_DOWNLOAD_URL}")"

${BASEDIR}/create-stack.sh "ConfluenceDataCenter.template" "${PARAMS}" "true"
