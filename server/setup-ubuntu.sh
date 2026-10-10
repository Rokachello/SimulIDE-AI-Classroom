#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -m venv .venv || { echo 'Namesti Python venv: sudo apt install python3-venv'; exit 1; }
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py init
printf '\nPripravljeno. Za zagon: bash zazen-server.sh\n'
