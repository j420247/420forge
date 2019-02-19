#!/bin/bash
### BEGIN INIT INFO
# Provides:          atl-init-10-volume
# Required-Start:    cloud-final
# Required-Stop:
# X-Start-Before:    atl-init-30-db atl-init-40-products
# Default-Start:     2 3 4 5
# Default-Stop:
# Short-Description: Ensures the Atlassian application data volume has been formatted and mounted.
# Description:       Ensures the Atlassian application data volume has been formatted and mounted.
### END INIT INFO

set -e

. /etc/init.d/atl-functions

trap 'atl_error ${LINENO}' ERR

ATL_FACTORY_CONFIG=/etc/sysconfig/atl
ATL_USER_CONFIG=/etc/atl

[[ -r "${ATL_FACTORY_CONFIG}" ]] && . "${ATL_FACTORY_CONFIG}"
[[ -r "${ATL_USER_CONFIG}" ]] && . "${ATL_USER_CONFIG}"

ATL_LOG=${ATL_LOG:?"The Atlassian log location must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_DATA_BLOCK_DEVICE=${ATL_APP_DATA_BLOCK_DEVICE:?"The application data block device must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_DATA_MOUNT=${ATL_APP_DATA_MOUNT:?"The application data mount must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_DATA_FS_TYPE=${ATL_APP_DATA_FS_TYPE:?"The application data filesystem type must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_NFS_SERVER=${ATL_APP_NFS_SERVER:?"The NFS server must be supplied in ${ATL_FACTORY_CONFIG}"}

function start {
    atl_log "=== BEGIN: service atl-init-10-volume start ==="
    atl_log "Initialising data volume"

    disableThisService
    if [[ "x${ATL_APP_DATA_MOUNT_ENABLED}" == "xtrue" ]]; then
        initSharedVolume
    fi

    initSharedHomes

    atl_log "=== END:   service atl-init-10-volume start ==="
}

function disableThisService {
    atl_log "Disabling atl-init-10-volume for future boots"
    chkconfig "atl-init-10-volume" off >> "${ATL_LOG}" 2>&1
    atl_log "Done disabling atl-init-10-volume for future boots"
}

function initSharedVolume {
    atl_log "Creating ${ATL_APP_DATA_MOUNT} directory"
    mkdir -p ${ATL_APP_DATA_MOUNT} >> "${ATL_LOG}" 2>&1

    atl_log "Checking ${ATL_APP_DATA_BLOCK_DEVICE} to be mounted on ${ATL_APP_DATA_MOUNT}"
    MAGIC=$(file -s -L "${ATL_APP_DATA_BLOCK_DEVICE}")
    if [[ -b "${ATL_APP_DATA_BLOCK_DEVICE}" || -L "${ATL_APP_DATA_BLOCK_DEVICE}" ]]; then
        if [[ "${ATL_APP_DATA_BLOCK_DEVICE}: data" == "${MAGIC}" ]]; then
            case "${ATL_APP_DATA_FS_TYPE}" in
            "zfs")
                atl_log "Setting up ZFS"

                # Prepare the disk to for use
                parted -s ${ATL_APP_DATA_BLOCK_DEVICE} mktable gpt >> "${ATL_LOG}" 2>&1

                # Load ZFS module
                /sbin/modprobe zfs >> "${ATL_LOG}" 2>&1

                atl_log "Creating ZFS pool"

                # Create ZFS volume
                zpool create tank $(basename ${ATL_APP_DATA_BLOCK_DEVICE}) >> "${ATL_LOG}" 2>&1

                atl_log "Creating ZFS file system 'tank/atlassian-home'"

                # Create ZFS filesystem
                if [[ "x${ATL_APP_NFS_SERVER}" == "xtrue" ]]; then
                    local sharenfs=on
                else
                    local sharenfs=off
                fi
                zfs create -o compression=off -o sharesmb=off -o sharenfs=${sharenfs} -o atime=off -o recordsize=8k \
                    -o mountpoint=${ATL_APP_DATA_MOUNT} tank/atlassian-home >> "${ATL_LOG}" 2>&1

                atl_log "Installing ZFS scrub cron script"

                mkdir -p "/etc/cron.weekly" >> "${ATL_LOG}" 2>&1

                cat > "/etc/cron.weekly/zfs-scrub" << EOF
#!/bin/bash
# This script was generated during the creation of the Bitbucket AMI
zpool scrub tank
EOF

                chmod +x "/etc/cron.weekly/zfs-scrub" >> "${ATL_LOG}" 2>&1

                atl_log "Finished ZFS setup"
                ;;
            *)

                atl_log "Formatting ${ATL_APP_DATA_BLOCK_DEVICE} with ${ATL_APP_DATA_FS_TYPE} filesystem"
                local TYPE="${ATL_APP_DATA_FS_TYPE}"
                mkfs -t "${ATL_APP_DATA_FS_TYPE}" "${ATL_APP_DATA_BLOCK_DEVICE}" >> "${ATL_LOG}" 2>&1
                mountAndMaybeExportVolume "${TYPE}"
                ;;
            esac
        else
            case "${MAGIC}" in
            "${ATL_APP_DATA_BLOCK_DEVICE}: GPT"*)
                atl_log "Detected ${ATL_APP_DATA_BLOCK_DEVICE} as ${MAGIC}, attempting to mount as ZFS"

                # Load ZFS module
                /sbin/modprobe zfs >> "${ATL_LOG}" 2>&1

                atl_log "Importing existing zpool"
                zpool import -f tank >> "${ATL_LOG}" 2>&1

                if [[ "x${ATL_APP_NFS_SERVER}" == "xtrue" ]]; then
                    local sharenfs=on
                else
                    local sharenfs=off
                fi

                atl_log "Setting 'sharenfs=${sharenfs}' on tank/atlassian-home"
                # Handle the case where you restore a snapshot from Server to Data Center or vice versa
                zfs set sharenfs=${sharenfs} tank/atlassian-home >> "${ATL_LOG}" 2>&1

                atl_log "Installing ZFS scrub cron script"

                mkdir -p "/etc/cron.weekly" >> "${ATL_LOG}" 2>&1

                cat > "/etc/cron.weekly/zfs-scrub" << EOF
#!/bin/bash
# This script was generated during the creation of the Bitbucket AMI
zpool scrub tank
EOF

                chmod +x "/etc/cron.weekly/zfs-scrub" >> "${ATL_LOG}" 2>&1

                atl_log "Finished ZFS setup"
                ;;
            *)
                atl_log "Using preformatted ${MAGIC}"
                local TYPE=$(udevadm info --query=property --name="${ATL_APP_DATA_BLOCK_DEVICE}" | sed -n s/ID_FS_TYPE=//p)
                if [[ $? != 0 || -z ${TYPE} ]]; then
                    atl_log "WARNING: udevadm info --query=property --name=\"${ATL_APP_DATA_BLOCK_DEVICE}\" failed: ${TYPE}"
                    TYPE=$(echo ${MAGIC} | grep -o '[^ ]* filesystem data' | awk '{print $1}')
                    if [[ $? != 0 || -z ${TYPE} ]]; then
                        atl_log "WARNING: file -s -L \"${ATL_APP_DATA_BLOCK_DEVICE}\" failed: ${TYPE}"
                        atl_log "WARNING: Trying ${ATL_APP_DATA_FS_TYPE}"
                        TYPE="${ATL_APP_DATA_FS_TYPE}"
                    fi
                fi
                mountAndMaybeExportVolume "${TYPE}"
                ;;
            esac
        fi
    else
        atl_log "WARNING: expected a block device mapping, got ${MAGIC}"
    fi
}

function initSharedHomes {
    for product in $(atl_enabled_shared_homes); do
        local LOWER_CASE_PRODUCT="$(atl_toLowerCase ${product})"
        local UPPER_CASE_PRODUCT="$(atl_toUpperCase ${product})"
        local USER_VAR="ATL_${UPPER_CASE_PRODUCT}_USER"
        local USER="${!USER_VAR}"
        local CONFIG_PROPERTIES_VAR="ATL_${UPPER_CASE_PRODUCT}_PROPERTIES"
        local CONFIG_PROPERTIES="${!CONFIG_PROPERTIES_VAR}"

        atl_log "Creating ${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}"
        mkdir -p "${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}" >> "${ATL_LOG}" 2>&1
        chown ${USER}:${USER} "${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}" >> "${ATL_LOG}" 2>&1

        atl_log "Creating ${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}/shared"
        mkdir -p "${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}/shared" >> "${ATL_LOG}" 2>&1
        chown ${USER}:${USER} "${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}/shared" >> "${ATL_LOG}" 2>&1

        if [[ -f "${CONFIG_PROPERTIES}" ]]; then
            local CONFIG_PROPERTIES_FILENAME="$(basename "${CONFIG_PROPERTIES}")"
            local DEST_CONFIG_PROPERTIES="${ATL_APP_DATA_MOUNT}/${LOWER_CASE_PRODUCT}/shared/${CONFIG_PROPERTIES_FILENAME}"
            atl_log "Appending ${CONFIG_PROPERTIES} to ${DEST_CONFIG_PROPERTIES}"
            su ${USER} -c "cat \"${CONFIG_PROPERTIES}\" >> \"${DEST_CONFIG_PROPERTIES}\"" >> "${ATL_LOG}" 2>&1
            rm -f "${CONFIG_PROPERTIES}" >> "${ATL_LOG}" 2>&1
        fi
    done
}

function mountAndMaybeExportVolume {
    local TYPE=$1

    atl_log "Mounting ${ATL_APP_DATA_BLOCK_DEVICE} on ${ATL_APP_DATA_MOUNT} type ${TYPE}"

    echo "${ATL_APP_DATA_BLOCK_DEVICE}  ${ATL_APP_DATA_MOUNT}  ${TYPE}  defaults,nofail  0  2" >>/etc/fstab
    mount -v "${ATL_APP_DATA_BLOCK_DEVICE}" >> "${ATL_LOG}" 2>&1

    # ZFS manages its network exports and therefore does not need an /etc/exports entry
    if [[ "x${ATL_APP_NFS_SERVER}" == "xtrue" ]]; then
        # Setup NFS export
        echo "${ATL_APP_DATA_MOUNT} *(rw,sync,no_root_squash)" >> /etc/exports

        exportfs -av >> "${ATL_LOG}" 2>&1
    fi
}

case "$1" in
    start)
        $1
        ;;
    stop)
        ;;
    *)
        echo "Usage: $0 {start}"
        RETVAL=1
esac
exit ${RETVAL}
