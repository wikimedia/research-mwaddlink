#!/usr/bin/env bash

set -e

# Download datasets for simplewiki (the smallest datasets we have) and place them
# in the data directory. These will then be used by pytest integration tests.

for WIKI_ID in simplewiki bat_smgwiki; do
  echo "Creating directory for data/$WIKI_ID and switching to it"
  # In CI, home directory is the same as app dir, but that's probably not the case
  # in your local environment.
  APP_DIR=$(pwd)
  mkdir -p "$APP_DIR/data"
  mkdir -p "$APP_DIR/data/$WIKI_ID"
  cd "$APP_DIR/data/$WIKI_ID"

  echo "Downloading and verifying linkmodel..."
  curl -Os https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/$WIKI_ID/$WIKI_ID.linkmodel.json.checksum
  curl -Os https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/$WIKI_ID/$WIKI_ID.linkmodel.json
  shasum -a 256 -c $WIKI_ID.linkmodel.json.checksum

  download_and_verify_sqlite() {
    echo "Downloading and verifying $1 and $2..."
    curl -Os https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/$WIKI_ID/$1
    curl -Os https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/$WIKI_ID/$2
    # Get rid of the relative path to the checksum
    CHECKSUM=$(cat $1| cut -d ' ' -f1)
    echo "$CHECKSUM  $2" > $1
    echo "$2 checksum: $CHECKSUM"
    shasum -a 256 -c $1
    gunzip --force $2
  }

  for TABLE in anchors pageids redirects w2vfiltered; do
    CHECKSUM_FILENAME=$WIKI_ID.$TABLE.sqlite.checksum
    FILENAME=$WIKI_ID.$TABLE.sqlite.gz
    download_and_verify_sqlite $CHECKSUM_FILENAME $FILENAME
  done

  # Back to app root
  cd "$APP_DIR"
done
