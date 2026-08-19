#!/usr/bin/env sh
set -eu
PORT="${PORT:-8000}"
exec gunicorn --workers 1 --threads 4 --timeout 700 --bind "0.0.0.0:${PORT}" app:app
