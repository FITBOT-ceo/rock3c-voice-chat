#!/bin/sh
set -eu

cd /home/radxa/voice-chat
exec /home/radxa/voice-chat/.venv/bin/python /home/radxa/voice-chat/web_ui/app.py
