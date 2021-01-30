#!/bin/bash

set -ex

WIKI_ID=${WIKI_ID:-simplewiki}
DATASET_PATH=$(pwd)/data/${WIKI_ID}

DATASET_PUBLISH_PARENT_DIRECTORY="/srv/published/datasets/one-off/research-mwaddlink"
DATASET_PUBLISH_PATH="$DATASET_PUBLISH_PARENT_DIRECTORY/$WIKI_ID"
DATASET_LISTING_FILE="$DATASET_PUBLISH_PARENT_DIRECTORY/wikis.txt"
mkdir -p "$DATASET_PUBLISH_PATH"
cp "$DATASET_PATH/"*.sql.gz "$DATASET_PUBLISH_PATH/"
cp "$DATASET_PATH/"*.sqlite.gz "$DATASET_PUBLISH_PATH/"
cp "$DATASET_PATH/$WIKI_ID.linkmodel.json" "$DATASET_PUBLISH_PATH/"
cp "$DATASET_PATH/"*.checksum "$DATASET_PUBLISH_PATH/"

# Write to an index of all wikis that have published datasets. This file is parsed by
# load-datasets.py when a specific wiki ID is not defined and the --download option
# is used.
if ! grep -q "$WIKI_ID" "$DATASET_LISTING_FILE"; then
  echo "$WIKI_ID" >> $DATASET_LISTING_FILE
fi

echo "These datasets can be used with Wikimedia's Link Recommendation Service.
See https://wikitech.wikimedia.org/wiki/Add_Link/Datasets for details" > "$DATASET_PUBLISH_PATH"/README
