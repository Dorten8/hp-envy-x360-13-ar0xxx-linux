#!/usr/bin/env bash
# Restores Fedora stock libfprint and fprintd
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "[!] Please run with sudo: sudo $0"
  exit 1
fi

echo "[*] Restoring stock Fedora libfprint and fprintd..."
systemctl stop fprintd || true
dnf reinstall -y libfprint fprintd fprintd-pam
systemctl restart fprintd
echo "[✓] Restored to official stock packages."
