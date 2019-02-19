#!/bin/bash
set -e

BASEDIR=$(dirname $0)
source $BASEDIR/atl-aws-extensions.sh

EBS_OPTIMIZED=${ebsoptimized-"false"}
INSTANCE_TYPE=${instancetype-"c3.large"}
SNAPSHOT=${snapshot}
VOLUME_TYPE=${volumetype}
BITBUCKET_VERSION="latest"

PARAMS="$(atl_param "AssociatePublicIpAddress" "true")"
PARAMS+="~$(atl_param "BitbucketProperties" "plugin.bitbucket-scm-cache.refs.enabled=true")"
PARAMS+="~$(atl_param "BitbucketVersion" "${BITBUCKET_VERSION}")"
PARAMS+="~$(atl_param "EbsOptimized" "${EBS_OPTIMIZED}")"
PARAMS+="~$(atl_param "InstanceType" "${INSTANCE_TYPE}")"
PARAMS+="~$(atl_param "HomeSize" "300")"
PARAMS+="~$(atl_param "AMIOpts" "ATL_FORCE_HOST_NAME=true")"

if [[ -n ${VOLUME_TYPE} ]]; then
    PARAMS+="~$(atl_param "HomeVolumeType" "${VOLUME_TYPE}")"
fi
if [[ -n ${SNAPSHOT} ]]; then
  PARAMS+="~$(atl_param "HomeVolumeSnapshotId" "${SNAPSHOT}")"
fi

${BASEDIR}/create-stack.sh "BitbucketServer.template.yaml" "${PARAMS}" "false"
