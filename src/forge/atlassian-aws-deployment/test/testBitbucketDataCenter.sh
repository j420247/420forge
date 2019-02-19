#!/bin/bash
set -e

BASEDIR=$(dirname $0)
source $BASEDIR/atl-aws-extensions.sh

DB_PASSWORD="stash"
DB_MASTER_PASSWORD="postgres"
BITBUCKET_VERSION="4.10.0"

EBS_SNAPSHOT=${ebs_snapshot}
RDS_SNAPSHOT=${rds_snapshot}
ES_SNAPSHOT=${es_snapshot}
FILE_SERVER_INSTANCE_TYPE=${fileserverinstancetype}
VOLUME_TYPE=${volumetype}
CREATE_BUCKET=${create_bucket}
ES_S3_BUCKET=${es_s3_bucket}
STANDBY_DB_MASTER=${standby_db_master}
SSL_CERTIFICATE=${ssl_certificate}

PARAMS="$(atl_param "AssociatePublicIpAddress" "true")"
PARAMS+="~$(atl_param "BitbucketProperties" "plugin.bitbucket-scm-cache.refs.enabled=true")"
PARAMS+="~$(atl_param "BitbucketVersion" "${BITBUCKET_VERSION}")"
PARAMS+="~$(atl_param "DBMasterUserPassword" "${DB_MASTER_PASSWORD}")"
PARAMS+="~$(atl_param "DBPassword" "${DB_PASSWORD}")"
PARAMS+="~$(atl_param "HomeSize" "300")"
PARAMS+="~$(atl_param "CidrBlock" "0.0.0.0/0")"
PARAMS+="~$(atl_param "StartCollectd" "true")"
PARAMS+="~$(atl_param "AMIOpts" "ATL_FORCE_HOST_NAME=true")"

if [[ -n ${FILE_SERVER_INSTANCE_TYPE} ]]; then
    PARAMS+="~$(atl_param "FileServerInstanceType" "${FILE_SERVER_INSTANCE_TYPE}")"
fi
if [[ -n ${VOLUME_TYPE} ]]; then
    PARAMS+="~$(atl_param "HomeVolumeType" "${VOLUME_TYPE}")"
fi
if [[ -n ${RDS_SNAPSHOT} ]]; then
    PARAMS+="~$(atl_param "DBSnapshotId" "${RDS_SNAPSHOT}")"
fi
if [[ -n ${EBS_SNAPSHOT} ]]; then
    PARAMS+="~$(atl_param "HomeVolumeSnapshotId" "${EBS_SNAPSHOT}")"
fi
if [[ -n ${ES_SNAPSHOT} ]]; then
    PARAMS+="~$(atl_param "ESSnapshotId" "${ES_SNAPSHOT}")"
fi
if [[ -n ${STANDBY_DB_MASTER} ]]; then
    PARAMS+="~$(atl_param "DBMaster" "${STANDBY_DB_MASTER}")"
fi
if [[ -n ${SSL_CERTIFICATE} ]]; then
    PARAMS+="~$(atl_param "SSLCertificateName" "${SSL_CERTIFICATE}")"
fi
if [[ -n ${ES_S3_BUCKET} ]]; then
    PARAMS+="~$(atl_param "ESBucketName" "${ES_S3_BUCKET}")"
fi
if [[ -n ${CREATE_BUCKET} ]]; then
    PARAMS+="~$(atl_param "CreateBucket" "${CREATE_BUCKET}")"
fi

${BASEDIR}/create-stack.sh "BitbucketDataCenter.template" "${PARAMS}"
