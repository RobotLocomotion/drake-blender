#!/bin/bash

# This script runs the autoformatter(s) on all source files that are subject to
# automated linter style checks.

set -eu -o pipefail

me=$(python3 -c 'import os; print(os.path.realpath("'"$0"'"))')
cd $(dirname "$me")

./bazel run //:buildifier \
    *.bazel \
    *.bzl \
    */*.bazel
./bazel build //:black //:isort
./.bazel/bin/black \
    bazel \
    *.py \
    */*.py \
    */*/*.py
./.bazel/bin/isort \
    bazel \
    *.py \
    */*.py \
    */*/*.py
