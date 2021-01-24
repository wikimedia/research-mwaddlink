#!/bin/bash

set -ex

WIKI_ID=${WIKI_ID:-simplewiki}
DATASET_PATH=$(pwd)/data/${WIKI_ID}

DATASET_PUBLISH_PATH="/srv/published/datasets/one-off/research-mwaddlink/$WIKI_ID"
mkdir -p "$DATASET_PUBLISH_PATH"
cp "$DATASET_PATH/*.sql.gz" "$DATASET_PUBLISH_PATH/"
cp "$DATASET_PATH/*.sqlite.gz" "$DATASET_PUBLISH_PATH/"
cp "$DATASET_PATH/$WIKI_ID.linkmodel.json" "$DATASET_PUBLISH_PATH/"
cp "$DATASET_PATH/*.checksum" "$DATASET_PUBLISH_PATH/"

echo "These datasets can be used with Wikimedia's Link Recommendation Service.
See https://wikitech.wikimedia.org/wiki/Add_Link/Datasets for details" > "$DATASET_PUBLISH_PATH"/README