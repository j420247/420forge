#!/bin/bash

umask 0022

fancywait() {
    FOO=$1
    echo -n "Sleeping $1 seconds "
    while [ $FOO -ne 0 ] ; do
        sleep 1
        echo -n "."
        FOO=$((FOO-1))
    done
    echo -ne "\r\033[K"
}

update_permission() {
    ITEM=$1
    if [ ! -e "$ITEM" ] ; then
        echo "ERROR: $ITEM does not exist!"
        exit 1
    fi
    if [ -d "$ITEM" ] ; then
        if [[ "$UID" -eq 0 ]] ; then
            /bin/chgrp atlassian-staff $ITEM
        fi
        chmod 2775 $ITEM
    elif [ -f "$ITEM" ] ; then
        chmod 644 $ITEM
    fi
}

if [ "x$1" == "x--no-heap" ]; then
    NO_HEAP=0
    shift
else
    NO_HEAP=1
fi

if [ "x$1" == "x--keepdump" ]; then
    KEEPDUMP=0
    shift
else
    KEEPDUMP=1
fi

if [ -z $1 ]; then
    echo "Attempting to auto-detect your service..."
    VALID_UPSTART_TYPES="confluence jira"
    UPSTART_FOUND=
    for type in $VALID_UPSTART_TYPES ; do
        if [ -f "/etc/init/$type.conf" ] ; then
            UPSTART_FOUND=$type
            break
        fi
    done

    # Try upstart if found
    UPSTART_IS_VALID=0
    if [ ! -z "$UPSTART_FOUND" ] ; then
        STATUS_OUT=$(status $UPSTART_FOUND 2> /dev/null)
        if [ $? == 0 ] ; then
            UPSTART_IS_VALID=1
        fi
    fi

    if [ $UPSTART_IS_VALID == 0 ] ; then
        # try to find pid
        SERVICE_PID=$(pgrep -f 'tomcat')
    else
        if [[ ! "$STATUS_OUT" =~ ([0-9]+)$ ]] ; then
            echo "Service does not appear to be running"
        else
            echo "Detected upstart service - ${UPSTART_FOUND}"
            SERVICE_PID=${BASH_REMATCH[1]}
        fi
    fi
else
    SERVICE_DIR=$1
    if [[ "$SERVICE_DIR" =~ ^/ ]] ; then
        echo "Please supply the service name  (eg jira|confluence)"
    else
        UPSTART_FOUND=$1
        STATUS_OUT=$(status $UPSTART_FOUND 2> /dev/null)
        if [ $? != 0 ] || [[ ! "$STATUS_OUT" =~ ([0-9]+)$ ]] ; then
            echo "Supplied upstart service ($UPSTART_FOUND) does not seem to be up, aborting"
            exit 3
        else
            echo "Upstart service - ${UPSTART_FOUND} detected"
            SERVICE_PID=${BASH_REMATCH[1]}
        fi
    fi
fi

# Set service name
if [ ! -z "$UPSTART_FOUND" ] ; then
  SERVICE_NAME=${UPSTART_FOUND}
else
  SERVICE_NAME="$(grep ATL_DB_NAME /etc/atl | cut -d= -f2)"
fi

# Make sure this PID exists and is sane - otherwise, bail out.
if [ -z "$SERVICE_PID" ] ; then
    echo "Unable to determine service pid of running app!"
    exit 4
fi

if [ ! -e /proc/${SERVICE_PID}/status ]; then
  echo "Couldn't find details about SERVICE_PID \"$SERVICE_PID\" - bailing out"
  exit 3
fi

# OK - SERVICE_PID seems valid...let's get some details about it...
JAVA=$(ps --no-headers -o cmd ${SERVICE_PID} | awk '{print $1}')
SERVICE_JAVA_HOME=${JAVA%/bin/java}
PROCESS=`awk '/^Name/ {print $2}' /proc/${SERVICE_PID}/status`
PROCUID=`awk '/^Uid/ {print $2}' /proc/${SERVICE_PID}/status`
PROCUSER=$(getent passwd ${PROCUID})
PROCUSER=${PROCUSER%%:*}

TMPDIR=/tmp
SCRATCHDIR=/scratch

if [ -d $SCRATCHDIR ]; then
    TMPDIR=$SCRATCHDIR
fi

if [[ $0 =~ (thread|heap)_dump ]] ; then
    DUMP_DIR_EXT=${BASH_REMATCH[0]}
    TMPDIR=$TMPDIR/$DUMP_DIR_EXT
fi

if [ ! -d "$TMPDIR" ] ; then
    mkdir $TMPDIR
    /bin/chown $PROCUSER $TMPDIR
fi

