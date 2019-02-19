#!/bin/bash
### BEGIN INIT INFO
# Provides:          atl-init-20-instance-store
# Required-Start:    cloud-final
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:
# Short-Description: Ensures "bitbucket" dir is present on the instance store mount as configured in (/etc/sysconfig/atl)
# Description:       Ensures "bitbucket" dir is present on the instance store mount as configured in (/etc/sysconfig/atl).
#                    Configures the ${SERVICE_NAME} which ensures the "bitbucket" dir is present at the instance store mount. This directory is
#                    used for file operations that benefit from fast IO but which need not be persisted between instance start/stops.
### END INIT INFO

set -e

. /etc/init.d/atl-functions

trap 'atl_error ${LINENO}' ERR

ATL_FACTORY_CONFIG=/etc/sysconfig/atl
ATL_USER_CONFIG=/etc/atl

[[ -r "${ATL_FACTORY_CONFIG}" ]] && . "${ATL_FACTORY_CONFIG}"
[[ -r "${ATL_USER_CONFIG}" ]] && . "${ATL_USER_CONFIG}"

ATL_LOG=${ATL_LOG:?"The Atlassian log location must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_ENABLED_PRODUCTS=${ATL_ENABLED_PRODUCTS:?"The enabled Atlassian products must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_INSTANCE_STORE_MOUNT=${ATL_INSTANCE_STORE_MOUNT:?"The instance store mount must be supplied in ${ATL_FACTORY_CONFIG}"}

function start {
    atl_log "=== BEGIN: service atl-init-20-instance-store start ==="
    atl_log "Initialising instance store"

    if [[ -n "${ATL_INSTANCE_STORE_MOUNT}" && -w "${ATL_INSTANCE_STORE_MOUNT}" ]]; then

        prepareInstanceStoreMount

        for product in $(atl_enabled_products); do
            local LOWER_CASE_PRODUCT="$(atl_toLowerCase ${product})"
            local UPPER_CASE_PRODUCT="$(atl_toUpperCase ${product})"
            local SENTENCE_CASE_PRODUCT="$(atl_toSentenceCase ${product})"

            if [[ ! -e "${ATL_INSTANCE_STORE_MOUNT}/${LOWER_CASE_PRODUCT}" ]]; then
                if [[ "xfunction" == "x$(type -t create${SENTENCE_CASE_PRODUCT}InstanceStoreDirs)" ]]; then
                    atl_log "Creating instance store directories for enabled product \"${SENTENCE_CASE_PRODUCT}\""
                    create${SENTENCE_CASE_PRODUCT}InstanceStoreDirs "${ATL_INSTANCE_STORE_MOUNT}/${LOWER_CASE_PRODUCT}"
                else
                    atl_log "Not creating instance store directories for enabled product \"${SENTENCE_CASE_PRODUCT}\" because no initialisation has been defined"
                fi
            else
                atl_log "Not creating ${ATL_INSTANCE_STORE_MOUNT}/${LOWER_CASE_PRODUCT} because it already exists"
            fi
        done
    else
        atl_log "The instance store mount ${ATL_INSTANCE_STORE_MOUNT} does not exist - not creating product directories"
    fi

    atl_log "=== END:   service atl-init-20-instance-store start ==="
}

function prepareInstanceStoreMount {
    # The instance store device may come to us preformatted, preconfigured in /etc/fstab, and premounted, but not always.
    # More details can be found at http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html
    if ! mount | grep "${ATL_INSTANCE_STORE_MOUNT}"; then
        atl_log "Preparing to mount to instance store target. Starting to format instance store target."
        # If formatting unsuccessful, log message and continue
        mkfs.ext4 -F -E nodiscard "${ATL_INSTANCE_STORE_BLOCK_DEVICE}"
        if grep "${ATL_INSTANCE_STORE_MOUNT}" /etc/fstab; then
            # Enable support for TRIM
            atl_log "Enable support for TRIM"
            if ! grep "${ATL_INSTANCE_STORE_MOUNT}.*discard" /etc/fstab; then
                awk '{ if ($2 == "'${ATL_INSTANCE_STORE_MOUNT}'" && $4 !~ "discard") $4 = $4 ",discard"; print }' \
                    /etc/fstab > /tmp/fstab && mv -f /tmp/fstab /etc/fstab
            fi
        else
            atl_log "Adding new entry into fstab file"
            echo "${ATL_INSTANCE_STORE_BLOCK_DEVICE}  ${ATL_INSTANCE_STORE_MOUNT} auto	discard,nofail,comment=atl-init-20-instance-store  0  2" >>/etc/fstab
        fi

        atl_log "Mounting to instance store"
        mount "${ATL_INSTANCE_STORE_MOUNT}"
        atl_log "Mounting to instance store ==> DONE"
    fi
}

function createBitbucketInstanceStoreDirs {
    atl_log "Invoking create-instance-store-dirs on service atl-init-bitbucket"
    service "atl-init-bitbucket" create-instance-store-dirs $1
}

function createJiraInstanceStoreDirs {
    atl_log "Invoking create-instance-store-dirs on service atl-init-jira"
    service "atl-init-jira" create-instance-store-dirs $1
}

case "$1" in
    start)
        $1
        ;;
    stop)
        ;;
    *)
        echo $"Usage: $0 {start}"
        RETVAL=1
esac
exit ${RETVAL}
