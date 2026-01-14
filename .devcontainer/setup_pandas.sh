#!/bin/bash

# Set COMMIT_DATE to get latest commit until a specific date (format: YYYY-MM-DD)
# Can be overridden by passing a different date as first argument
# Default: 2025-08-01
COMMIT_DATE="${1:-2025-08-01}"

echo "Creating directory for clones"
cd ..
sudo mkdir clones
sudo chown vscode:vscode clones/
cd clones

echo "Cleaning any existing pandas-dev containers"
docker rm -f pandas-dev1
docker rm -f pandas-dev2
docker rm -f pandas-dev3

mkdir clone1
cd clone1

echo "Creating first clone of pandas"
git clone https://github.com/pandas-dev/pandas.git
cd pandas

if [ -n "$COMMIT_DATE" ]; then
  echo "Checking out latest commit until $COMMIT_DATE"
  COMMIT_HASH=$(git log --all --until="$COMMIT_DATE" -1 --format=%H)
  if [ -z "$COMMIT_HASH" ]; then
    echo "Error: No commits found before $COMMIT_DATE"
    exit 1
  fi
  echo "Found commit: $COMMIT_HASH"
  git checkout "$COMMIT_HASH"
fi

echo "Building dev container for pandas (first clone)"
docker build -t pandas-dev .
docker run -t -d --name pandas-dev1 -v ${PWD}:/home/pandas pandas-dev
docker exec pandas-dev1 python -m pip install -ve . --no-build-isolation --config-settings editable-verbose=true
docker exec pandas-dev1 python -m pip install sphinx-version-warning coverage==7.11.0
echo "Done with first clone"

echo "Creating second clone of pandas"
cd ../..
cp -r clone1 clone2
cd clone2/pandas
echo "Building dev container for pandas (second clone)"
docker run -t -d --name pandas-dev2 -v ${PWD}:/home/pandas pandas-dev
docker exec pandas-dev2 python -m pip install -ve . --no-build-isolation --config-settings editable-verbose=true
docker exec pandas-dev2 python -m pip install sphinx-version-warning coverage==7.11.0
echo "Done with second clone"

echo "Creating third clone of pandas"
cd ../..
cp -r clone1 clone3
cd clone3/pandas
echo "Building dev container for pandas (third clone)"
docker run -t -d --name pandas-dev3 -v ${PWD}:/home/pandas pandas-dev
docker exec pandas-dev3 python -m pip install -ve . --no-build-isolation --config-settings editable-verbose=true
docker exec pandas-dev3 python -m pip install sphinx-version-warning coverage==7.11.0
echo "Done with third clone"

cd ../../../Testora-diff-test-gen
