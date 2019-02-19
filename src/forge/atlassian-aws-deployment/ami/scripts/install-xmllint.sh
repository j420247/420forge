#!/bin/bash
set -e

echo "Installing XMLLint"
sudo yum -y -q list installed libxml2 > /dev/null 2>&1 || sudo yum -y -q install libxml2
