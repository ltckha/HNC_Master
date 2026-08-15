#!/usr/bin/env zsh
# HNC Control Center - Local Developer Launcher Script
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
source "$DIR/venv/bin/activate"
python3 "$DIR/main.py"
