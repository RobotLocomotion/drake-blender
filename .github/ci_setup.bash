#!/bin/bash

set -euxo pipefail

# Downgrade mesa per https://github.com/RobotLocomotion/drake/issues/18726.
sudo apt-get --assume-yes --allow-downgrades install \
 xvfb \
 libegl1 \
 libegl-mesa0=22.0.1-1ubuntu2 \
 libgbm1=22.0.1-1ubuntu2 \
 libgl1-mesa-dri=22.0.1-1ubuntu2 \
 libglapi-mesa=22.0.1-1ubuntu2 \
 libglx-mesa0=22.0.1-1ubuntu2

cat << EOF | sudo tee /lib/systemd/system/xvfb.service
[Unit]
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +extension RANDR +render -noreset

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl --now --quiet enable /lib/systemd/system/xvfb.service
