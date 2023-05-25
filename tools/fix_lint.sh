#!/bin/bash

# This script is intended for use by drake-blender developers.
# Users of the project do not need to run it.

# This script runs the autoformatter(s) on all source files that are subject to
# automated linter style checks.

set -eu -o pipefail

me=$(python3 -c 'import os; print(os.path.realpath("'"$0"'"))')
cd $(dirname "$me")/..

./bazel run //tools:buildifier \
    *.bazel \
    */*.bazel \
    */*.bzl
./bazel build //tools:black //tools:isort
./.bazel/bin/tools/black \
    bazel \
    *.py \
    */*.py \
    */*/*.py
./.bazel/bin/tools/isort \
    bazel \
    *.py \
    */*.py \
    */*/*.py
