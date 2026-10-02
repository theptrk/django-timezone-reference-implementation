#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

if [ "$(git branch --show-current)" != "main" ]; then
  echo "Refusing deploy: check out local main first." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Refusing deploy: working tree is not clean." >&2
  exit 1
fi

git fetch origin main
local_sha=$(git rev-parse HEAD)
origin_sha=$(git rev-parse origin/main)

if [ "$local_sha" != "$origin_sha" ]; then
  echo "Refusing deploy: local main is not exactly origin/main." >&2
  echo "local main:  $local_sha" >&2
  echo "origin/main: $origin_sha" >&2
  exit 1
fi

echo "Deploying origin/main $origin_sha to dokku/master."
git push dokku HEAD:master
