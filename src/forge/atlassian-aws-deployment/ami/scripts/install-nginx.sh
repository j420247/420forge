#!/bin/bash
set -e

echo "Installing NGINX"
sudo yum -y -q list installed nginx > /dev/null 2>&1 || sudo yum -y -q install nginx
if [[ $(($(/usr/sbin/nginx -V 2>&1 | grep "TLS SNI support enabled" | wc -l))) < 0 ]]; then
    echo "This version of NGINX does not support TLS"
    exit 1
fi
echo "Starting NGINX"
sudo /etc/init.d/nginx start
echo "Enabling NGINX"
sudo chkconfig nginx on
echo "Done enabling NGINX"
