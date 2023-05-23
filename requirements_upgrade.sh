#!/bin/bash

# This script upgrades all of our lockfiles to the latest.

set -eu -o pipefail

me=$(python3 -c 'import os; print(os.path.realpath("'"$0"'"))')
cd $(dirname "$me")

./bazel run //:requirements.update -- --upgrade
./bazel run //:test_requirements.update -- --upgrade
./bazel run //examples:requirements.update -- --upgrade
