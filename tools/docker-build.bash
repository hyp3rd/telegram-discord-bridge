#!/usr/bin/env bash

#######################################
# Determine if a command exists on the system
# Globals:
#   None
# Arguments:
#   A directory or a file
# Returns:
#   0 if the command exists, non-zero on error.
#######################################
__command_exists() {
  command -v "$@" >/dev/null 2>&1
}

#######################################
# Build and push docker image
# Globals:
#   None
# Arguments:
#   None
# Returns:
#   None
#######################################
build() {
  if __command_exists docker; then
    latest_version=$(git describe --tags --abbrev=0)

    docker build -t ghcr.io/hyp3rd/bridge:"$latest_version" -t ghcr.io/hyp3rd/bridge:latest .
    docker push ghcr.io/hyp3rd/bridge:"$latest_version"
    docker push ghcr.io/hyp3rd/bridge:latest
  else
    echo "docker is not installed or not running'"
  fi
}

build
