#!/bin/sh
cd "$(dirname "$0")" || exit 1
# Finder's PATH may omit Homebrew; never install dependencies silently.
for a7_python in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if "$a7_python" -c 'import sys; sys.exit(sys.version_info < (3,10))' 2>/dev/null; then
    exec "$a7_python" app.py
  fi
done
echo 'Please install Python 3.10+ from python.org, then open this file again.'
read -r a7_answer
