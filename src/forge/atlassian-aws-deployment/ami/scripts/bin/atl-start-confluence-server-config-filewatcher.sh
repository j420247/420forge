#!/usr/bin/env bash

set -e

WATCHED_FILE=${WATCHED_FILE:?"The file to watch must be supplied"}
FILE_DEST=${FILE_DEST:?"The backup destination must be supplied"}
LOG_FILE=${LOG_FILE:?"The file for logging events must be supplied"}

FILEPATH=$(dirname "${WATCHED_FILE}")
INOTIFYCMD="inotifywait -m --timefmt '%Y-%m-%d %H:%M:%S' --format '%T %w%f' -e moved_to \"${FILEPATH}\""

if [[ ! $(pgrep -f "${INOTIFYCMD}") ]]; then
    eval "${INOTIFYCMD}" | while read -r date time file; do
        if [[ "${WATCHED_FILE}" == "${file}" ]]; then
            echo "${date} ${time} Watched file (${file}) has been modified; backing up to $(dirname "${FILE_DEST}")" >> "${LOG_FILE}" 2>&1
            cp -fp "${file}" "${FILE_DEST}" >> "${LOG_FILE}" 2>&1
        fi
    done
fi
