#!/bin/bash
# Double-click to show the safe local commands. Everything runs on this Mac.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "AutoWarmer needs Python 3, which comes with Apple's developer tools."
  echo "Install them with:   xcode-select --install"
  echo
  read -r -p "Press return to close." _
  exit 1
fi

python3 -m autowarmer "$@"
code=$?
if [ $code -ne 0 ]; then
  echo
  echo "AutoWarmer stopped (exit $code). The message above says why."
  read -r -p "Press return to close." _
fi
exit $code
