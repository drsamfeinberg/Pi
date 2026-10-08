#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Run Install.command first.'
  read -r -p 'Press Return to close.'
  exit 1
fi
exec .venv/bin/python pi_service.py
