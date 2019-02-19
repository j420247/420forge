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

ATL_CROWD_NAME=${ATL_CROWD_NAME:?"The CROWD name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_CROWD_SHORT_DISPLAY_NAME=${ATL_CROWD_SHORT_DISPLAY_NAME:?"The ${ATL_CROWD_NAME} short display name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_CROWD_FULL_DISPLAY_NAME=${ATL_CROWD_FULL_DISPLAY_NAME:?"The ${ATL_CROWD_SHORT_DISPLAY_NAME} short display name must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_CROWD_INSTALL_DIR=${ATL_CROWD_INSTALL_DIR:?"The ${ATL_CROWD_SHORT_DISPLAY_NAME} install dir must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_CROWD_HOME=${ATL_CROWD_HOME:?"The ${ATL_CROWD_SHORT_DISPLAY_NAME} home dir must be supplied in ${ATL_FACTORY_CONFIG}"}
ATL_CROWD_SHARED_HOME="${ATL_CROWD_HOME}/shared"
ATL_CROWD_SERVICE_NAME="crowd"

ATL_CROWD_USER="crowd" #you don't get to choose user name. Installer creates user 'crowd' and that's it

ATL_CROWD_RELEASES_S3_URL="https://s3.amazonaws.com/downloads-public-us-east-1/software/${ATL_CROWD_NAME}/downloads/atlassian-${ATL_CROWD_NAME}-${ATL_CROWD_VERSION}.tar.gz"

function start {
  atl_log "=== BEGIN: service atl-init-crowd start ==="
  atl_log "Initialising ${ATL_CROWD_FULL_DISPLAY_NAME}"

  installCrowd
  if [[ -n "${ATL_PROXY_NAME}" ]]; then
    updateHostName "${ATL_PROXY_NAME}"
  fi
  configureCrowdHome
  exportCatalinaOpts
  configureCrowdEnvironmentVariables
  atl_configureThreadHeapScripts
  if [[ -n "${ATL_DB_NAME}" ]]; then
    configureRemoteDb
  fi
  configureCrowdContext
  atl_log "=== BEGIN: service atl-init-crowd runLocalAnsible ==="
  runLocalAnsible
  atl_log "=== END:   service atl-init-crowd runLocalAnsible ==="

  if [ "${ATL_ENVIRONMENT}" != "prod" ]; then
    local baseURL="${ATL_TOMCAT_SCHEME}://${ATL_PROXY_NAME}${ATL_TOMCAT_CONTEXTPATH}"
    if updateBaseUrl ${baseURL} ${ATL_DB_HOST} ${ATL_DB_PORT} ${ATL_DB_NAME}; then echo "baseUrl updated";fi
    if updateDBConfig; then echo "DB Config updated in crowd.cfg.xml";fi
  fi

  goCrowd

  atl_log "=== END:   service atl-init-crowd start ==="
}

function updateBaseUrl {
  atl_log "=== BEGIN: Updating Server URL ==="
  local BASE_URL=$1
  local DB_HOST=$2
  local DB_PORT=$3
  local DB_NAME=$4
  set -f

  (su postgres -c "psql -w -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} -t --command \"update cwd_property set property_value = '${BASE_URL}' where property_name='base.url' and property_key='crowd';\"") >> "${ATL_LOG}" 2>&1

  atl_log "=== END: Server baseUrl update ==="
}

function updateDBConfig {
  atl_log "=== BEGIN: crowd.cfg.xml DB update ==="
    xmlstarlet edit --inplace \
    --update '//application-configuration/properties/property[@name="hibernate.connection.password"]' \
    --value ${ATL_JDBC_PASSWORD} \
    --update '//application-configuration/properties/property[@name="hibernate.connection.url"]' \
    --value ${ATL_JDBC_URL} \
    --update '//application-configuration/properties/property[@name="hibernate.connection.username"]' \
    --value ${ATL_JDBC_USER} \
    /media/atl/crowd/shared/crowd.cfg.xml

  atl_log "=== END: crowd.cfg.xml DB update ==="
}

function exportCatalinaOpts() {
  atl_log "=== BEGIN: service exportCatalinaOpts ==="

  cat <<EOT | su "${ATL_CROWD_USER}" -c "tee -a \"/home/${ATL_CROWD_USER}/.bash_profile\"" > /dev/null 2>&1

if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi

export CATALINA_OPTS="${ATL_CATALINA_OPTS}"

EOT
  chmod 644 "/home/${ATL_CROWD_USER}/.bash_profile"
  chown ${ATL_CROWD_USER}:${ATL_CROWD_USER} /home/${ATL_CROWD_USER}/.bash_profile
  atl_log "=== END: service exportCatalinaOpts ==="
}

function configureCrowdEnvironmentVariables (){
  atl_log "=== BEGIN: service configureCrowdEnvironmentVariables ==="
   if [ -n "${ATL_JVM_HEAP}" ]; then
       if [[ ! "${ATL_JVM_HEAP}" =~ ^.*[mMgG]$ ]]; then
            ATL_JVM_HEAP="${ATL_JVM_HEAP}m"
       fi
       su "${ATL_CROWD_USER}" -c "sed -i -r 's/^(.*)Xmx(\w+) (.*)$/\1Xmx${ATL_JVM_HEAP} \3/' /opt/atlassian/crowd/apache-tomcat/bin/setenv.sh" >> "${ATL_LOG}" 2>&1
       su "${ATL_CROWD_USER}" -c "sed -i -r 's/^(.*)Xms(\w+) (.*)$/\1Xms${ATL_JVM_HEAP} \3/' /opt/atlassian/crowd/apache-tomcat/bin/setenv.sh" >> "${ATL_LOG}" 2>&1
   fi

  atl_resolveHostNamesAndIps > /dev/null 2>&1

  cat <<EOT | su "${ATL_CROWD_USER}" -c "tee -a \"${ATL_CROWD_INSTALL_DIR}/apache-tomcat/bin/setenv.sh\"" > /dev/null

CATALINA_OPTS="\${CATALINA_OPTS} -Dcluster.node.name=${_ATL_PRIVATE_IPV4}"
CATALINA_OPTS="\${CATALINA_OPTS} ${ATL_CATALINA_OPTS}"
export CATALINA_OPTS
EOT
  atl_log "=== END: service configureCrowdEnvironmentVariables ==="
}

function createInstanceStoreDirs {
  atl_log "=== BEGIN: service atl-init-crowd create-instance-store-dirs ==="
  atl_log "Initialising ${ATL_CROWD_FULL_DISPLAY_NAME}"

  local CROWD_DIR=${1:?"The instance store directory for ${ATL_CROWD_NAME} must be supplied"}

  if [[ ! -e "${CROWD_DIR}" ]]; then
    atl_log "Creating ${CROWD_DIR}"
    mkdir -p "${CROWD_DIR}" >> "${ATL_LOG}" 2>&1
  else
    atl_log "Not creating ${CROWD_DIR} because it already exists"
  fi
  atl_log "Creating ${CROWD_DIR}/caches"
  mkdir -p "${CROWD_DIR}/caches" >> "${ATL_LOG}" 2>&1
  atl_log "Creating ${CROWD_DIR}/tmp"
  mkdir -p "${CROWD_DIR}/tmp" >> "${ATL_LOG}" 2>&1

  atl_log "=== END:   service atl-init-crowd create-instance-store-dirs ==="
}

function ownMount {
  if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}"; then
    atl_log "Setting ownership of ${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME} to '${ATL_CROWD_USER}' user"
    mkdir -p "${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}"
    chown -R "${ATL_CROWD_USER}":"${ATL_CROWD_USER}" "${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}"
  fi
}

function linkAppData {
  local LINK_DIR_NAME=${1:?"The name of the directory to link must be supplied"}
  if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}/${LINK_DIR_NAME}"; then
    atl_log "Linking ${ATL_CROWD_HOME}/${LINK_DIR_NAME} to ${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}/${LINK_DIR_NAME}"
    su "${ATL_CROWD_USER}" -c "mkdir -p \"${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}/${LINK_DIR_NAME}\""
    su "${ATL_CROWD_USER}" -c "ln -s \"${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}/${LINK_DIR_NAME}\" \"${ATL_CROWD_HOME}/${LINK_DIR_NAME}\"" >> "${ATL_LOG}" 2>&1
  fi
}

function initInstanceData {
  local LINK_DIR_NAME=${1:?"The name of the directory to mount must be supplied"}
  local INSTANCE_DIR="${ATL_INSTANCE_STORE_MOUNT}/${ATL_CROWD_SERVICE_NAME}/${LINK_DIR_NAME}"
  if [[ -d "${INSTANCE_DIR}" && $(( $(atl_freeSpace "${ATL_INSTANCE_STORE_MOUNT}") > 10485760 )) ]]; then
    atl_log "Linking ${ATL_CROWD_HOME}/${LINK_DIR_NAME} to ${INSTANCE_DIR}"
    su "${ATL_CROWD_USER}" -c "ln -s \"${INSTANCE_DIR}\" \"${ATL_CROWD_HOME}/${LINK_DIR_NAME}\"" >> "${ATL_LOG}" 2>&1
  fi
}

function configureSharedHome {
  local CROWD_SHARED="${ATL_APP_DATA_MOUNT}/${ATL_CROWD_SERVICE_NAME}/shared"
  if mountpoint -q "${ATL_APP_DATA_MOUNT}" || mountpoint -q "${CROWD_SHARED}"; then
    mkdir -p "${CROWD_SHARED}"
    chown -R -H "${ATL_CROWD_USER}":"${ATL_CROWD_USER}" "${CROWD_SHARED}" >> "${ATL_LOG}" 2>&1
    ln -s "${CROWD_SHARED}" "${ATL_CROWD_SHARED_HOME}"
    cat <<EOT | su "${ATL_CROWD_USER}" -c "tee -a \"${ATL_CROWD_HOME}/cluster.properties\"" > /dev/null
crowd.node.id = $(curl -f --silent http://169.254.169.254/latest/meta-data/instance-id)
crowd.shared.home = ${CROWD_SHARED}
EOT
  else
    atl_log "No mountpoint for shared home exists. Failed to create cluster.properties file."
  fi
}

function configureCrowdHome {
  atl_log "Configuring ${ATL_CROWD_HOME}"
  mkdir -p "${ATL_CROWD_HOME}" >> "${ATL_LOG}" 2>&1

  atl_log "Setting ownership of ${ATL_CROWD_HOME} to '${ATL_CROWD_USER}' user"
  chown -R -H "${ATL_CROWD_USER}":"${ATL_CROWD_USER}" "${ATL_CROWD_HOME}" >> "${ATL_LOG}" 2>&1


  configureSharedHome

  initInstanceData "caches"
  initInstanceData "tmp"

  atl_log "Done configuring ${ATL_CROWD_HOME}"
}

function configureCrowdContext {
  if [[ ! -n "${ATL_TOMCAT_CONTEXTPATH}" ]]; then
    atl_log "Configuring Crowd's Context path"

    # context path is empty, need to remove /crowd
    cat <<EOT | su "${ATL_CROWD_USER}" -c "tee \"$(atl_tempDir)/server-context.xslt\"" >> "${ATL_LOG}" 2>&1
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output omit-xml-declaration="yes" indent="yes" method="html"/>

    <xsl:template match="@* | node()">
       <xsl:copy>
          <xsl:apply-templates select="@* | node()"/>
       </xsl:copy>
    </xsl:template>

    <xsl:template match="/Server/Service/Engine/Host">
      <xsl:copy select=".">
	      <xsl:copy-of select="@*"/>
      	  <Context path="${ATL_TOMCAT_CONTEXTPATH}" docBase="../../crowd-webapp" debug="0">
            <Manager pathname="${ATL_TOMCAT_CONTEXTPATH}" />
          </Context>
	    </xsl:copy>
    </xsl:template>
</xsl:stylesheet>
EOT

    local SERVER_TMP="$(atl_tempDir)/server-context.xml.tmp"
    local SERVER_XML="${ATL_CROWD_INSTALL_DIR}/apache-tomcat/conf/server.xml"
    set -C
    if  >"${SERVER_TMP}"; then
      set +C
      chown "${ATL_CROWD_USER}:${ATL_CROWD_USER}" "${SERVER_TMP}" >> "${ATL_LOG}" 2>&1
      atl_log "running xsltproc -o ${SERVER_TMP} $(atl_tempDir)/server-context.xslt ${SERVER_XML}"
      if su "${ATL_CROWD_USER}" -c "xsltproc -o \"${SERVER_TMP}\" \"$(atl_tempDir)/server-context.xslt\" \"${SERVER_XML}\""; then
        if mv -f "${SERVER_TMP}" "${SERVER_XML}" >> "${ATL_LOG}" 2>&1; then
          atl_log "Updated server.xml to remove context path"
        else
          atl_log "Updating ${SERVER_XML} failed"
        fi
      else
        atl_log "Updating server.xml failed. Skipping."
      fi
    else
      set +C
    fi
  fi
}

function configureRemoteDb {
  atl_log "Configuring remote DB for use with ${ATL_CROWD_SHORT_DISPLAY_NAME}"

  if [[ -n "${ATL_DB_PASSWORD}" ]]; then
    atl_configureDbPassword "${ATL_DB_PASSWORD}" "*" "${ATL_DB_HOST}" "${ATL_DB_PORT}"

    if atl_roleExists ${ATL_JDBC_USER} "postgres" ${ATL_DB_HOST} ${ATL_DB_PORT}; then
      atl_log "${ATL_JDBC_USER} role already exists. Skipping role creation."
    else
      atl_createRole "${ATL_CROWD_SHORT_DISPLAY_NAME}" "${ATL_JDBC_USER}" "${ATL_JDBC_PASSWORD}" "${ATL_DB_HOST}" "${ATL_DB_PORT}"
      if ! atl_dbExists "${ATL_DB_NAME}" "${ATL_DB_HOST}" "${ATL_DB_PORT}"; then
        atl_log "Creating Databse ${ATL_DB_NAME} on ${ATL_DB_HOST}"
        atl_createRemoteDb "${ATL_CROWD_SHORT_DISPLAY_NAME}" "${ATL_DB_NAME}" "${ATL_JDBC_USER}" "${ATL_DB_HOST}" "${ATL_DB_PORT}" "C" "C" "template0"
      else
        atl_log "Database exists, skipping creation"
      fi
    fi
  fi
}


function configureCrowdProperties {
  atl_log "Updating crowd-init.properties with crowd.home = ${ATL_CROWD_HOME}"
  cat <<EOT  > "${ATL_CROWD_INSTALL_DIR}/crowd-webapp/WEB-INF/classes/crowd-init.properties"
crowd.home = ${ATL_CROWD_HOME}
EOT
}

function downloadArchive {
  atl_log "[downloadArchive]: "
  # if ATL_CROWD_INSTALLER_DOWNLOAD_URL is empty, use ATL_CROWD_RELEASES_S3_URL
  # note that 'latest' doesn't work.
  if [ -z "${ATL_CROWD_INSTALLER_DOWNLOAD_URL}" ]; then
    ATL_CROWD_INSTALLER_DOWNLOAD_URL=${ATL_CROWD_RELEASES_S3_URL}
  fi

  if [[ -d "${ATL_CROWD_INSTALL_DIR}" ]]; then
    local ERROR_MESSAGE="${ATL_CROWD_SHORT_DISPLAY_NAME} install directory ${ATL_CROWD_INSTALL_DIR} already exists - aborting installation"
    atl_log "${ERROR_MESSAGE}"
    atl_fatal_error "${ERROR_MESSAGE}"
  fi

  atl_log "Downloading ${ATL_CROWD_SHORT_DISPLAY_NAME} ${ATL_CROWD_VERSION} from ${ATL_CROWD_INSTALLER_DOWNLOAD_URL}"
  if ! curl -L -f --silent "${ATL_CROWD_INSTALLER_DOWNLOAD_URL}" -o "$(atl_tempDir)/installer" >> "${ATL_LOG}" 2>&1
  then
    local ERROR_MESSAGE="Could not download installer from ${ATL_CROWD_INSTALLER_DOWNLOAD_URL} - aborting installation"
    atl_log "${ERROR_MESSAGE}"
    atl_fatal_error "${ERROR_MESSAGE}"
  fi
}

function installCrowd {
  atl_log "Checking if ${ATL_CROWD_SHORT_DISPLAY_NAME} has already been installed"

  downloadArchive


  atl_log "Creating ${ATL_CROWD_SHORT_DISPLAY_NAME} install directory"
  mkdir -p "${ATL_CROWD_INSTALL_DIR}"

  atl_log "Installing ${ATL_CROWD_SHORT_DISPLAY_NAME} to ${ATL_CROWD_INSTALL_DIR}"
  # this is where we do to do untar
  tar zxvf "$(atl_tempDir)/installer" -C "${ATL_CROWD_INSTALL_DIR}" --strip-components=1  >> "${ATL_LOG}" 2>&1
  #"$(atl_tempDir)/installer" -q -varfile "$(atl_tempDir)/installer.varfile" >> "${ATL_LOG}" 2>&1
  atl_log "Installed ${ATL_CROWD_SHORT_DISPLAY_NAME} to ${ATL_CROWD_INSTALL_DIR}"

  atl_log "Cleaning up"
  rm -rf "$(atl_tempDir)"/installer* >> "${ATL_LOG}" 2>&1

  atl_log "checking if crowd user exists"
  if ! id -u ${ATL_CROWD_USER} > /dev/null 2>&1
  then
    atl_log "crowd user not found, creating"
    adduser -c "Created by atl-init-crowd.sh" "${ATL_CROWD_USER}"
  fi
  chown -R "${ATL_CROWD_USER}":"${ATL_CROWD_USER}" "${ATL_CROWD_INSTALL_DIR}"
  configureCrowdProperties
  addInitScript

  atl_log "${ATL_CROWD_SHORT_DISPLAY_NAME} installation completed"
}

function addInitScript {
  atl_log "Adding init.d script for crowd"
  cat <<EOT > /etc/init.d/crowd
#!/bin/bash

# Crowd Linux service controller script
cd "/opt/atlassian/crowd"

case "\$1" in
    start)
        /sbin/runuser -m ${ATL_CROWD_USER} -c "export JAVA_HOME=/usr/lib/jvm/jre-1.8.0-openjdk.x86_64 && ./start_crowd.sh $@"
        ;;
    stop)
        /sbin/runuser -m ${ATL_CROWD_USER} -c "export JAVA_HOME=/usr/lib/jvm/jre-1.8.0-openjdk.x86_64 && ./stop_crowd.sh"
        ;;
    *)
        echo "Usage: /etc/init.d/crowd {start|stop}"
        exit 1
        ;;
esac
EOT
  chmod +x /etc/init.d/crowd

}

function configureNginx {
  updateHostName "${ATL_HOST_NAME}"
  atl_addNginxProductMapping "${ATL_CROWD_NGINX_PATH}" 8095
}

function noCrowd {
  atl_log "Stopping ${ATL_CROWD_SERVICE_NAME} service"
  /etc/init.d/"${ATL_CROWD_SERVICE_NAME}" stop >> "${ATL_LOG}" 2>&1
}

function goCrowd {
  atl_log "Starting ${ATL_CROWD_SERVICE_NAME} service"
  /etc/init.d/"${ATL_CROWD_SERVICE_NAME}" start >> "${ATL_LOG}" 2>&1
}

function updateHostName {
  atl_configureTomcatConnector "${1}" "8095" "8443" "${ATL_CROWD_USER}" \
    "${ATL_CROWD_INSTALL_DIR}/apache-tomcat/conf" \
    "${ATL_CROWD_INSTALL_DIR}/crowd-webapp/WEB-INF"

  STATUS="$(service "${ATL_CROWD_SERVICE_NAME}" status || true)"
  if [[ "${STATUS}" =~ .*\ is\ running ]]; then
    atl_log "Restarting ${ATL_CROWD_SHORT_DISPLAY_NAME} to pick up host name change"
    noCrowd
    goCrowd
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
