#!/bin/bash
# Private script to synchronize the development with
# "demo" HA server configured in .ssh/config as ha-demo.
#scp -rp ./* ha-demo:/addons/haos-addon/
scp -rp ./run.sh translations config.yaml ha-demo:/addons/haos-addon/
