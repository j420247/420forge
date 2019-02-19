#!/bin/bash
### BEGIN INIT INFO
# Provides:          atl-init-30-db
# Required-Start:    cloud-final atl-init-10-volume atl-init-20-instance-store
# Required-Stop:
# X-Start-Before:    postgresql%%POSTGRES_SHORT_VERSION%%
# Default-Start:     2 3 4 5
# Default-Stop:
# Short-Description: Ensures the Postgres db data dir has been created and initialised. It does not create any product-specific databases - that is performed by the product initialisation services.
# Description:       Ensures the Postgres db data dir has been created and initialised. It does not create any product-specific databases - that is performed by the product initialisation services.
### END INIT INFO

set -e

. /etc/init.d/atl-functions

trap 'atl_error ${LINENO}' ERR

ATL_FACTORY_CONFIG=/etc/sysconfig/atl
ATL_USER_CONFIG=/etc/atl

[[ -r "${ATL_FACTORY_CONFIG}" ]] && . "${ATL_FACTORY_CONFIG}"
[[ -r "${ATL_USER_CONFIG}" ]] && . "${ATL_USER_CONFIG}"

ATL_LOG=${ATL_LOG:?"The Atlassian log location must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_DATA_MOUNT=${ATL_APP_DATA_MOUNT:?"The application data mount must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_DATA_DIR=${ATL_APP_DATA_DIR:-"The application data dir must be supplied in ${ATL_FACTORY_CONFIG}"}

ATL_DB_DIR="${ATL_APP_DATA_DIR}/db"
ATL_DB_MOUNT="${ATL_APP_DATA_MOUNT}/db"

function start {
    atl_log "=== BEGIN: service atl-init-30-db start ==="
    atl_log "Initialising database"

    disableThisService
    if [[ "x${ATL_POSTGRES_ENABLED}" == "xtrue" ]]; then
        createDbDir
        initDbDir
        enablePostgres
        startPostgres
        configureDbPassword
    fi

    atl_log "=== END:   service atl-init-30-db start ==="
}

function disableThisService {
    atl_log "Disabling atl-init-30-db for future boots"
    chkconfig "atl-init-30-db" off >> "${ATL_LOG}" 2>&1
    atl_log "Done disabling atl-init-30-db for future boots"
}

function createDbDir {
    if [[ -e "${ATL_DB_DIR}" ]]; then
        local ERROR_MESSAGE="Error: ${ATL_DB_DIR} already exists - not initialising"
        atl_log "${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
    fi
        
    atl_log "Ensuring ${ATL_APP_DATA_DIR} exists"
    mkdir -p "${ATL_APP_DATA_DIR}" >> "${ATL_LOG}" 2>&1

    if grep -qs "${ATL_APP_DATA_MOUNT}" /proc/mounts; then
        atl_log "Atlassian application data mount ${ATL_APP_DATA_MOUNT} is present"

        if [[ ! -d "${ATL_DB_MOUNT}" ]]; then
            atl_log "Creating ${ATL_DB_MOUNT}"
            mkdir -p "${ATL_DB_MOUNT}" >> "${ATL_LOG}" 2>&1
            chmod 755 "${ATL_DB_MOUNT}" >> "${ATL_LOG}" 2>&1
            chown postgres:postgres "${ATL_DB_MOUNT}" >> "${ATL_LOG}" 2>&1
        fi

        atl_log "Linking ${ATL_DB_DIR} to ${ATL_DB_MOUNT}"
        ln -s "${ATL_DB_MOUNT}" "${ATL_DB_DIR}" >> "${ATL_LOG}" 2>&1
        chown -h postgres:postgres "${ATL_DB_DIR}" >> "${ATL_LOG}" 2>&1
    else
        atl_log "Atlassian application data mount ${ATL_APP_DATA_MOUNT} is not present. Creating ${ATL_DB_DIR} instead"
        mkdir -p "${ATL_DB_DIR}" >> "${ATL_LOG}" 2>&1
        chown postgres:postgres "${ATL_DB_DIR}" >> "${ATL_LOG}" 2>&1
    fi
}

function configureDbPassword {
    atl_log "Configuring postgres user database password"
    local PASSWORD=$(cat /proc/sys/kernel/random/uuid)
    su postgres -c "psql --command \"ALTER USER postgres password '${PASSWORD}'\"" >> "${ATL_LOG}" 2>&1
    atl_configureDbPassword "${PASSWORD}" "*"
}

function initDbDir {
    atl_log "Configuring Postgres to use directory ${ATL_DB_DIR} for data"
    cat <<EOT >> "/etc/sysconfig/pgsql/postgresql%%POSTGRES_SHORT_VERSION%%"
PGDATA=${ATL_DB_DIR}
EOT

    if [[ "$(ls -A ${ATL_DB_DIR}/)" ]]; then
        atl_log "${ATL_DB_DIR}/ is non-empty, skipping Postgres data initialisation"
    else
        atl_log "Initialising Postgres data in ${ATL_DB_DIR}"
        service postgresql%%POSTGRES_SHORT_VERSION%% initdb >> "${ATL_LOG}" 2>&1
        su postgres -c "sed -i -e 's/^[ \t]*#*[ \t]*\(hot_standby[ \t]*=[ \t]*\)[^ \t]*/\1on/' \
                               -e 's/^[ \t]*#*[ \t]*\(wal_level[ \t]*=[ \t]*\)[^ \t]*/\1hot_standby/' \
                        \"${ATL_DB_DIR}/postgresql.conf\"" >> "${ATL_LOG}" 2>&1
        su postgres -c "sed -i 's/^[^#]/#/' \"${ATL_DB_DIR}/pg_hba.conf\"" >> "${ATL_LOG}" 2>&1
        cat <<EOT >> "${ATL_DB_DIR}/pg_hba.conf"
#
# Added by atl-init-30-db at $(date)
local   all         all                               peer
host    all         all         127.0.0.1/32          md5
host    all         all         ::1/128               md5
EOT
        chown postgres:postgres "${ATL_DB_DIR}/pg_hba.conf" >> "${ATL_LOG}" 2>&1
    fi
}

function enablePostgres {
    atl_log "Enabling Postgres for configured run levels"
    chkconfig "postgresql%%POSTGRES_SHORT_VERSION%%" on >> "${ATL_LOG}" 2>&1
    atl_log "Done enabling Postgres for configured run levels"
}

function startPostgres {
    atl_log "Starting Postgres"
    while ! service "postgresql%%POSTGRES_SHORT_VERSION%%" start >> "${ATL_LOG}" 2>&1; do
        sleep 5
    done
    atl_log "Waiting for DB service to start"
    atl_waitForDbToStart >> "${ATL_LOG}" 2>&1
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
