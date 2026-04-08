#!/bin/sh
set -eu

exec /home/radxa/voice-chat/.venv/bin/python \
  /home/radxa/voice-chat/scripts/voice_assistant_daemon.py \
  --seconds 4 \
  --idle-sleep 0.4 \
  --speak-cooldown 1.2
