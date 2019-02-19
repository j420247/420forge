#!/usr/bin/env bash

# Please run this script from the "test" folder, so it can correctly load functions from atl-init-synchrony.sh

source ../ami/scripts/init.d/atl-init-synchrony.sh test

function assertNegative {
    if [[ $1>=0 ]]; then
        echo "Value supposed to be negative! Current value: $1"
        if [[ -n "$2" ]]; then
            echo "$2"
        fi
        exit 1
    fi
}

function assertPositive {
    if [ $1 -lt 1 ]; then
        echo "Value supposed to be positive! Current value: $1"
        if [[ -n "$2" ]]; then
            echo "$2"
        fi
        exit 1
    fi
}

function assertEquals {
    if ! [ "$1" == "$2" ]; then
        echo "Values are not equal! $1 != $2"
        if [[ -n "$3" ]]; then
            echo "$3"
        fi
        exit 1
    fi
}

####### Testing #######
### Versions ###
assertEquals "0" $(compareVersions "confluence-parent-6.5.0-m01" "6.5.0") "confluence-parent-6.5.0-m01 vs 6.5.0"
assertEquals "0" $(compareVersions "confluence-parent-6.5.0-m01" "06.05.00") "confluence-parent-6.5.0-m01 vs 06.05.00"
assertPositive $(compareVersions "confluence-parent-6.5.0-m01" "6.4.0") "confluence-parent-6.5.0-m01 vs 6.4.0"
assertPositive $(compareVersions "confluence-parent-6.5.0-m01" "5.5.0") "confluence-parent-6.5.0-m01 vs 5.5.0"
assertPositive $(compareVersions "confluence-parent-6.5.0-m01" "6.4.9") "confluence-parent-6.5.0-m01 vs 6.4.9"
assertNegative $(compareVersions "confluence-parent-6.5.0-m01" "6.5.1") "confluence-parent-6.5.0-m01 vs 6.5.1"
assertNegative $(compareVersions "confluence-parent-6.5.0-m01" "6.6.0") "confluence-parent-6.5.0-m01 vs 6.6.0"
assertNegative $(compareVersions "confluence-parent-6.5.0-m01" "7.5.0") "confluence-parent-6.5.0-m01 vs 7.5.0"
assertNegative $(compareVersions "confluence-parent-6.5.0-m01" "7.0.0") "confluence-parent-6.5.0-m01 vs 7.0.0"
assertNegative $(compareVersions "confluence-parent-6.5.0-m01" "6.5.01") "confluence-parent-6.5.0-m01 vs 6.5.01"
assertNegative $(compareVersions "confluence-parent-6.5.0-m01" "0007.0.0") "confluence-parent-6.5.0-m01 vs 0007.0.0"

### Startup properties ###
assertEquals "$(oldSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.4.0-beta1")" "6.4.0-beta1"
assertEquals "$(oldSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.4.1000")" "6.4.1000"
assertEquals "$(oldSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.0.0")" "6.0.0"

assertEquals "$(newSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.5.0-m01")" "6.5.0-m01"
assertEquals "$(newSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.6.0")" "6.6.0"
assertEquals "$(newSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.5.1")" "6.5.1"
assertEquals "$(newSynchronyStartupProperties)" "$(getSynchronyStartupProperties "6.5.1-m00")" "6.5.1-m00"
assertEquals "$(newSynchronyStartupProperties)" "$(getSynchronyStartupProperties "latest")" "latest"
echo "All tests passed!"



