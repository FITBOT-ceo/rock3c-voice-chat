#!/bin/sh
set -eu

exec /home/radxa/voice-chat/llama.cpp/build/bin/llama-server \
  --model /home/radxa/voice-chat/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  --threads 4 \
  --ctx-size 1024 \
  --parallel 1
