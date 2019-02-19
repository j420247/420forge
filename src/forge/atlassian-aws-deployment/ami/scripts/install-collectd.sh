#!/bin/bash
set -e

echo "Copying collectd.conf to final destination /etc/collectd.conf"
sudo mv /tmp/collectd.conf /etc/collectd.conf
echo "changing ownership of /etc/collectd.conf to root:root"
sudo chown root:root /etc/collectd.conf
echo "Changing file permissions on collectd.conf to 0600"
sudo chmod 0600 /etc/collectd.conf