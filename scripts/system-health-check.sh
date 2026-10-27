#!/usr/bin/env bash
# ==============================================================================
# HP ENVY x360 System Health, Power, Tablet & Black-Box Diagnostic Tool
# ==============================================================================

echo "============================================================"
echo "        HP ENVY x360 13-ar0xxx Health & Power Diagnostic"
echo "============================================================"
echo ""

echo "--- [1] HARDWARE & PLATFORM ---"
echo "Model:   $(cat /sys/class/dmi/id/product_name 2>/dev/null || echo 'HP ENVY x360') (SKU: $(cat /sys/class/dmi/id/product_sku 2>/dev/null || echo 'Unknown'))"
echo "BIOS:    $(cat /sys/class/dmi/id/bios_version 2>/dev/null || echo 'Unknown') (Date: $(cat /sys/class/dmi/id/bios_date 2>/dev/null || echo 'Unknown'))"
echo "CPU:     $(lscpu | grep 'Model name:' | sed 's/Model name:[ \t]*//')"
echo "Kernel:  $(uname -r)"
echo "Cmdline: $(cat /proc/cmdline)"
echo ""

echo "--- [2] BATTERY, THERMALS & POWER SUBSYSTEM ---"
if [ -d /sys/class/power_supply/BAT0 ]; then
  status=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo "Unknown")
  cap=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo "Unknown")
  energy_now=$(cat /sys/class/power_supply/BAT0/charge_now 2>/dev/null || cat /sys/class/power_supply/BAT0/energy_now 2>/dev/null || echo "0")
  energy_full=$(cat /sys/class/power_supply/BAT0/charge_full 2>/dev/null || cat /sys/class/power_supply/BAT0/energy_full 2>/dev/null || echo "1")
  energy_design=$(cat /sys/class/power_supply/BAT0/charge_full_design 2>/dev/null || cat /sys/class/power_supply/BAT0/energy_full_design 2>/dev/null || echo "1")
  
  health=$(( (energy_full * 100) / energy_design ))
  echo "Battery Status:  $status ($cap%)"
  echo "Battery Health:  $health% (Full: $energy_full / Design: $energy_design)"
else
  echo "Battery BAT0 not detected."
fi
echo "Sleep States:    $(cat /sys/power/mem_sleep 2>/dev/null || echo 'N/A')"
echo ""

echo "--- [3] HIBERNATION & SWAP ---"
swapon --show
echo -n "DBus CanHibernate: "
busctl call org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager CanHibernate 2>/dev/null || echo "Failed to query"
echo -n "Systemd Logind Drop-in: "
[ -f /etc/systemd/logind.conf.d/lid-hibernate.conf ] && echo "INSTALLED" || echo "MISSING (run sudo ~/scripts/apply-all-fixes.sh)"
echo -n "Pre-Hibernate Sleep Hook: "
[ -x /usr/lib/systemd/system-sleep/00-envy-blackbox-and-hibernation.sh ] && echo "INSTALLED" || echo "MISSING (run sudo ~/scripts/apply-all-fixes.sh)"
echo ""

echo "--- [4] LID DAEMON, INHIBITOR & TABLET ROTATION DAEMON ---"
echo -n "Lid Daemon User Service:      "
systemctl --user is-active lid-hibernate.service 2>/dev/null || echo "inactive"
echo -n "Tablet Rotation User Service: "
systemctl --user is-active tablet-rotation.service 2>/dev/null || echo "inactive"
echo -n "Lid Switch Inhibitor Lock:    "
systemd-inhibit --list --no-pager 2>/dev/null | grep -q "lid-hibernate-daemon" && echo "ACTIVE (blocks s2idle race)" || echo "INACTIVE"
echo -n "AMD SFH hidraw0 Access:       "
[ -r /dev/hidraw0 ] && echo "READABLE" || echo "LOCKED (run sudo ~/scripts/apply-all-fixes.sh)"
echo ""

echo "--- [5] FINGERPRINT SENSOR (06cb:00c9) ---"
fp_usb=$(lsusb | grep -i "06cb:00c9" || echo "")
if [ -n "$fp_usb" ]; then
  echo "Sensor Detected on USB: $fp_usb"
  echo -n "DNF Package Lock:       "
  grep -q "^excludepkgs=.*libfprint" /etc/dnf/dnf.conf 2>/dev/null && echo "LOCKED (protected from dnf upgrade)" || echo "UNLOCKED"
  echo -n "fprintd Status:         "
  fprintd-list "$USER" 2>&1
else
  echo "Synaptics 06cb:00c9 not detected on USB bus."
fi
echo ""

echo "--- [6] RECENT BLACK-BOX POWER LOGS (last 10 lines) ---"
if [ -f /home/dorten_hp_envy/logs/power-blackbox.log ]; then
  tail -n 10 /home/dorten_hp_envy/logs/power-blackbox.log
else
  echo "No black-box logs yet."
fi
echo "============================================================"
