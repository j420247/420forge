#!/bin/bash
set -e

GIT_VERSION=${GIT_VERSION}

if [ -z ${GIT_VERSION} ]; then
    echo "Installing latest Git"
    sudo yum -y -q install git
else
    echo "Installing Git ${GIT_VERSION}"
    sudo yum -y -q list installed git-${GIT_VERSION} 2>/dev/null || sudo yum -y -q install git-${GIT_VERSION}
fi