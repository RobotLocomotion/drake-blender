#!/bin/bash
# SPDX-License-Identifier: BSD-2-Clause

# This script is intended for use by drake-blender developers.
# Users of the project do not need to run it.

# This script upgrades the pinned version of all dependencies.
# TODO(jwnimmer-tri) It doesn't upgrade MODULE.bazel yet.

set -eu -o pipefail

me=$(python3 -c 'import os; print(os.path.realpath("'"$0"'"))')
cd $(dirname "$me")/..

python3 -B ./tools/upgrade_helper.py
./bazel run //tools:buildifier tools/buildifier_version.bzl

./bazel run //:requirements.update -- --upgrade
./bazel run //examples:requirements.update -- --upgrade
./bazel run //test:requirements.update -- --upgrade
