#!/bin/bash
set -e

echo "Installing JQ"
sudo yum -y -q list installed jq > /dev/null 2>&1 || sudo yum -y -q install jq
