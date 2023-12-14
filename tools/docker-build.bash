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
    docker build -t ghcr.io/hyp3rd/bridge:"$(git describe --tags)" .

    docker push ghcr.io/hyp3rd/bridge:"$(git describe --tags)"
  else
    echo "docker is not installed or not running'"
  fi
}

build
