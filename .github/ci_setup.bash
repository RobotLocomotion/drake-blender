#!/bin/bash

set -euxo pipefail

# Rendering in CI (for both Drake and Blender) requires a GL pipeline.
sudo apt-get --assume-yes install libegl1
