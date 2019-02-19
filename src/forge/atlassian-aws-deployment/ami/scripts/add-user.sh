#!/bin/bash
set -e

USER=${USER:?"The username for the account must be supplied"}
USER_ID=${USER_ID:?"The ID for the account must be supplied"}
COMMENT=${COMMENT:?"The comment for the account must be supplied"}

echo "Adding user ${USER} with UID ${USER_ID}"
sudo adduser -c "${COMMENT}" -u "${USER_ID}" "${USER}"
