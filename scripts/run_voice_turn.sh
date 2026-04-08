#!/bin/sh
set -eu

exec /home/radxa/voice-chat/.venv/bin/python \
  /home/radxa/voice-chat/scripts/voice_turn_loop.py \
  --seconds 5
