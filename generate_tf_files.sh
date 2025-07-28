#!/usr/bin/env bash

dirs=$(find . -maxdepth 1 -type d ! -name '.')

for dir in $dirs; do
  echo "Processing directory: $dir"

  for file in main.tf variables.tf output.tf; do
    path="$dir/$file"
    if [ ! -f "$path" ]; then
      echo "Creating $path"
      touch "$path"
    else
      echo "$path already exists. Skipping."
    fi
  done
done