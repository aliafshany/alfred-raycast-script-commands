#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Public IP
# @raycast.mode inline
# @raycast.packageName Examples

# Optional parameters:
# @raycast.icon 🌐
# @raycast.refreshTime 1h
# @raycast.description Show the current public IPv4 address

curl -fsS --max-time 8 https://api.ipify.org || curl -fsS --max-time 8 https://ifconfig.me/ip
