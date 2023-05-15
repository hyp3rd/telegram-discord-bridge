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
# Run the uvicorn server
# Globals:
#   None
# Arguments:
#   None
# Returns:
#   None
#######################################
run() {
  if __command_exists uvicorn; then
    uvicorn api.api:app --reload
  else
    echo "uvicorn is not installed. Please install it using 'pip install uvicorn, or check that you're in the correct virtual environment'"
  fi
}

run
