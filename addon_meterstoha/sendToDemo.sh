#!/bin/bash
# Private script to synchronize the development with
# "demo" HA server configured in .ssh/config as ha-demo.
#scp -rp ./* ha-demo:/addons/haos-addon/
scp -rp Dockerfile ./run.sh translations config.yaml build.yaml ha-demo:/addons/haos-addon/
#scp -rp Dockerfile ./run.sh translations config.yaml ha-demo:/addons/haos-addon/
