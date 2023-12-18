#!/usr/bin/env bash

# #######################################
# This script is used to bump the version of the bridge
# project. It will bump the version in the release.py
# file and commit the change.
# #######################################
bump_version() {
    # Get the latest version tag
    latest_version=$(git describe --tags --abbrev=0)

    # Increment the last number in the version tag by 1
    new_version=$(echo "$latest_version" | awk -F. -v OFS=. '{$NF = $NF + 1;} 1' | sed 's/ /./g')

    # Replace the version number in release.py with the new version number
    sed -i '' 's/__version__ = .*/__version__ = "'"$new_version"'"/' bridge/release.py

    # Replace the version number in README.md with the new version number
    sed -i '' 's/ghcr.io\/hyp3rd\/bridge:.*/ghcr.io\/hyp3rd\/bridge:'"$new_version"'/' README.md
}

# bump_version && git add bridge/release.py README.md
bump_version
