#!/usr/bin/env bash
LOG_FILE="/home/dorten_hp_envy/logs/power-blackbox.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
BAT_CAP=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo "?")
BAT_STAT=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo "?")

case "$1" in
  pre)
    echo "[$TIMESTAMP] [KERNEL-HOOK] PRE-$2 | BAT=${BAT_CAP}%($BAT_STAT) | Flushing cache, compacting memory & setting safe image_size" >> "$LOG_FILE"
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
    echo 1 > /proc/sys/vm/compact_memory 2>/dev/null || true
    echo 2147483648 > /sys/power/image_size 2>/dev/null || true
    ;;
  post)
    echo Y > /sys/module/acpi/parameters/ec_busy_polling 2>/dev/null || true
    # Refresh amd_sfh on resume to prevent MP2 co-processor mailbox stalls
    systemctl stop iio-sensor-proxy.service 2>/dev/null || true
    modprobe -r hid_sensor_accel_3d hid_sensor_gyro_3d hid_sensor_magn_3d hid_sensor_hub amd_sfh 2>/dev/null || true
    modprobe amd_sfh sensor_mask=1 2>/dev/null || true
    systemctl start iio-sensor-proxy.service 2>/dev/null || true
    chmod 666 /dev/hidraw* 2>/dev/null || true
    chmod 666 /dev/input/event* 2>/dev/null || true
    echo "[$TIMESTAMP] [KERNEL-HOOK] POST-$2 (RESUMED) | BAT=${BAT_CAP}%($BAT_STAT) | Enabled ec_busy_polling=Y & refreshed amd_sfh" >> "$LOG_FILE"
    ;;
esac
