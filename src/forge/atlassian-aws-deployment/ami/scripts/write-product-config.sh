#!/bin/bash
set -e


# Some parameters are optional as they can come from Cloud Formation template
#
# We try not to define a parameter twice (in a template and in an AMI)
# to avoid confusion
#
# Optional parameters marked with OPTIONAL comment
#
LOCATION=${LOCATION:?"The config location must be supplied"}
LOG=${LOG:?"The Atlassian log location must be supplied"}
VERSION=${VERSION-"latest"} #OPTIONAL
USER=${USER-""} #OPTIONAL
HOME=${HOME:?"The product home must be supplied"}
APP_DATA_BLOCK_DEVICE=${APP_DATA_BLOCK_DEVICE:?"The app data block device must be supplied"}
APP_DATA_MOUNT=${APP_DATA_MOUNT:?"The app data mount must be supplied"}
APP_DATA_FS_TYPE=${APP_DATA_FS_TYPE:?"The app data filesystem type must be suppled"}
APP_DATA_DIR=${APP_DATA_DIR:?"The app data mount must be supplied"}
NAME=${NAME:?"The product name must be supplied"}
SHORT_DISPLAY_NAME=${SHORT_DISPLAY_NAME-""} #OPTIONAL
FULL_DISPLAY_NAME=${FULL_DISPLAY_NAME-""} #OPTIONAL
DB_DIR=${DB_DIR-""} #OPTIONAL
DB_NAME=${DB_NAME-""} #OPTIONAL
DB_USER=${DB_USER-""} #OPTIONAL
INSTALL_DIR=${INSTALL_DIR:?"The product install dir must be supplied"}
INSTANCE_STORE_BLOCK_DEVICE=${INSTANCE_STORE_BLOCK_DEVICE:?"The instance store block device must be supplied"}
INSTANCE_STORE_MOUNT=${INSTANCE_STORE_MOUNT:?"The instance store mount must be supplied"}
RELEASE_S3_BUCKET=${RELEASE_S3_BUCKET-"atlassian-software"} #OPTIONAL
RELEASE_S3_PATH=${RELEASE_S3_PATH-""} #OPTIONAL

echo "Writing first boot environment variables to ${LOCATION}"
cat <<EOT | sudo tee "${LOCATION}" > /dev/null
# Created by the Atlassian AMI build process at $(date)
# This file defines the variables used to configure and initialise the Atlassian product in this AMI

# The location of the Atlassian log
ATL_LOG=${LOG}

# Set to false to disable format and mount of application data volume
ATL_APP_DATA_MOUNT_ENABLED=true
# The block device where app data is attached
ATL_APP_DATA_BLOCK_DEVICE=${APP_DATA_BLOCK_DEVICE}
# The mount location of the EBS volume where app data is stored
ATL_APP_DATA_MOUNT="${APP_DATA_MOUNT}"
# The location on the root volume where application data is stored
ATL_APP_DATA_DIR="${APP_DATA_DIR}"
# The default filesystem type for the application data volume
ATL_APP_DATA_FS_TYPE="${APP_DATA_FS_TYPE}"
# The block device for the machine's instance store
ATL_INSTANCE_STORE_BLOCK_DEVICE="${INSTANCE_STORE_BLOCK_DEVICE}"
# The location where the machine's instance store is located
ATL_INSTANCE_STORE_MOUNT="${INSTANCE_STORE_MOUNT}"
# Set to true to enable NFS export
ATL_APP_NFS_SERVER=false
# The s3 bucket where the Atlassian product installers are located
ATL_RELEASE_S3_BUCKET="${RELEASE_S3_BUCKET}"
# The path in the s3 bucket where the Atlassian product installers are located
ATL_RELEASE_S3_PATH="${RELEASE_S3_PATH}"
# The public or VPC-resolvable host name of the EC2 instance. Used in the self-signed certificate if generated and to
# tell the web containers the URL they should assume they are serving from
# If empty, defaults to the public host name of the EC2 instance if available, public IP address of the EC2 instance if available or else "localhost"
ATL_HOST_NAME=

# Set to false to disable PostgreSQL database creation
ATL_POSTGRES_ENABLED=true

# Set to false to disable NGINX setup and SSL self-certification
ATL_NGINX_ENABLED=true
# Set to true to enable SSL self-certification (ATL_NGINX_ENABLED must also be true)
ATL_SSL_SELF_CERT_ENABLED=false
ATL_SSL_SELF_CERT_COUNTRY=US
ATL_SSL_SELF_CERT_STATE=CA
ATL_SSL_SELF_CERT_LOCALE="San Francisco"
ATL_SSL_SELF_CERT_ORG="An Atlassian Customer"
ATL_SSL_SELF_CERT_ORG_UNIT="An Atlassian Customer's Team"
ATL_SSL_SELF_CERT_EMAIL_ADDRESS=sales@atlassian.com
ATL_SSL_SELF_CERT_PATH=/etc/nginx/ssl/self-ssl.crt
ATL_SSL_SELF_CERT_KEY_PATH=/etc/nginx/ssl/self-ssl.key
ATL_SSL_CERT_PATH=\${ATL_SSL_SELF_CERT_PATH}
ATL_SSL_CERT_KEY_PATH=\${ATL_SSL_SELF_CERT_KEY_PATH}

# Set to true to configure an external proxy with SSL
ATL_SSL_PROXY=false

# Comma-separated list of products to install
ATL_ENABLED_PRODUCTS=Bitbucket

# Comma-separated list of product shared home directories to create
ATL_ENABLED_SHARED_HOMES="\${ATL_ENABLED_PRODUCTS}"

# Bitbucket-specific config
ATL_BITBUCKET_NAME="${NAME}"
ATL_BITBUCKET_SHORT_DISPLAY_NAME="${SHORT_DISPLAY_NAME}"
ATL_BITBUCKET_FULL_DISPLAY_NAME="${FULL_DISPLAY_NAME}"
ATL_BITBUCKET_VERSION="${VERSION}"
ATL_BITBUCKET_USER="${USER}"
ATL_BITBUCKET_PROPERTIES=
ATL_BITBUCKET_DB_NAME="${DB_NAME}"
ATL_BITBUCKET_DB_USER="${DB_USER}"
ATL_BITBUCKET_INSTALL_DIR="${INSTALL_DIR}"
ATL_BITBUCKET_HOME="${HOME}"
ATL_BITBUCKET_NGINX_PATH=/
# Set to false to disable use of bundled Elasticsearch instance
ATL_BITBUCKET_BUNDLED_ELASTICSEARCH_ENABLED=true

# JIRA-specific config
ATL_JIRA_NAME="${NAME}"
ATL_JIRA_SHORT_DISPLAY_NAME="${SHORT_DISPLAY_NAME}"
ATL_JIRA_FULL_DISPLAY_NAME="${FULL_DISPLAY_NAME}"
ATL_JIRA_USER="${USER}"
ATL_JIRA_CONFIG_PROPERTIES=
ATL_JIRA_DB_NAME="${DB_NAME}"
ATL_JIRA_DB_USER="${DB_USER}"
ATL_JIRA_INSTALL_DIR="${INSTALL_DIR}"
ATL_JIRA_HOME="${HOME}"
ATL_JIRA_NGINX_PATH=/

# Confluence-specific config
ATL_CONFLUENCE_NAME="${NAME}"
ATL_CONFLUENCE_SHORT_DISPLAY_NAME="${SHORT_DISPLAY_NAME}"
ATL_CONFLUENCE_FULL_DISPLAY_NAME="${FULL_DISPLAY_NAME}"
ATL_CONFLUENCE_VERSION="${VERSION}"
ATL_CONFLUENCE_USER="${USER}"
ATL_CONFLUENCE_CONFIG_PROPERTIES=
ATL_CONFLUENCE_DB_NAME="${DB_NAME}"
ATL_CONFLUENCE_DB_USER="${DB_USER}"
ATL_CONFLUENCE_INSTALL_DIR="${INSTALL_DIR}"
ATL_CONFLUENCE_HOME="${HOME}"
ATL_CONFLUENCE_NGINX_PATH=/

# Crowd-specific config
ATL_CROWD_NAME="${NAME}"
ATL_CROWD_SHORT_DISPLAY_NAME="${SHORT_DISPLAY_NAME}"
ATL_CROWD_FULL_DISPLAY_NAME="${FULL_DISPLAY_NAME}"
ATL_CROWD_VERSION="${VERSION}"
ATL_CROWD_USER="${USER}"
ATL_CROWD_CONFIG_PROPERTIES=
ATL_CROWD_DB_NAME="${DB_NAME}"
ATL_CROWD_DB_USER="${DB_USER}"
ATL_CROWD_INSTALL_DIR="${INSTALL_DIR}"
ATL_CROWD_HOME="${HOME}"
ATL_CROWD_NGINX_PATH=/
EOT
