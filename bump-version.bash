#!/usr/bin/env bash

# #######################################
# This script is used to bump the version of the bridge
# project. It will bump the version in the release.py
# file and commit the change.
# #######################################
bump_version() {
    git describe --tags --abbrev=0 | awk -F. -v OFS=. '{$NF = $NF + 1;} 1' | sed 's/ /./g' | xargs -I {} sed -i '' 's/__version__ = .*/__version__ = "'{}'"/' bridge/release.py
    git describe --tags --abbrev=0 | awk -F. -v OFS=. '{$NF = $NF + 1;} 1' | sed 's/ /./g' | xargs -I {} sed -i '' 's/ghcr.io\/hyp3rd\/bridge:.*/ghcr.io\/hyp3rd\/bridge:"'{}'"/' README.md
}

bump_version && git add bridge/release.py README.md
