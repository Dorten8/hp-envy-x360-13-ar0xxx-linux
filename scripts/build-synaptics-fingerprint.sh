#!/usr/bin/env bash
# ==============================================================================
# Synaptics Prometheus / Tudor Fingerprint (06cb:00c9) Driver Builder for Fedora
# ==============================================================================
# This script builds the experimental vojtapl/synaTudorMiS libfprint driver
# for Synaptics Match-in-Sensor fingerprint readers on HP ENVY/Spectre laptops.
# ==============================================================================

set -euo pipefail

BUILD_DIR="/home/dorten_hp_envy/src/fingerprint-driver"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "============================================================"
echo "    Synaptics 06cb:00c9 Driver Build Assistant (Fedora)"
echo "============================================================"
echo ""
echo "[*] Step 1: Checking / installing build dependencies..."
echo "Run with sudo if dependencies are missing:"
echo "sudo dnf install -y git meson ninja-build gcc gcc-c++ \\"
echo "    glib2-devel libusb1-devel pixman-devel nss-devel \\"
echo "    openssl-devel systemd-devel polkit-devel \\"
echo "    gobject-introspection-devel doctool vala"
echo ""

echo "[*] Step 2: Cloning libfprint with Tudor driver support..."
if [ ! -d "libfprint" ]; then
  git clone --depth 1 https://github.com/vojtapl/libfprint.git
else
  echo "    libfprint repository already present."
fi

if [ ! -d "synaTudorMiS" ]; then
  git clone --depth 1 https://github.com/vojtapl/synaTudorMiS.git
else
  echo "    synaTudorMiS repository already present."
fi

echo "[*] Step 3: Configuring build with Meson..."
cd libfprint
if [ ! -d "build" ]; then
  meson setup build --prefix=/usr -Ddrivers=all -Dudev_rules=enabled -Ddoc=false
else
  echo "    Meson build directory already initialized."
fi

echo "[*] Step 4: Compiling libfprint..."
ninja -C build

echo ""
echo "============================================================"
echo "[✓] Build completed successfully!"
echo "To test device detection without replacing system files:"
echo "  sudo ./build/examples/identify"
echo "  sudo ./build/examples/enroll"
echo ""
echo "To install system-wide:"
echo "  sudo ninja -C build install"
echo "  sudo systemctl restart fprintd"
echo "============================================================"
