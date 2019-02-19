#!/bin/bash
set -e

POSTGRES_VERSION=${POSTGRES_VERSION:?"The Postgres version must be supplied"}
INIT_SCRIPT=${INIT_SCRIPT:?"The init.d script must be supplied"}

POSTGRES_SHORT_VERSION=$(echo ${POSTGRES_VERSION} | sed -e 's/\.//g')
FILENAME="$(basename ${INIT_SCRIPT})"
SERVICE_NAME="${FILENAME%.*}"

echo "Creating init.d service /etc/init.d/${SERVICE_NAME}"
sed -i "s/%%POSTGRES_SHORT_VERSION%%/${POSTGRES_SHORT_VERSION}/g" "${INIT_SCRIPT}"
sudo mv "${INIT_SCRIPT}" "/etc/init.d/${SERVICE_NAME}"
sudo chmod 755 "/etc/init.d/${SERVICE_NAME}"
sudo chown root:root "/etc/init.d/${SERVICE_NAME}"
sudo chkconfig --add "${SERVICE_NAME}"
sudo chkconfig "${SERVICE_NAME}" on