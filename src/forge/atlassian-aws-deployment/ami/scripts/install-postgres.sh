#!/bin/bash
set -e

VERSION=${VERSION:?"The Postgres version must be supplied"}

SHORT_VERSION=$(echo ${VERSION} | sed -e 's/\.//g')

echo "Installing Postgres ${VERSION}"
sudo yum -y -q list installed postgresql${SHORT_VERSION}-server > /dev/null 2>&1 || sudo yum -y -q install postgresql${SHORT_VERSION}-server