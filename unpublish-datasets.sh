#!/bin/bash

set -ex

# Confirm WIKI_ID is set and doesn't have a "*" character
# in it to avoid nuking the entire repo.
if [ -z "$WIKI_ID" ]; then
  echo "WIKI_ID must be set."
  exit 1
elif [[ $WIKI_ID == *"*"* ]]; then
  echo "WIKI_ID cannot have a '*' character in it."
  exit 1
fi

DATASET_PUBLISH_PARENT_DIRECTORY="/srv/published/datasets/one-off/research-mwaddlink"
DATASET_PUBLISH_CHILD_DIRECTORY="$DATASET_PUBLISH_PARENT_DIRECTORY/$WIKI_ID"
DATASET_LISTING_FILE="$DATASET_PUBLISH_PARENT_DIRECTORY/wikis.txt"

# Function to remove files if they exist
function remove_file() {
  # Get the file path and pattern
  DIRECTORY_PATH=$1
  FILE_PATTERN=$2

  # Find all files that match the pattern
  FILES=$(find "$DIRECTORY_PATH" -type f -name "$FILE_PATTERN" -print)

  # Check if any files were found
  if [ -z "$FILES" ]; then
    echo "No files found matching the pattern '$FILE_PATTERN'."
  else
    # Delete the files found
    for FILE in $FILES; do
      rm -f "$FILE"
      echo $FILE" removed."
    done
  fi
}

# Confirm whether the directory exists.
if [ -d "$DATASET_PUBLISH_CHILD_DIRECTORY" ]; then
  # Delete the directory content.
  # code below is not DRY because we avoided `rm -rf <directory>` for safety.
  remove_file "$DATASET_PUBLISH_CHILD_DIRECTORY/" "*.sql.gz"
  remove_file "$DATASET_PUBLISH_CHILD_DIRECTORY/" "*.sqlite.gz"
  remove_file "$DATASET_PUBLISH_CHILD_DIRECTORY/" "$WIKI_ID.linkmodel.json"
  remove_file "$DATASET_PUBLISH_CHILD_DIRECTORY/" "*.checksum"
  remove_file "$DATASET_PUBLISH_CHILD_DIRECTORY/" "README"

  # Delete the directory if it is empty.
  if [ "$(ls -A $DATASET_PUBLISH_CHILD_DIRECTORY)" ]; then
    echo "$DATASET_PUBLISH_CHILD_DIRECTORY is not empty, check its content before removing. \
    If the remaining files are not one-offs, please add them to this unpublish script."
  else
    echo "$DATASET_PUBLISH_CHILD_DIRECTORY is empty, removing ..."
    rmdir "$DATASET_PUBLISH_CHILD_DIRECTORY"
    echo $WIKI_ID" has been removed from the published datasets repo."
  fi
fi

# Confirm whether the WIKI_ID exists in the index.
if grep -q "^$WIKI_ID$" "$DATASET_LISTING_FILE"; then
  # Remove the WIKI_ID from the index.
  sed -i "/^$WIKI_ID$/d" $DATASET_LISTING_FILE
  echo $WIKI_ID" has been delisted from the index."
fi