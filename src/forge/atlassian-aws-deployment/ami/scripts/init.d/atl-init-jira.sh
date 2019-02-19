#!/bin/bash

set -e

. /etc/init.d/atl-functions

trap 'atl_error ${LINENO}' ERR

ATL_FACTORY_CONFIG=/etc/sysconfig/atl
ATL_USER_CONFIG=/etc/atl


[[ -r "${ATL_FACTORY_CONFIG}" ]] && . "${ATL_FACTORY_CONFIG}"
[[ -r "${ATL_USER_CONFIG}" ]] && . "${ATL_USER_CONFIG}"


ATL_LOG=${ATL_LOG:?"The Atlassian log location must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_APP_DATA_MOUNT=${ATL_APP_DATA_MOUNT:?"The application data mount name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_INSTANCE_STORE_MOUNT=${ATL_INSTANCE_STORE_MOUNT:?"The instance store mount must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_HOST_NAME=$(atl_hostName)

ATL_JIRA_NAME=${ATL_JIRA_NAME:?"The JIRA name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_SHORT_DISPLAY_NAME=${ATL_JIRA_SHORT_DISPLAY_NAME:?"The ${ATL_JIRA_NAME} short display name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_FULL_DISPLAY_NAME=${ATL_JIRA_FULL_DISPLAY_NAME:?"The ${ATL_JIRA_SHORT_DISPLAY_NAME} short display name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_DB_NAME=${ATL_DB_NAME:?"The ${ATL_JIRA_SHORT_DISPLAY_NAME} db name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_DB_USER=${ATL_DB_USER:?"The ${ATL_JIRA_SHORT_DISPLAY_NAME} db user must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_INSTALL_DIR=${ATL_JIRA_INSTALL_DIR:?"The ${ATL_JIRA_SHORT_DISPLAY_NAME} install dir must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_HOME=${ATL_JIRA_HOME:?"The ${ATL_JIRA_SHORT_DISPLAY_NAME} home dir must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_JIRA_SHARED_HOME="${ATL_JIRA_HOME}/shared"
ATL_JIRA_SERVICE_NAME="jira"

ATL_JIRA_USER="jira" #you don't get to choose user name. Installer creates user 'jira' and that's it
if [ "${ATL_JIRA_NAME}" == "jira-all" ]; then
    ATL_JIRA_ALL="true"
    ATL_JIRA_NAME="jira-software"
    INSTALL_PRODUCT_LIST="jira-software servicedesk"
fi

ATL_JIRA_RELEASES_S3_URL="https://s3.amazonaws.com/${ATL_RELEASE_S3_BUCKET}/${ATL_RELEASE_S3_PATH}/${ATL_JIRA_NAME}"

function start {
    atl_log "=== BEGIN: service atl-init-jira start ==="
    atl_log "Initialising ${ATL_JIRA_FULL_DISPLAY_NAME}"

    installJIRA
    updateHostName "${ATL_PROXY_NAME}"
    configureJIRAHome
    installOBR
    exportCatalinaOpts
    configureJiraEnvironmentVariables
    atl_configureThreadHeapScripts
    if [[ -n "${ATL_DB_NAME}" ]]; then
        configureRemoteDb
    fi

    atl_log "=== BEGIN: service atl-init-jira runLocalAnsible ==="
    runLocalAnsible
    atl_log "=== END:   service atl-init-jira runLocalAnsible ==="

    atl_recursiveChown "root" "jira" "/etc/atl"

    if [ "${ATL_ENVIRONMENT}" != "prod" ]; then
        local baseURL="${ATL_TOMCAT_SCHEME}://${ATL_PROXY_NAME}${ATL_TOMCAT_CONTEXTPATH}"
        if updateBaseUrl ${baseURL} ${ATL_DB_HOST} ${ATL_DB_PORT} ${ATL_DB_NAME}; then echo "baseUrl updated";fi
    fi

    goJIRA

    atl_log "=== END:   service atl-init-jira start ==="
}

function updateBaseUrl {
  atl_log "=== BEGIN: Updating Server URL ==="
  local QUERY_RESULT=''
  local BASE_URL=$1
  local DB_HOST=$2
  local DB_PORT=$3
  local DB_NAME=$4
  set -f

  (su postgres -c "psql -w -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} -t --command \"update propertystring set propertyvalue = '${BASE_URL}' from propertyentry PE where PE.id=propertystring.id and PE.property_key = 'jira.baseurl';\"") >> "${ATL_LOG}" 2>&1

  atl_log "=== END: Server baseUrl update ==="
}

function exportCatalinaOpts() {
    atl_log "=== BEGIN: service exportCatalinaOpts ==="
    cat <<EOT | su "${ATL_JIRA_USER}" -c "tee -a \"/home/${ATL_JIRA_USER}/.bash_profile\"" > /dev/null 2>&1

if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi
export CATALINA_OPTS="${ATL_CATALINA_OPTS}"

EOT
    chmod 644 "/home/${ATL_JIRA_USER}/.bash_profile"
    chown ${ATL_JIRA_USER}:${ATL_JIRA_USER} /home/${ATL_JIRA_USER}/.bash_profile
    atl_log "=== END: service exportCatalinaOpts ==="
}

function configureJiraEnvironmentVariables (){
   atl_log "=== BEGIN: service configureJiraEnvironmentVariables ==="
   if [ -n "${ATL_JVM_HEAP}" ];then
       if [[ ! "${ATL_JVM_HEAP}" =~ ^.*[mMgG]$ ]]; then
           ATL_JVM_HEAP="${ATL_JVM_HEAP}m"
      fi
      su "${ATL_JIRA_USER}" -c "sed -i -r 's/^(JVM.+MEMORY=\")([0-9]+[mMgG])(.+)$/\1${ATL_JVM_HEAP}\3/' /opt/atlassian/jira/bin/setenv.sh" >> "${ATL_LOG}" 2>&1
   fi
   cat <<EOT | su "${ATL_JIRA_USER}" -c "tee -a \"${ATL_JIRA_INSTALL_DIR}/bin/setenv.sh\"" > /dev/null
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+UseG1GC"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+PrintAdaptiveSizePolicy"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+PrintGCDetails"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:NumberOfGCLogFiles=10"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:GCLogFileSize=5m"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+UseGCLogFileRotation"
CATALINA_OPTS="\${CATALINA_OPTS} -XX:+PrintTenuringDistribution"
CATALINA_OPTS="\${CATALINA_OPTS} -Dfile.encoding=UTF-8"
CATALINA_OPTS="\${CATALINA_OPTS} ${ATL_CATALINA_OPTS}"

export CATALINA_OPTS
EOT
   atl_log "=== END: service configureJiraEnvironmentVariables ==="
}

function createInstanceStoreDirs {
    atl_log "=== BEGIN: service atl-init-jira create-instance-store-dirs ==="
    atl_log "Initialising ${ATL_JIRA_FULL_DISPLAY_NAME}"

    local JIRA_DIR=${1:?"The instance store directory for ${ATL_JIRA_NAME} must be supplied"}

    if [[ ! -e "${JIRA_DIR}" ]]; then
        atl_log "Creating ${JIRA_DIR}"
        mkdir -p "${JIRA_DIR}" >> "${ATL_LOG}" 2>&1
    else
        atl_log "Not creating ${JIRA_DIR} because it already exists"
    fi
    atl_log "Creating ${JIRA_DIR}/caches"
    mkdir -p "${JIRA_DIR}/caches" >> "${ATL_LOG}" 2>&1
    atl_log "Creating ${JIRA_DIR}/tmp"
    mkdir -p "${JIRA_DIR}/tmp" >> "${ATL_LOG}" 2>&1

    atl_log "=== END:   service atl-init-jira create-instance-store-dirs ==="
}

function ownMount {
    if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}"; then
        atl_log "Setting ownership of ${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME} to '${ATL_JIRA_USER}' user"
        mkdir -p "${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}"
        chown -R "${ATL_JIRA_USER}":"${ATL_JIRA_USER}" "${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}"
    fi
}

function linkAppData {
    local LINK_DIR_NAME=${1:?"The name of the directory to link must be supplied"}
    if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}/${LINK_DIR_NAME}"; then
        atl_log "Linking ${ATL_JIRA_HOME}/${LINK_DIR_NAME} to ${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}/${LINK_DIR_NAME}"
        su "${ATL_JIRA_USER}" -c "mkdir -p \"${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}/${LINK_DIR_NAME}\""
        su "${ATL_JIRA_USER}" -c "ln -s \"${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}/${LINK_DIR_NAME}\" \"${ATL_JIRA_HOME}/${LINK_DIR_NAME}\"" >> "${ATL_LOG}" 2>&1
    fi
}

function initInstanceData {
    local LINK_DIR_NAME=${1:?"The name of the directory to mount must be supplied"}
    local INSTANCE_DIR="${ATL_INSTANCE_STORE_MOUNT}/${ATL_JIRA_SERVICE_NAME}/${LINK_DIR_NAME}"
    if [[ -d "${INSTANCE_DIR}" && $(( $(atl_freeSpace "${ATL_INSTANCE_STORE_MOUNT}") > 10485760 )) ]]; then
        atl_log "Linking ${ATL_JIRA_HOME}/${LINK_DIR_NAME} to ${INSTANCE_DIR}"
        su "${ATL_JIRA_USER}" -c "ln -s \"${INSTANCE_DIR}\" \"${ATL_JIRA_HOME}/${LINK_DIR_NAME}\"" >> "${ATL_LOG}" 2>&1
    fi
}

function configureSharedHome {
    local JIRA_SHARED="${ATL_APP_DATA_MOUNT}/${ATL_JIRA_SERVICE_NAME}/shared"
    if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${JIRA_SHARED}"; then
        mkdir -p "${JIRA_SHARED}"
        touch "${JIRA_SHARED}/init"
        chown -H "${ATL_JIRA_USER}":"${ATL_JIRA_USER}" "${JIRA_SHARED}" >> "${ATL_LOG}" 2>&1
        if ! chown -H "${ATL_JIRA_USER}":"${ATL_JIRA_USER}" ${JIRA_SHARED}/* >> "${ATL_LOG}" 2>&1; then
            atl_log "Chown on contents of shared home failed most likley because this is a new cluster and no contents yet exist, moving on"
        fi

        atl_resolveHostNamesAndIps > /dev/null 2>&1

        cat <<EOT | su "${ATL_JIRA_USER}" -c "tee -a \"${ATL_JIRA_HOME}/cluster.properties\"" > /dev/null
jira.node.id = $(curl -f --silent http://169.254.169.254/latest/meta-data/instance-id):${_ATL_PRIVATE_IPV4}
jira.shared.home = ${JIRA_SHARED}
EOT
    else
        atl_log "No mountpoint for shared home exists. Failed to create cluster.properties file."
    fi
}

function configureJIRAHome {
    atl_log "Configuring ${ATL_JIRA_HOME}"
    mkdir -p "${ATL_JIRA_HOME}" >> "${ATL_LOG}" 2>&1

    configureSharedHome

    initInstanceData "caches"
    initInstanceData "tmp"

    atl_log "Setting ownership of ${ATL_JIRA_HOME} to '${ATL_JIRA_USER}' user"
    chown -R -H "${ATL_JIRA_USER}":"${ATL_JIRA_USER}" "${ATL_JIRA_HOME}" >> "${ATL_LOG}" 2>&1
    # if jira-config.properties exists at /media/atl/jira/shared/ then copy it to /var/atlassian/application-data/jira
    if [ -e /media/atl/jira/shared/jira-config.properties ]; then
        if cp /media/atl/jira/shared/jira-config.properties /var/atlassian/application-data/jira/jira-config.properties; then
            atl_log "copied /media/atl/jira/shared/jira-config.properties to /var/atlassian/application-data/jira/jira-config.properties"
        fi
        chown -h jira:jira /var/atlassian/application-data/jira/jira-config.properties
    fi
    atl_log "Done configuring ${ATL_JIRA_HOME}"
}

function configureDbProperties {
    atl_log "Configuring ${ATL_JIRA_SHORT_DISPLAY_NAME} DB settings"
    cat <<EOT | su "${ATL_JIRA_USER}" -c "tee -a \"${ATL_JIRA_HOME}/dbconfig.xml\"" > /dev/null
<?xml version="1.0" encoding="UTF-8"?>

<jira-database-config>
  <name>defaultDS</name>
  <delegator-name>default</delegator-name>
  <database-type>postgres72</database-type>
  <schema-name>public</schema-name>
  <jdbc-datasource>
    <url>$2</url>
    <driver-class>$1</driver-class>
    <username>$3</username>
    <password>$4</password>
    <pool-min-size>${ATL_DB_POOLMINSIZE}</pool-min-size>
    <pool-max-size>${ATL_DB_POOLMAXSIZE}</pool-max-size>
    <pool-max-wait>${ATL_DB_MAXWAITMILLIS}</pool-max-wait>
    <validation-query>select version();</validation-query>
    <min-evictable-idle-time-millis>${ATL_DB_MINEVICTABLEIDLETIMEMILLIS}</min-evictable-idle-time-millis>
    <time-between-eviction-runs-millis>${ATL_DB_TIMEBETWEENEVICTIONRUNSMILLIS}</time-between-eviction-runs-millis>
    <pool-max-idle>${ATL_DB_MAXIDLE}</pool-max-idle>
    <pool-min-idle>${ATL_DB_MINIDLE}</pool-min-idle>
    <pool-remove-abandoned>${ATL_DB_REMOVEABANDONED}</pool-remove-abandoned>
    <pool-remove-abandoned-timeout>${ATL_DB_REMOVEABANDONEDTIMEOUT}</pool-remove-abandoned-timeout>
    <pool-test-on-borrow>${ATL_DB_TESTONBORROW}</pool-test-on-borrow>
    <pool-test-while-idle>${ATL_DB_TESTWHILEIDLE}</pool-test-while-idle>
  </jdbc-datasource>
</jira-database-config>
EOT
    su "${ATL_JIRA_USER}" -c "chmod 600 \"${ATL_JIRA_HOME}/dbconfig.xml\"" >> "${ATL_LOG}" 2>&1
    atl_log "Done configuring ${ATL_JIRA_SHORT_DISPLAY_NAME} to use the ${ATL_JIRA_SHORT_DISPLAY_NAME} DB role ${ATL_JIRA_DB_USER}"
}

function configureRemoteDb {
    atl_log "Configuring remote DB for use with ${ATL_JIRA_SHORT_DISPLAY_NAME}"

    if [[ -n "${ATL_DB_PASSWORD}" ]]; then
        atl_configureDbPassword "${ATL_DB_PASSWORD}" "*" "${ATL_DB_HOST}" "${ATL_DB_PORT}"

        if atl_roleExists ${ATL_JDBC_USER} "postgres" ${ATL_DB_HOST} ${ATL_DB_PORT}; then
            atl_log "${ATL_JDBC_USER} role already exists. Skipping role creation."
            atl_log "Setting password for ${ATL_JDBC_USER}."
            atl_configureDbUserPassword "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}" "${ATL_DB_HOST}" "${ATL_DB_PORT}"
        else
            atl_createRole "${ATL_JIRA_SHORT_DISPLAY_NAME}" "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}" "${ATL_DB_HOST}" "${ATL_DB_PORT}"
            atl_createRemoteDb "${ATL_JIRA_SHORT_DISPLAY_NAME}" "${ATL_DB_NAME}" "${ATL_JDBC_USER}" "${ATL_DB_HOST}" "${ATL_DB_PORT}" "C" "C" "template0"
        fi

        configureDbProperties "${ATL_JDBC_DRIVER}" "${ATL_JDBC_URL}" "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}"
    fi
}

function preserveInstaller {
    local ATL_LOG_HEADER="[preserveInstaller]:"

    local JIRA_VERSION=$(cat $(atl_tempDir)/version)
    local JIRA_INSTALLER="atlassian-${ATL_JIRA_NAME}-${JIRA_VERSION}-x64.bin"

    atl_log "${ATL_LOG_HEADER} preserving ${ATL_JIRA_SHORT_DISPLAY_NAME} installer ${JIRA_INSTALLER} and metadata"
    cp $(atl_tempDir)/installer $ATL_APP_DATA_MOUNT/$JIRA_INSTALLER
    cp $(atl_tempDir)/version $ATL_APP_DATA_MOUNT/$ATL_JIRA_NAME.version
    atl_log "${ATL_LOG_HEADER} ${ATL_JIRA_SHORT_DISPLAY_NAME} installer ${JIRA_INSTALLER} and metadata has been preserved"
}

function restoreInstaller {
    local ATL_LOG_HEADER="[restoreInstaller]:"

    local JIRA_VERSION=$(cat $ATL_APP_DATA_MOUNT/$ATL_JIRA_NAME.version)
    local JIRA_INSTALLER="atlassian-${ATL_JIRA_NAME}-${JIRA_VERSION}-x64.bin"
    atl_log "${ATL_LOG_HEADER} Using existing installer ${JIRA_INSTALLER} from ${ATL_APP_DATA_MOUNT} mount"

    atl_log "${ATL_LOG_HEADER} Ready to restore ${ATL_JIRA_SHORT_DISPLAY_NAME} installer ${JIRA_INSTALLER}"

    if [[ -f $ATL_APP_DATA_MOUNT/$JIRA_INSTALLER ]]; then
        cp $ATL_APP_DATA_MOUNT/$JIRA_INSTALLER $(atl_tempDir)/installer
    else
        local msg="${ATL_LOG_HEADER} ${ATL_JIRA_SHORT_DISPLAY_NAME} installer $JIRA_INSTALLER has been requested, but unable to locate it in shared mount directory"
        atl_log "${msg}"
        atl_fatal_error "${msg}"
    fi

    atl_log "${ATL_LOG_HEADER} Restoration of ${ATL_JIRA_SHORT_DISPLAY_NAME} installer ${JIRA_INSTALLER} completed"
}

function downloadInstaller {
    local ATL_LOG_HEADER="[downloadInstaller]: "

    local VERSION_FILE_URL="https://marketplace.atlassian.com/rest/2/applications/jira/versions/latest"

    atl_log "${ATL_LOG_HEADER} Downloading installer description from ${VERSION_FILE_URL}"
    local JIRA_VERSION=$(curl --silent "${VERSION_FILE_URL}" | jq -r '.version')
    echo "${JIRA_VERSION}" > $(atl_tempDir)/version

    if [ -z "$JIRA_VERSION" ]
    then
        local ERROR_MESSAGE="Could not download installer description from ${VERSION_FILE_URL} - aborting installation"
        atl_log "${ATL_LOG_HEADER} ${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
    fi

    local JIRA_VERSION=$(cat $(atl_tempDir)/version)
    # if a jira version was passed on the cloudformation template, use that instead
    if [[ -n $requestedVersion ]] && [ $requestedVersion != "latest" ]; then
      echo $requestedVersion > $(atl_tempDir)/version
      local JIRA_VERSION=$requestedVersion
    fi
    local JIRA_INSTALLER="atlassian-${ATL_JIRA_NAME}-${JIRA_VERSION}-x64.bin"
    local JIRA_INSTALLER_URL="${ATL_JIRA_RELEASES_S3_URL}/${JIRA_INSTALLER}"
    # if a jira download_url was passed on the cloudformation template, use that instead
    if [[ -n $ATL_JIRA_INSTALLER_DOWNLOAD_URL ]]; then
      local JIRA_INSTALLER_URL=$ATL_JIRA_INSTALLER_DOWNLOAD_URL
    fi

    atl_log "${ATL_LOG_HEADER} Downloading ${ATL_JIRA_SHORT_DISPLAY_NAME} installer ${JIRA_INSTALLER} from ${ATL_JIRA_RELEASES_S3_URL}"
    if ! curl -L -f --silent "${JIRA_INSTALLER_URL}" \
        -o "$(atl_tempDir)/installer" >> "${ATL_LOG}" 2>&1
    then
        local ERROR_MESSAGE="Could not download ${ATL_JIRA_SHORT_DISPLAY_NAME} installer from ${ATL_JIRA_RELEASES_S3_URL} - aborting installation"
        atl_log "${ATL_LOG_HEADER} ${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
    fi
}

function prepareInstaller {
    local ATL_LOG_HEADER="[prepareInstaller]: "
    atl_log "${ATL_LOG_HEADER} Preparing an installer"

    atl_log "${ATL_LOG_HEADER} Checking if installer has been downloaded already"
    if [[ -f $ATL_APP_DATA_MOUNT/$ATL_JIRA_NAME.version ]]; then
        restoreInstaller
    else
        downloadInstaller
        preserveInstaller
    fi

    chmod +x "$(atl_tempDir)/installer" >> "${ATL_LOG}" 2>&1

    atl_log "${ATL_LOG_HEADER} Preparing installer configuration"

    cat <<EOT >> "$(atl_tempDir)/installer.varfile"
launch.application\$Boolean=false
rmiPort\$Long=8005
app.jiraHome=${ATL_JIRA_HOME}
app.install.service\$Boolean=true
existingInstallationDir=${ATL_JIRA_INSTALL_DIR}
sys.confirmedUpdateInstallationString=false
sys.languageId=en
sys.installationDir=${ATL_JIRA_INSTALL_DIR}
executeLauncherAction\$Boolean=true
httpPort\$Long=8080
portChoice=default
executeLauncherAction\$Boolean=false
EOT

    cp $(atl_tempDir)/installer.varfile /tmp/installer.varfile.bkp

    atl_log "${ATL_LOG_HEADER} Installer configuration preparation completed"
}

function cleanupJIRA {
    # cleanup pre-existing Jira
    if rm -rf /opt/atlassian/jira ; then echo "install cleaned up"; fi
    if userdel jira ; then echo "user cleaned up"; fi
    if groupdel jira ; then echo "group cleaned up"; fi
    if rm /media/atl/atlassian-jira-core-*.bin ; then echo "installer cleaned up"; fi
    if rm /media/atl/jira-core.version /var/atlassian/application-data/jira/cluster.properties /var/atlassian/application-data/jira/dbconfig.xml ; then echo "config cleaned up"; fi
}

function installJIRA {
    atl_log "Checking if the jira version requested is newer than one currently installed (ie if this is an upgrade)"
    requestedVersion=${ATL_JIRA_VERSION}
    # note for override versions we are ignoring the release type component (ie m00001) of the installer intentionally
    if [[ -n $ATL_JIRA_INSTALLER_DOWNLOAD_URL ]]; then
      overrideVersion=$(sed -rn 's/ATL_JIRA_INSTALLER_DOWNLOAD_URL.+atlassian-jira-\w+-([0-9]\.[0-9]\.[0-9])-.*x64.bin/\1/p' /etc/atl)
    fi
    # overrideVersion always wins out over requestedVersion
    if [[ -n $overrideVersion ]]; then requestedVersion=$overrideVersion; fi
    lastVersionFile=$(ls -tr1 /media/atl/*.version |tail -1)
    if [[ -n $lastVersionFile ]]; then currentVersion="$(cat $lastVersionFile 2>/dev/null)"; fi
    if [[ -n $currentVersion ]] && [[ -n $requestedVersion ]] ; then
      # abend if requested version is older than current
      if [[ $(echo -e "$currentVersion\n$requestedVersion"|sort -V|head -1) != $currentVersion ]]; then
        local ERROR_MESSAGE="requested jira version ($requestedVersion) is older than the one already installed ($currentVersion) - aborting installation"
        atl_log "${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
      fi
      # remove version file to allow new version download/deploy
      rm $lastVersionFile
      # else ensure the node is cleaned up ready for fresh install of newer release
      atl_log "Confirming this IS an upgrade ! - if requestedVersion is not 'latest' then clean up the environment"
      if [[ $requestedVersion != "latest" ]]; then
        export requestedVersion
        cleanupJIRA
      fi
    fi

    atl_log "Checking if ${ATL_JIRA_SHORT_DISPLAY_NAME} has already been installed"
    if [[ -d "${ATL_JIRA_INSTALL_DIR}" ]]; then
        local ERROR_MESSAGE="${ATL_JIRA_SHORT_DISPLAY_NAME} install directory ${ATL_JIRA_INSTALL_DIR} already exists - aborting installation"
        atl_log "${ERROR_MESSAGE}"
        atl_fatal_error "${ERROR_MESSAGE}"
    fi

    prepareInstaller

    atl_log "Creating ${ATL_JIRA_SHORT_DISPLAY_NAME} install directory"
    mkdir -p "${ATL_JIRA_INSTALL_DIR}"

    atl_log "Installing ${ATL_JIRA_SHORT_DISPLAY_NAME} to ${ATL_JIRA_INSTALL_DIR}"
    "$(atl_tempDir)/installer" -q -varfile "$(atl_tempDir)/installer.varfile" >> "${ATL_LOG}" 2>&1
    atl_log "Installed ${ATL_JIRA_SHORT_DISPLAY_NAME} to ${ATL_JIRA_INSTALL_DIR}"

    atl_log "Cleaning up"
    rm -rf "$(atl_tempDir)"/installer* >> "${ATL_LOG}" 2>&1

    chown -R "${ATL_JIRA_USER}":"${ATL_JIRA_USER}" "${ATL_JIRA_INSTALL_DIR}"

    atl_log "${ATL_JIRA_SHORT_DISPLAY_NAME} installation completed"
}

function installOBR {
    if [[ "${ATL_JIRA_ALL}" == "true" ]]; then # retrieve and drop OBR for JSD into /media/atl/jira/shared/plugins
        JIRA_VERSION=$(cat /media/atl/${ATL_JIRA_NAME}.version)
        PLUGIN_DIR="/media/atl/jira/shared/plugins/installed-plugins"
        atl_log "Fetching and Installing JSD OBR for Jira ${JIRA_VERSION}"
        MPLACE_URL=$(curl -s https://marketplace.atlassian.com/apps/1213632/jira-service-desk/version-history | tr '><"' '\n' |egrep -e 'Jira Server|download/apps'|sed '$!N;s/\n/ /'|grep $JIRA_VERSION |  awk '{print $NF}')
        MPLACE_FILE=''
        if [[ -n $MPLACE_URL ]]; then
            MPLACE_REDIRECT_URL=$(curl -Ls $MPLACE_URL -o /dev/null -w %{url_effective})
            MPLACE_FILE=$(basename $MPLACE_REDIRECT_URL)
            ZIP_FILENAME=$MPLACE_FILE
            # if obr doesnt exist on efs, try to fetch it first from marketplace
            if [ ! -f /media/atl/${MPLACE_FILE} ]; then
                atl_log "OBR doesnt exist on EFS, trying to fetch it first from marketplace"
                curl -s $MPLACE_REDIRECT_URL -o /media/atl/${MPLACE_FILE}
            fi
        fi
        # if obr still doesnt exist on efs, try to fetch it from downloads-internal
        if [ ! -f /media/atl/${MPLACE_FILE} ]; then
            atl_log "Unable to retrieve OBR from marketplace, trying to fetch it from downloads-internal S3 bucket"
            INTERNAL_JSD_OBR_NAME=$(aws s3 ls s3://downloads-internal-us-east-1/private/jira/${JIRA_VERSION}/|grep jira-servicedesk-application|grep obr|awk '{print $4}')
            INTERNAL_OBR_S3_LOCATION="s3://downloads-internal-us-east-1/private/jira/${JIRA_VERSION}/${INTERNAL_JSD_OBR_NAME}"
            aws s3 cp ${INTERNAL_OBR_S3_LOCATION} /media/atl/${INTERNAL_JSD_OBR_NAME}
            ZIP_FILENAME=$INTERNAL_JSD_OBR_NAME
        fi
        if [ -e /media/atl/${ZIP_FILENAME} ]; then atl_log "Retrieved JSD OBR ${ZIP_FILENAME} for Jira ${JIRA_VERSION}"; fi
        if ! mkdir -p ${PLUGIN_DIR};then echo "plugins dir already exists"; fi
        if ! chown -R jira:jira /media/atl/jira/shared/plugins; then echo "chown of plugins failed"; fi
        # and unpack the JARS to /media/atl/jira/shared/plugins/installed-plugins
        cd /media/atl/jira/shared/plugins/installed-plugins
        unzip -nj /media/atl/${ZIP_FILENAME} '*.jar'
    fi
}

function noJIRA {
    atl_log "Stopping ${ATL_JIRA_SERVICE_NAME} service"
    service "${ATL_JIRA_SERVICE_NAME}" stop >> "${ATL_LOG}" 2>&1
}

function goJIRA {
    atl_log "Starting ${ATL_JIRA_SERVICE_NAME} service"
    service "${ATL_JIRA_SERVICE_NAME}" start >> "${ATL_LOG}" 2>&1
}

function updateHostName {
    atl_configureTomcatConnector "${1}" "8080" "8081" "${ATL_JIRA_USER}" \
        "${ATL_JIRA_INSTALL_DIR}/conf" \
        "${ATL_JIRA_INSTALL_DIR}/atlassian-jira/WEB-INF"

    STATUS="$(service "${ATL_JIRA_SERVICE_NAME}" status || true)"
    if [[ "${STATUS}" =~ .*\ is\ running ]]; then
        atl_log "Restarting ${ATL_JIRA_SHORT_DISPLAY_NAME} to pick up host name change"
        noJIRA
        goJIRA
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
    stop)
        ;;
    *)
        echo "Usage: $0 {start|init-instance-store-dirs|update-host-name}"
        RETVAL=1
esac
exit ${RETVAL}
