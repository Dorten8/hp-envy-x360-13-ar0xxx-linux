#!/usr/bin/env bash
# ==============================================================================
# HP ENVY x360 Convertible 13-ar0xxx Master Linux Enablement Installer
# One-shot orchestrator to apply all power, sensor, performance, and driver fixes.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$EUID" -ne 0 ]; then
  echo "[!] Error: Root privileges required."
  echo "    Please run with sudo: sudo ./install.sh"
  exit 1
fi

echo "============================================================"
echo "   HP ENVY x360 Convertible 13-ar0xxx Linux Enablement"
echo "============================================================"
echo "[*] Invoking master fix script..."
"$SCRIPT_DIR/scripts/apply-all-fixes.sh"
