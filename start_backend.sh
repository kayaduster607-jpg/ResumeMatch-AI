#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
python main.py
