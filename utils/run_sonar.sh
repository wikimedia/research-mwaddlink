#!/bin/bash

set -eu
set -o pipefail

# define permission of the files created by this script
# SonarQube needs to create tmp files during execution
# created from the template below
# https://gerrit.wikimedia.org/r/plugins/gitiles/integration/config/+/refs/heads/master/dockerfiles/java8-sonar-scanner/run.sh
umask 002

set +x

# check for conditional parameter SONAR_BRANCH_TARGET
args=()
if [ ! -z ${SONAR_BRANCH_TARGET+x} ]; then
  args+=( "-Dsonar.branch.target=$SONAR_BRANCH_TARGET" )
fi

# Initialize analysis, send data to SonarQube
/opt/sonar-scanner/bin/sonar-scanner "${args[@]}" -Dsonar.login="$SONAR_API_KEY" -Dsonar.branch.name="${SONAR_BRANCH_NAME}" "$@"
