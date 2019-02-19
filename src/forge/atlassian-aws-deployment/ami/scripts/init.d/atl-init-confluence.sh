#!/bin/bash

set -e

. /etc/init.d/atl-functions
. /etc/init.d/atl-confluence-common

trap 'atl_error ${LINENO}' ERR

if [[ "x${ATL_CONFLUENCE_DATA_CENTER}" = "xtrue" ]]; then
    ATL_HAZELCAST_NETWORK_AWS_HOST_HEADER="${ATL_HAZELCAST_NETWORK_AWS_HOST_HEADER:-"ec2.${ATL_HAZELCAST_NETWORK_AWS_IAM_REGION}.amazonaws.com"}"
fi

# We are using ALB so Confluence will startup without Synchrony-Proxy and using Synchrony at port 8091 of LB
function start {
    atl_log "=== BEGIN: service atl-init-confluence start ==="
    atl_log "Initialising ${ATL_CONFLUENCE_FULL_DISPLAY_NAME}"

    installConfluence
    if [[ "xtrue" == "x$(atl_toLowerCase ${ATL_NGINX_ENABLED})" ]]; then
        configureNginx
    fi

    updateHostName "${ATL_PROXY_NAME}"
    configureConfluenceHome
    exportCatalinaOpts
    configureConfluenceEnvironmentVariables
    atl_configureThreadHeapScripts
    if [[ -n "${ATL_AUTOLOGIN_COOKIE_AGE}" ]]; then
        atl_autologinCookieAge "${ATL_CONFLUENCE_USER}" "${ATL_CONFLUENCE_INSTALL_DIR}/confluence/WEB-INF/classes/seraph-config.xml" "${ATL_AUTOLOGIN_COOKIE_AGE}"
    fi
    if [[ "x${ATL_POSTGRES_ENABLED}" == "xtrue" ]]; then
        createConfluenceDbAndRole
    elif [[ -n "${ATL_DB_NAME}" ]]; then
        configureRemoteDb
    fi

    atl_log "=== BEGIN: service atl-init-confluence runLocalAnsible ==="
    runLocalAnsible
    atl_log "=== END:   service atl-init-confluence runLocalAnsible ==="

    atl_recursiveChown "root" "confluence" "/etc/atl"

    if [ "${ATL_ENVIRONMENT}" != "prod" ]; then
        local baseURL="${ATL_TOMCAT_SCHEME}://${ATL_PROXY_NAME}${ATL_TOMCAT_CONTEXTPATH}"
        if updateBaseUrl ${baseURL} ${ATL_DB_HOST} ${ATL_DB_PORT} ${ATL_DB_NAME}; then echo "baseUrl updated";fi
    fi

    goCONF

    atl_log "=== END:   service atl-init-confluence start ==="
}

function updateBaseUrl {
  atl_log "=== BEGIN: Updating Server URL ==="
  local QUERY_RESULT=''
  local BASE_URL=$1
  local DB_HOST=$2
  local DB_PORT=$3
  local DB_NAME=$4
  set -f

  (su postgres -c "psql -w -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} -t --command \"update bandana set bandanavalue=regexp_replace(bandanavalue, '<baseUrl>.*</baseUrl>', '<baseUrl>${BASE_URL}</baseUrl>') where bandanacontext = '_GLOBAL' and bandanakey = 'atlassian.confluence.settings';\"") >> "${ATL_LOG}" 2>&1

  atl_log "=== END: Server baseUrl update ==="
}

function configureConfluenceEnvironmentVariables (){
   atl_log "=== BEGIN: service configureConfluenceEnvironmentVariables ==="
   if [ -n "${ATL_JVM_HEAP}" ]; then
       if [[ ! "${ATL_JVM_HEAP}" =~ ^.*[mMgG]$ ]]; then
            ATL_JVM_HEAP="${ATL_JVM_HEAP}m"
       fi
       su "${ATL_CONFLUENCE_USER}" -c "sed -i -r 's/^(.*)Xmx(\w+) (.*)$/\1Xmx${ATL_JVM_HEAP} \3/' /opt/atlassian/confluence/bin/setenv.sh" >> "${ATL_LOG}" 2>&1
       su "${ATL_CONFLUENCE_USER}" -c "sed -i -r 's/^(.*)Xms(\w+) (.*)$/\1Xms${ATL_JVM_HEAP} \3/' /opt/atlassian/confluence/bin/setenv.sh" >> "${ATL_LOG}" 2>&1
   fi

   atl_resolveHostNamesAndIps > /dev/null 2>&1

   cat <<EOT | su "${ATL_CONFLUENCE_USER}" -c "tee -a \"${ATL_CONFLUENCE_INSTALL_DIR}/bin/setenv.sh\"" > /dev/null
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+PrintAdaptiveSizePolicy"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+PrintGCDetails"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:NumberOfGCLogFiles=10"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:GCLogFileSize=5m"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+UseGCLogFileRotation"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+PrintTenuringDistribution"
CATALINA_OPTS="\${CATALINA_OPTS} -Dfile.encoding=UTF-8"
CATALINA_OPTS="\${CATALINA_OPTS} -Dconfluence.upgrade.recovery.file.enabled=false"
CATALINA_OPTS="\${CATALINA_OPTS} -Djava.net.preferIPv4Stack=true"
CATALINA_OPTS="\${CATALINA_OPTS} -Djira.executor.threadpool.size=16"
CATALINA_OPTS="\${CATALINA_OPTS} -Datlassian.event.thread_pool_configuration.queue_size=4096"
CATALINA_OPTS="\${CATALINA_OPTS} -Dshare.group.email.mapping=atlassian-all:atlassian-all@atlassian.com,atlassian-staff:atlassian-staff@atlassian.com"
CATALINA_OPTS="\${CATALINA_OPTS} -Dconfluence.cluster.hazelcast.max.no.heartbeat.seconds=60"
CATALINA_OPTS="\${CATALINA_OPTS} -Datlassian.plugins.enable.wait=300"
CATALINA_OPTS="\${CATALINA_OPTS} -Dconfluence.cluster.node.name=${_ATL_PRIVATE_IPV4}"
CATALINA_OPTS="\${CATALINA_OPTS} -Dsynchrony.service.url=${ATL_SYNCHRONY_SERVICE_URL} -Dsynchrony.proxy.enabled=false ${ATL_CATALINA_OPTS}"

export CATALINA_OPTS
EOT
   atl_log "=== END: service configureConfluenceEnvironmentVariables ==="
}

function createInstanceStoreDirs {
    atl_log "=== BEGIN: service atl-init-confluence create-instance-store-dirs ==="
    atl_log "Initialising ${ATL_CONFLUENCE_FULL_DISPLAY_NAME}"

    local CONFLUENCE_DIR=${1:?"The instance store directory for ${ATL_CONFLUENCE_NAME} must be supplied"}

    if [[ ! -e "${CONFLUENCE_DIR}" ]]; then
        atl_log "Creating ${CONFLUENCE_DIR}"
        mkdir -p "${CONFLUENCE_DIR}" >> "${ATL_LOG}" 2>&1
    else
        atl_log "Not creating ${CONFLUENCE_DIR} because it already exists"
    fi
    atl_log "Creating ${CONFLUENCE_DIR}/caches"
    mkdir -p "${CONFLUENCE_DIR}/caches" >> "${ATL_LOG}" 2>&1
    atl_log "Creating ${CONFLUENCE_DIR}/tmp"
    mkdir -p "${CONFLUENCE_DIR}/tmp" >> "${ATL_LOG}" 2>&1

    atl_log "Changing ownership of the contents of ${CONFLUENCE_DIR} to ${ATL_CONFLUENCE_USER}"
    chown -R "${ATL_CONFLUENCE_USER}":"${ATL_CONFLUENCE_USER}" "${CONFLUENCE_DIR}"

    atl_log "=== END:   service atl-init-confluence create-instance-store-dirs ==="
}

function configureSharedHome {
    atl_log "=== BEGIN: service atl-init-confluence configureSharedHome ==="
    local CONFLUENCE_SHARED="${ATL_APP_DATA_MOUNT}/${ATL_CONFLUENCE_SERVICE_NAME}/shared-home"
    if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${CONFLUENCE_SHARED}"; then
        atl_log "Linking ${CONFLUENCE_SHARED} to ${ATL_CONFLUENCE_SHARED_HOME}"
        mkdir -p "${CONFLUENCE_SHARED}"
        chown -H "${ATL_CONFLUENCE_USER}":"${ATL_CONFLUENCE_USER}" "${CONFLUENCE_SHARED}" >> "${ATL_LOG}" 2>&1
        if ! chown -H "${ATL_CONFLUENCE_USER}":"${ATL_CONFLUENCE_USER}" ${CONFLUENCE_SHARED}/* >> "${ATL_LOG}" 2>&1; then
            atl_log "Chown on contents of shared home failed most likley because this is a new cluster or instance and no contents yet exist, moving on"
        fi
        su "${ATL_CONFLUENCE_USER}" -c "ln -fs \"${CONFLUENCE_SHARED}\" \"${ATL_CONFLUENCE_SHARED_HOME}\"" >> "${ATL_LOG}" 2>&1
        if [[ "x${ATL_CONFLUENCE_DATA_CENTER}" != "xtrue" ]]; then
            mkdir -p "${CONFLUENCE_SHARED}"/{backups,attachments,imgEffects,thumbnails}
            su "${ATL_CONFLUENCE_USER}" -c "ln -fs \"${CONFLUENCE_SHARED}/backups\" \"${ATL_CONFLUENCE_HOME}\"" >> "${ATL_LOG}" 2>&1
            su "${ATL_CONFLUENCE_USER}" -c "ln -fs \"${CONFLUENCE_SHARED}/attachments\" \"${ATL_CONFLUENCE_HOME}\"" >> "${ATL_LOG}" 2>&1
            su "${ATL_CONFLUENCE_USER}" -c "ln -fs \"${CONFLUENCE_SHARED}/imgEffects\" \"${ATL_CONFLUENCE_HOME}\"" >> "${ATL_LOG}" 2>&1
            su "${ATL_CONFLUENCE_USER}" -c "ln -fs \"${CONFLUENCE_SHARED}/thumbnails\" \"${ATL_CONFLUENCE_HOME}\"" >> "${ATL_LOG}" 2>&1
        fi
    else
        atl_log "No mountpoint for shared home exists."
    fi
    atl_log "=== END:   service atl-init-confluence configureSharedHome ==="
}

function configureConfluenceHome {
    atl_log "Configuring ${ATL_CONFLUENCE_HOME}"
    mkdir -p "${ATL_CONFLUENCE_HOME}" >> "${ATL_LOG}" 2>&1
    configureSharedHome
    atl_log "Setting ownership of ${ATL_CONFLUENCE_HOME} to '${ATL_CONFLUENCE_USER}' user"
    chown -R -H "${ATL_CONFLUENCE_USER}":"${ATL_CONFLUENCE_USER}" "${ATL_CONFLUENCE_HOME}" >> "${ATL_LOG}" 2>&1
    atl_log "Done configuring ${ATL_CONFLUENCE_HOME}"
}

function configureDbProperties {

    local LOCAL_CFG_XML="${ATL_CONFLUENCE_HOME}/confluence.cfg.xml"
    local SHARED_CFG_XML="${ATL_APP_DATA_MOUNT}/${ATL_CONFLUENCE_SERVICE_NAME}/shared-home/confluence.cfg.xml"

    declare -A SERVER_PROPS=(
        ["hibernate.connection.driver_class"]="${ATL_JDBC_DRIVER}"
        ["hibernate.connection.url"]="${ATL_JDBC_URL}"
        ["hibernate.connection.password"]="${ATL_JDBC_PASSWORD}"
        ["hibernate.connection.username"]="${ATL_JDBC_USER}"
        ["hibernate.c3p0.max_size"]="${ATL_DB_POOLMAXSIZE}"
        ["hibernate.c3p0.min_size"]="${ATL_DB_POOLMINSIZE}"
        ["hibernate.c3p0.timeout"]="${ATL_DB_TIMEOUT}"
        ["hibernate.c3p0.idle_test_period"]="${ATL_DB_IDLETESTPERIOD}"
        ["hibernate.c3p0.max_statements"]="${ATL_DB_MAXSTATEMENTS}"
        ["hibernate.c3p0.validate"]="${ATL_DB_VALIDATE}"
        ["hibernate.c3p0.preferredTestQuery"]="select version();"
        ["hibernate.c3p0.acquire_increment"]="${ATL_DB_ACQUIREINCREMENT}"
        ["shared-home"]="${ATL_CONFLUENCE_SHARED_HOME}"
    )

    if [[ "x${ATL_CONFLUENCE_DATA_CENTER}" != "xtrue" ]] && [[ -f "${SHARED_CFG_XML}" ]] && grep "setupStep>complete" "${SHARED_CFG_XML}" >> "${ATL_LOG}" 2>&1; then
        # Confluence Server doesn't really use the shared-home config at all, but we want it to for resiliency/recovery in a cloud environment
        # Hence, if this run isn't for Data Center and we find a completed config in the shared-home, we'll grab it and update it with any new/updated values
        atl_log "Found complete Confluence Server config in shared-home; restoring configuration"
        su "${ATL_CONFLUENCE_USER}" -c "cp -fpv \"${SHARED_CFG_XML}\" \"${LOCAL_CFG_XML}\"" >> "${ATL_LOG}" 2>&1
        atl_log "Editing restored confluence.cfg.xml with updated configuration options"
        for PROP in "${!SERVER_PROPS[@]}"; do
            xmlstarlet edit --inplace --update "/confluence-configuration/properties/property[@name='${PROP}']" --value "${SERVER_PROPS[${PROP}]}" "${LOCAL_CFG_XML}"
        done
    else
        # Otherwise, consider this a "new install" and we'll create the configuration from scratch
        atl_log "Configuring ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} DB settings"
        local PRODUCT_CONFIG_NAME="confluence"
        local CONFLUENCE_SETUP_STEP="setupstart"
        local CONFLUENCE_SETUP_TYPE="custom"
        local CONFLUENCE_BUILD_NUMBER="0"
        cat <<EOT | su "${ATL_CONFLUENCE_USER}" -c "tee \"${LOCAL_CFG_XML}\"" > /dev/null
<?xml version="1.0" encoding="UTF-8"?>

<${PRODUCT_CONFIG_NAME}-configuration>
  <setupStep>${CONFLUENCE_SETUP_STEP}</setupStep>
  <setupType>${CONFLUENCE_SETUP_TYPE}</setupType>
  <buildNumber>${CONFLUENCE_BUILD_NUMBER}</buildNumber>
  <properties>
    <property name="confluence.database.choice">postgresql</property>
    <property name="confluence.database.connection.type">database-type-standard</property>
    <property name="hibernate.dialect">com.atlassian.confluence.impl.hibernate.dialect.PostgreSQLDialect</property>
    <property name="webwork.multipart.saveDir">\${localHome}/temp</property>
    <property name="attachments.dir">\${confluenceHome}/attachments</property>
EOT

        for PROP in "${!SERVER_PROPS[@]}"; do
            echo "    <property name=\"${PROP}\">${SERVER_PROPS[${PROP}]}</property>" | su "${ATL_CONFLUENCE_USER}" -c "tee -a \"${LOCAL_CFG_XML}\"" > /dev/null
        done

        if [[ "x${ATL_CONFLUENCE_DATA_CENTER}" = "xtrue" ]]; then
            cat <<EOT | su "${ATL_CONFLUENCE_USER}" -c "tee -a \"${LOCAL_CFG_XML}\"" > /dev/null
    <property name="confluence.cluster">true</property>
    <property name="confluence.cluster.home">${ATL_CONFLUENCE_SHARED_HOME}</property>
    <property name="confluence.cluster.aws.iam.role">${ATL_HAZELCAST_NETWORK_AWS_IAM_ROLE}</property>
    <property name="confluence.cluster.aws.region">${ATL_HAZELCAST_NETWORK_AWS_IAM_REGION}</property>
    <property name="confluence.cluster.aws.host.header">${ATL_HAZELCAST_NETWORK_AWS_HOST_HEADER}</property>
    <property name="confluence.cluster.aws.tag.key">${ATL_HAZELCAST_NETWORK_AWS_TAG_KEY}</property>
    <property name="confluence.cluster.aws.tag.value">${ATL_HAZELCAST_NETWORK_AWS_TAG_VALUE}</property>
    <property name="confluence.cluster.join.type">aws</property>
    <property name="confluence.cluster.name">${ATL_AWS_STACK_NAME}</property>
    <property name="confluence.cluster.ttl">1</property>
EOT
        fi
        cat <<EOT | su "${ATL_CONFLUENCE_USER}" -c "tee -a \"${LOCAL_CFG_XML}\"" > /dev/null
  </properties>
</${PRODUCT_CONFIG_NAME}-configuration>
EOT

        su "${ATL_CONFLUENCE_USER}" -c "chmod 600 \"${LOCAL_CFG_XML}\"" >> "${ATL_LOG}" 2>&1
        atl_log "Done configuring ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} to use the ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} DB role ${ATL_CONFLUENCE_DB_USER}"
    fi

    if [[ "x${ATL_CONFLUENCE_DATA_CENTER}" != "xtrue" ]]; then
        local WATCHER_SCRIPT="/opt/atlassian/bin/atl-start-confluence-server-config-filewatcher.sh"
        if [[ -x ${WATCHER_SCRIPT} ]]; then
            atl_log "Starting filewatcher to copy Confluence Server config to shared-home on-edit"
            WATCHED_FILE=${LOCAL_CFG_XML} FILE_DEST=${SHARED_CFG_XML} LOG_FILE=${ATL_LOG} ${WATCHER_SCRIPT} >> "${ATL_LOG}" 2>&1 &
        else
            atl_log "Script for monitoring Confluence Server configuration changes is not available; config will not persist"
        fi
    fi
}

function createConfluenceDbAndRole {
    if atl_roleExists ${ATL_CONFLUENCE_DB_USER}; then
        atl_log "${ATL_CONFLUENCE_DB_USER} role already exists. Skipping database and role creation. Skipping dbconfig.xml update"
    else
        local PASSWORD=$(cat /proc/sys/kernel/random/uuid)

        atl_createRole "${ATL_CONFLUENCE_SHORT_DISPLAY_NAME}" "${ATL_CONFLUENCE_DB_USER}" "${PASSWORD}"
        atl_createDb "${ATL_CONFLUENCE_SHORT_DISPLAY_NAME}" "${ATL_CONFLUENCE_DB_NAME}" "${ATL_CONFLUENCE_DB_USER}"
        configureDbProperties "org.postgresql.Driver" "jdbc:postgresql://localhost/${ATL_CONFLUENCE_DB_NAME}" "${ATL_CONFLUENCE_DB_USER}" "${PASSWORD}"
    fi
}

function configureRemoteDb {
    atl_log "Configuring remote DB for use with ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME}"

    if [[ -n "${ATL_DB_PASSWORD}" ]]; then
        atl_configureDbPassword "${ATL_DB_PASSWORD}" "*" "${ATL_DB_HOST}" "${ATL_DB_PORT}"

        if atl_roleExists ${ATL_JDBC_USER} "postgres" ${ATL_DB_HOST} ${ATL_DB_PORT}; then
            atl_log "${ATL_JDBC_USER} role already exists. Skipping role creation."
            atl_log "Setting password for ${ATL_JDBC_USER}."
            atl_configureDbUserPassword "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}" "${ATL_DB_HOST}" "${ATL_DB_PORT}"
        else
            atl_createRole "${ATL_CONFLUENCE_SHORT_DISPLAY_NAME}" "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}" "${ATL_DB_HOST}" "${ATL_DB_PORT}"
            atl_createRemoteDb "${ATL_CONFLUENCE_SHORT_DISPLAY_NAME}" "${ATL_DB_NAME}" "${ATL_JDBC_USER}" "${ATL_DB_HOST}" "${ATL_DB_PORT}" "C" "C" "template0"
        fi

        configureDbProperties "${ATL_JDBC_DRIVER}" "${ATL_JDBC_URL}" "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}"
    fi
}

function configureNginx {
    updateHostName "${ATL_HOST_NAME}"
    atl_addNginxProductMapping "${ATL_CONFLUENCE_NGINX_PATH}" 8080
}

function installConfluence {
    atl_log "Checking if ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} has already been installed"

    if [[ "${ATL_USE_COLLECTD}" = true && -e /etc/init.d/collectd ]]; then
        atl_log "Creating file /etc/ld.so.conf.d/confluence.conf"
        echo /usr/lib/jvm/jre-1.7.0-openjdk.x86_64/lib/amd64/server/ > /etc/ld.so.conf.d/confluence.conf
        sudo ldconfig
        if [[ $ATL_STARTCOLLECTD == "true" ]]; then
            service collectd restart
        fi
        atl_log "Creating file /etc/ld.so.conf.d/confluence.conf ==> done"
    fi

    if [[ -d "${ATL_CONFLUENCE_INSTALL_DIR}" ]]; then
        local ERROR_MESSAGE="${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} install directory ${ATL_CONFLUENCE_INSTALL_DIR} already exists - aborting installation"
        atl_log "${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
    fi

    atl_log "Downloading ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} ${ATL_CONFLUENCE_VERSION} from ${ATL_CONFLUENCE_INSTALLER_DOWNLOAD_URL}"
    if ! curl -L -f --silent "${ATL_CONFLUENCE_INSTALLER_DOWNLOAD_URL}" -o "$(atl_tempDir)/installer" >> "${ATL_LOG}" 2>&1; then
        local ERROR_MESSAGE="Could not download installer from ${ATL_CONFLUENCE_INSTALLER_DOWNLOAD_URL} - aborting installation"
        atl_log "${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
    fi
    chmod +x "$(atl_tempDir)/installer" >> "${ATL_LOG}" 2>&1
    cat <<EOT >> "$(atl_tempDir)/installer.varfile"
launch.application\$Boolean=false
rmiPort\$Long=8005
app.defaultHome=${ATL_CONFLUENCE_HOME}
app.install.service\$Boolean=true
existingInstallationDir=${ATL_CONFLUENCE_INSTALL_DIR}
sys.confirmedUpdateInstallationString=false
sys.languageId=en
sys.installationDir=${ATL_CONFLUENCE_INSTALL_DIR}
executeLauncherAction\$Boolean=true
httpPort\$Long=8080
portChoice=default
executeLauncherAction\$Boolean=false
EOT

    cp $(atl_tempDir)/installer.varfile /tmp/installer.varfile.bkp

    atl_log "Creating ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} install directory"
    mkdir -p "${ATL_CONFLUENCE_INSTALL_DIR}"

    atl_log "Installing ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} to ${ATL_CONFLUENCE_INSTALL_DIR}"
    "$(atl_tempDir)/installer" -q -varfile "$(atl_tempDir)/installer.varfile" >> "${ATL_LOG}" 2>&1
    atl_log "Installed ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} to ${ATL_CONFLUENCE_INSTALL_DIR}"

    atl_log "Cleaning up"
    rm -rf "$(atl_tempDir)"/installer* >> "${ATL_LOG}" 2>&1

    chown -R "${ATL_CONFLUENCE_USER}":"${ATL_CONFLUENCE_USER}" "${ATL_CONFLUENCE_INSTALL_DIR}"

    atl_log "${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} installation completed"
}

function noCONF {
    atl_log "Stopping ${ATL_CONFLUENCE_SERVICE_NAME} service"
    service "${ATL_CONFLUENCE_SERVICE_NAME}" stop >> "${ATL_LOG}" 2>&1
}

function goCONF {
    atl_log "Starting ${ATL_CONFLUENCE_SERVICE_NAME} service"
    service "${ATL_CONFLUENCE_SERVICE_NAME}" start >> "${ATL_LOG}" 2>&1
}

function updateHostName {
    atl_configureTomcatConnector "${1}" "8080" "8081" "${ATL_CONFLUENCE_USER}" \
        "${ATL_CONFLUENCE_INSTALL_DIR}/conf" \
        "${ATL_CONFLUENCE_INSTALL_DIR}/confluence/WEB-INF"

    STATUS="$(service "${ATL_CONFLUENCE_SERVICE_NAME}" status || true)"
    if [[ "${STATUS}" =~ .*\ is\ running ]]; then
        atl_log "Restarting ${ATL_CONFLUENCE_SHORT_DISPLAY_NAME} to pick up host name change"
        noCONF
        goCONF
    fi
}

case "$1" in
    start)
        $1
        ;;
    create-instance-store-dirs)
        createInstanceStoreDirs $2
        ;;
    update-host-name)
        updateHostName $2
        ;;
    *)
        echo "Usage: $0 {start|init-instance-store-dirs|update-host-name}"
        RETVAL=1
esac
exit ${RETVAL}
