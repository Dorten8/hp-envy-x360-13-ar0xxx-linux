#!/usr/bin/env bash
# ==============================================================================
# Synaptics 06cb:00c9 Driver Installer (Fedora 43)
# ==============================================================================

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "[!] Please run with sudo: sudo $0"
  exit 1
fi

SRC_DIR="/home/dorten_hp_envy/src/fingerprint-driver"

echo "============================================================"
echo "    Installing Synaptics 06cb:00c9 Driver & Services"
echo "============================================================"

echo "[*] Step 1: Stopping existing fprintd..."
systemctl stop fprintd || true

echo "[*] Step 2: Safe backup of stock library..."
if [ -f /usr/lib64/libfprint-2.so.2.0.0.stock-bak ]; then
  mv /usr/lib64/libfprint-2.so.2.0.0.stock-bak /var/backup-libfprint-stock.so || true
fi

echo "[*] Step 3: Installing compiled libfprint..."
cp -f "$SRC_DIR/libfprint/build/libfprint/libfprint-2.so.2.0.0" /usr/lib64/
ln -sf /usr/lib64/libfprint-2.so.2.0.0 /usr/lib64/libfprint-2.so.2
ln -sf /usr/lib64/libfprint-2.so.2 /usr/lib64/libfprint-2.so

echo "[*] Step 4: Installing compiled fprintd and utilities..."
cp -f "$SRC_DIR/fprintd/build/src/fprintd" /usr/libexec/fprintd
cp -f "$SRC_DIR/fprintd/build/pam/pam_fprintd.so" /usr/lib64/security/pam_fprintd.so
cp -f "$SRC_DIR/fprintd/build/utils/fprintd-enroll" /usr/bin/fprintd-enroll
cp -f "$SRC_DIR/fprintd/build/utils/fprintd-verify" /usr/bin/fprintd-verify
cp -f "$SRC_DIR/fprintd/build/utils/fprintd-list" /usr/bin/fprintd-list
cp -f "$SRC_DIR/fprintd/build/utils/fprintd-delete" /usr/bin/fprintd-delete

echo "[*] Step 5: Installing Polkit action policies & DBus configs..."
mkdir -p /usr/share/polkit-1/actions /usr/share/dbus-1/system.d /usr/share/dbus-1/system-services
cp -f "$SRC_DIR/fprintd/build/data/net.reactivated.fprint.device.policy" /usr/share/polkit-1/actions/
cp -f "$SRC_DIR/fprintd/data/net.reactivated.Fprint.conf" /usr/share/dbus-1/system.d/
cp -f "$SRC_DIR/fprintd/build/data/net.reactivated.Fprint.service" /usr/share/dbus-1/system-services/
chmod 644 /usr/share/polkit-1/actions/net.reactivated.fprint.device.policy

echo "[*] Step 6: Creating storage directories..."
mkdir -p /var/lib/fprint/0-persistent/synatlsmoc
chmod 700 /var/lib/fprint
chmod 700 /var/lib/fprint/0-persistent
chmod 700 /var/lib/fprint/0-persistent/synatlsmoc

echo "[*] Step 7: Installing udev rules for 06cb:00c9..."
cat << 'UDEV_EOF' > /etc/udev/rules.d/70-libfprint-2.rules
# Synaptics Prometheus / Tudor Match-in-Sensor (06cb:00c9)
SUBSYSTEM=="usb", ATTRS{idVendor}=="06cb", ATTRS{idProduct}=="00c9", ATTRS{dev}=="*", ENV{ID_SECURITY_TOKEN}="1", ENV{DEVTYPE}=="usb_device", TAG+="uaccess"
UDEV_EOF

echo "[*] Step 8: Updating dynamic linker cache & udev..."
ldconfig
udevadm control --reload
udevadm trigger

echo "[*] Step 9: Configuring fprintd debug logging & restarting services..."
mkdir -p /etc/systemd/system/fprintd.service.d
cat << 'DBG_EOF' > /etc/systemd/system/fprintd.service.d/debug.conf
[Service]
Environment="G_MESSAGES_DEBUG=fp-device,synatlsmoc,fprintd"
DBG_EOF
systemctl daemon-reload
systemctl restart polkit
systemctl restart fprintd

echo "[*] Step 10: Enabling PAM authselect..."
authselect enable-feature with-fingerprint || true
authselect apply-changes || true

echo ""
echo "============================================================"
echo "[✓] Driver and Services successfully installed and configured!"
echo "Polkit Action Verification:"
pkaction --action-id net.reactivated.fprint.device.enroll || true
echo "============================================================"
echo "You can now run: fprintd-enroll"
echo "============================================================"
