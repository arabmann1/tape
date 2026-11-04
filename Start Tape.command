#!/bin/bash
# Double-click this on a Mac. (The first time, right-click it and choose Open.)
bash "$(dirname "$0")/launcher/start.sh"
status=$?
if [ "$status" -ne 0 ]; then
  read -r -p "  Press Enter to close this window. " _
fi
exit "$status"
