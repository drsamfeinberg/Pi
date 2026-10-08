#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v brew >/dev/null 2>&1; then
  echo 'Install Homebrew from https://brew.sh first, then run this installer again.'
  read -r -p 'Press Return to close.'
  exit 1
fi
brew install python@3.11 ollama
"$(brew --prefix python@3.11)/bin/python3.11" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
brew services start ollama
for attempt in {1..30}; do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
  sleep 1
done
ollama pull qwen3:4b
.venv/bin/python -c 'from faster_whisper import WhisperModel; WhisperModel("small", device="cpu", compute_type="int8")'
echo 'Models installed. Double-click Start.command and paste its pairing code into Pi.'
read -r -p 'Press Return to close.'
