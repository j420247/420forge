#!/bin/bash
set -e

INIT_SCRIPT=${INIT_SCRIPT:?"The init.d script must be supplied"}

FILENAME="$(basename ${INIT_SCRIPT})"
SERVICE_NAME="${FILENAME%.*}"

echo "Creating init.d service /etc/init.d/${SERVICE_NAME}"
sudo mv "${INIT_SCRIPT}" "/etc/init.d/${SERVICE_NAME}"
sudo chmod 755 "/etc/init.d/${SERVICE_NAME}"
sudo chown root:root "/etc/init.d/${SERVICE_NAME}"
sudo chkconfig --add "${SERVICE_NAME}"
sudo chkconfig "${SERVICE_NAME}" on