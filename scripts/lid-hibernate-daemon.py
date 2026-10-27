#!/usr/bin/env python3
"""
HP ENVY x360 Lid-Hibernate & Black-Box Power/Thermal Watchdog Daemon
- Holds a systemd-logind 'handle-lid-switch' block inhibitor so systemd-logind
  NEVER races with an s2idle 'suspend' when the lid closes.
- Listens for lid-close, PrepareForSleep, and PrepareForShutdown DBus signals.
- Writes persistent black-box diagnostics (battery %, power draw, CPU/GPU/NVMe
  temps, RAM/Swap free, tablet state, inhibitors) to ~/logs/power-blackbox.log.
- Boil-Protection Guard: If hibernation fails while the lid remains closed,
  automatically retries hibernation and falls back to clean poweroff before
  the laptop can overheat or drain the battery in a bag.
"""

import os
import sys
import time
import glob
import subprocess
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

LOG_DIR = "/home/dorten_hp_envy/logs"
LOG_FILE = os.path.join(LOG_DIR, "power-blackbox.log")

os.makedirs(LOG_DIR, exist_ok=True)

inhibit_fd = None
hibernate_in_flight = False
lid_closed_retry_count = 0
lid_closed_poll_streak = 0
last_polled_lid_closed = False


def read_file(path, default="N/A"):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default


def is_acpi_lid_closed():
    lid_state = read_file("/proc/acpi/button/lid/LID0/state")
    if lid_state == "N/A":
        lid_files = glob.glob("/proc/acpi/button/lid/*/state")
        if lid_files:
            lid_state = read_file(lid_files[0])
    return "closed" in lid_state.lower()


def get_hwmon_temps():
    temps = {}
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name = read_file(os.path.join(hwmon, "name"), "unknown")
        t1 = read_file(os.path.join(hwmon, "temp1_input"), "")
        if t1.isdigit():
            temps[name] = f"{int(t1) / 1000.0:.1f}C"
    return temps


def get_mem_swap_summary():
    info = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2 and parts[0] in (
                    "MemTotal",
                    "MemAvailable",
                    "SwapTotal",
                    "SwapFree",
                ):
                    kb = int(parts[1].strip().split()[0])
                    info[parts[0]] = f"{kb / 1024 / 1024:.2f}GiB"
    except Exception:
        pass
    return info


def get_system_snapshot():
    bat_status = read_file("/sys/class/power_supply/BAT0/status")
    bat_cap = read_file("/sys/class/power_supply/BAT0/capacity")
    ac_online = read_file("/sys/class/power_supply/ADP1/online")
    lid_state = read_file("/proc/acpi/button/lid/LID0/state")
    if lid_state == "N/A":
        lid_files = glob.glob("/proc/acpi/button/lid/*/state")
        if lid_files:
            lid_state = read_file(lid_files[0])
    tablet_mode = read_file("/sys/devices/platform/hp-wmi/tablet")
    temps = get_hwmon_temps()
    mem = get_mem_swap_summary()
    temp_str = ", ".join(f"{k}={v}" for k, v in temps.items())
    mem_str = (
        f"MemAvail={mem.get('MemAvailable', '?')}/{mem.get('MemTotal', '?')}, "
        f"SwapFree={mem.get('SwapFree', '?')}/{mem.get('SwapTotal', '?')}"
    )
    return (
        f"BAT={bat_cap}%({bat_status}) AC={ac_online} | "
        f"Lid='{lid_state}' Tablet={tablet_mode} | "
        f"Temps=[{temp_str}] | {mem_str}"
    )


def log(msg, level="INFO"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Failed to write log file: {e}", flush=True)


def acquire_lid_inhibitor(bus):
    global inhibit_fd
    try:
        login1 = bus.get_object("org.freedesktop.login1", "/org/freedesktop/login1")
        manager = dbus.Interface(login1, "org.freedesktop.login1.Manager")
        unix_fd = manager.Inhibit(
            "handle-lid-switch",
            "lid-hibernate-daemon",
            "Intercept lid close to trigger Hibernate instead of s2idle suspend",
            "block",
        )
        inhibit_fd = unix_fd.take()
        log(f"Acquired 'handle-lid-switch' block inhibitor (fd={inhibit_fd}).")
    except Exception as e:
        log(f"Lid inhibitor not held ({e}); relying on systemd-logind lid-hibernate.conf + watchdog.", "INFO")


def is_lid_currently_closed(bus):
    if is_acpi_lid_closed():
        return True
    try:
        upower = bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower")
        props = dbus.Interface(upower, "org.freedesktop.DBus.Properties")
        return bool(props.Get("org.freedesktop.UPower", "LidIsClosed"))
    except Exception:
        return False


def trigger_poweroff(bus, reason):
    log(f"EMERGENCY BOIL-PROTECTION POWEROFF: {reason} | {get_system_snapshot()}", "CRIT")
    try:
        login1 = bus.get_object("org.freedesktop.login1", "/org/freedesktop/login1")
        manager = dbus.Interface(login1, "org.freedesktop.login1.Manager")
        manager.PowerOff(False)
    except Exception as e:
        log(f"DBus PowerOff failed ({e}), running systemctl poweroff -i...", "CRIT")
        subprocess.run(["systemctl", "poweroff", "-i"], check=False)


def retry_after_cooldown(bus):
    if not is_lid_currently_closed(bus):
        log("Lid was opened during cooldown, aborting retry.", "INFO")
        return False
    log("Executing single clean retry after cooldown...", "EVENT")
    trigger_hibernate(bus, reason="Boil-guard single retry after cooldown")
    return False


def verify_lid_hibernated(bus):
    """
    Runs 35 seconds after a lid-close hibernate attempt.
    If the system successfully hibernates, the monotonic/wall clock pauses
    or the lid will be open upon resume. If the lid is STILL closed and we are
    still awake, hibernation failed or was aborted!
    """
    global hibernate_in_flight, lid_closed_retry_count
    hibernate_in_flight = False

    if not is_lid_currently_closed(bus):
        lid_closed_retry_count = 0
        return False

    lid_closed_retry_count += 1
    log(
        f"BOIL-GUARD: System is still awake with lid CLOSED (attempt #{lid_closed_retry_count})! "
        f"{get_system_snapshot()}",
        "WARN",
    )

    if lid_closed_retry_count >= 2:
        trigger_poweroff(
            bus,
            reason="Hibernation failed twice while lid remained closed; powering off to prevent overheating/battery drain!",
        )
    else:
        log("Retrying hibernation once after failure...", "WARN")
        trigger_hibernate(bus, reason=f"Boil-guard retry #{lid_closed_retry_count}")
    return False


def trigger_hibernate(bus, reason="Lid closed"):
    global hibernate_in_flight
    if hibernate_in_flight:
        log(f"Hibernate already in flight (reason={reason}), skipping duplicate call.")
        return

    hibernate_in_flight = True
    log(f"Initiating HIBERNATION (reason: {reason}) | {get_system_snapshot()}", "EVENT")

    try:
        os.sync()
    except Exception:
        pass

    try:
        login1 = bus.get_object("org.freedesktop.login1", "/org/freedesktop/login1")
        manager = dbus.Interface(login1, "org.freedesktop.login1.Manager")
        manager.Hibernate(False)
        log("Hibernation request dispatched via org.freedesktop.login1.Manager.Hibernate.")
    except Exception as e:
        log(f"DBus Hibernate failed: {e}. Falling back to 'systemctl hibernate'...", "WARN")
        try:
            subprocess.run(["systemctl", "hibernate"], check=True)
        except Exception as e2:
            log(f"systemctl hibernate fallback failed: {e2}", "ERROR")

    # Schedule Boil-Guard verification in 35 seconds
    GLib.timeout_add_seconds(35, verify_lid_hibernated, bus)


def on_upower_properties_changed(bus, interface, changed_props, invalidated_props):
    if interface == "org.freedesktop.UPower" and "LidIsClosed" in changed_props:
        is_closed = bool(changed_props["LidIsClosed"])
        log(f"UPower signal: LidIsClosed = {is_closed} | {get_system_snapshot()}", "EVENT")
        if is_closed:
            trigger_hibernate(bus, reason="UPower LidIsClosed=True")
        else:
            global lid_closed_retry_count
            lid_closed_retry_count = 0


def on_login1_properties_changed(bus, interface, changed_props, invalidated_props):
    if interface == "org.freedesktop.login1.Manager" and "LidClosed" in changed_props:
        is_closed = bool(changed_props["LidClosed"])
        log(f"login1 signal: LidClosed = {is_closed} | {get_system_snapshot()}", "EVENT")
        if is_closed:
            trigger_hibernate(bus, reason="login1 LidClosed=True")


def on_prepare_for_sleep(starting, bus):
    global hibernate_in_flight, lid_closed_retry_count, lid_closed_poll_streak, last_polled_lid_closed
    state = "ENTERING SLEEP/HIBERNATE" if starting else "RESUMED FROM SLEEP/HIBERNATE"
    log(f"PrepareForSleep(starting={ bool(starting) }) -> {state} | {get_system_snapshot()}", "SLEEP")
    if not starting:
        hibernate_in_flight = False
        lid_closed = is_lid_currently_closed(bus)
        if lid_closed:
            lid_closed_retry_count += 1
            log(
                f"BOIL-GUARD ALERT: System resumed while lid is STILL CLOSED! "
                f"(Failure count: {lid_closed_retry_count}) | {get_system_snapshot()}",
                "WARN",
            )
            if lid_closed_retry_count >= 2:
                trigger_poweroff(
                    bus,
                    reason=f"Hibernation failed {lid_closed_retry_count} times while lid closed; forcing poweroff to save battery!",
                )
            else:
                log("Scheduling single retry in 15 seconds after cooldown...", "WARN")
                GLib.timeout_add_seconds(15, retry_after_cooldown, bus)
        else:
            lid_closed_retry_count = 0
            lid_closed_poll_streak = 0
            last_polled_lid_closed = False


def on_prepare_for_shutdown(starting):
    state = "ENTERING SHUTDOWN/REBOOT" if starting else "SHUTDOWN ABORTED"
    log(f"PrepareForShutdown(starting={ bool(starting) }) -> {state} | {get_system_snapshot()}", "POWEROFF")


def poll_acpi_lid_state(bus):
    """
    Lightweight 2-second ACPI _LID poll.
    After resuming from S4 hibernation on AMD Ryzen 3500U (Picasso), pinctrl_amd
    edge-triggered GPIO interrupts (IRQ 68 ACPI:Event / IRQ 98 ACPI EC) can stop
    firing, preventing kernel input/UPower/logind from emitting LidClosed signals
    on subsequent lid closes. Directly reading /proc/acpi/button/lid/LID0/state
    evaluates the ACPI _LID method in ~3ms and reliably detects lid closure.
    """
    global lid_closed_poll_streak, last_polled_lid_closed, lid_closed_retry_count
    closed = is_acpi_lid_closed()
    if closed:
        lid_closed_poll_streak += 1
        if not last_polled_lid_closed:
            last_polled_lid_closed = True
            log(f"ACPI _LID poll detected lid CLOSED (streak={lid_closed_poll_streak}) | {get_system_snapshot()}", "EVENT")
        if lid_closed_poll_streak >= 2 and not hibernate_in_flight:
            if lid_closed_retry_count >= 2:
                trigger_poweroff(bus, reason="Lid closed and max hibernation retries reached; powering off.")
            elif lid_closed_retry_count == 0:
                trigger_hibernate(bus, reason=f"ACPI _LID poll confirmed lid closed ({lid_closed_poll_streak * 2}s)")
    else:
        if last_polled_lid_closed:
            log(f"ACPI _LID poll detected lid OPENED | {get_system_snapshot()}", "EVENT")
        last_polled_lid_closed = False
        lid_closed_poll_streak = 0
        lid_closed_retry_count = 0
    return True


def periodic_heartbeat(bus):
    temps = get_hwmon_temps()
    cpu_temp_str = temps.get("k10temp", "0C").replace("C", "")
    try:
        cpu_temp = float(cpu_temp_str)
    except ValueError:
        cpu_temp = 0.0

    lid_closed = is_lid_currently_closed(bus)
    if lid_closed or cpu_temp >= 75.0:
        level = "WARN" if (lid_closed or cpu_temp >= 80.0) else "HEARTBEAT"
        log(f"Watchdog check (lid_closed={lid_closed}): {get_system_snapshot()}", level)
        if lid_closed and not hibernate_in_flight:
            trigger_hibernate(bus, reason="Heartbeat detected lid closed while awake")
    else:
        log(f"Heartbeat: {get_system_snapshot()}", "HEARTBEAT")
    return True


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    log("====================================================================", "START")
    log(f"Starting Lid-Hibernate & Black-Box Watchdog Daemon | {get_system_snapshot()}", "START")

    acquire_lid_inhibitor(bus)

    bus.add_signal_receiver(
        lambda iface, changed, inv: on_upower_properties_changed(bus, iface, changed, inv),
        signal_name="PropertiesChanged",
        dbus_interface="org.freedesktop.DBus.Properties",
        path="/org/freedesktop/UPower",
    )

    bus.add_signal_receiver(
        lambda iface, changed, inv: on_login1_properties_changed(bus, iface, changed, inv),
        signal_name="PropertiesChanged",
        dbus_interface="org.freedesktop.DBus.Properties",
        path="/org/freedesktop/login1",
    )

    bus.add_signal_receiver(
        lambda starting: on_prepare_for_sleep(starting, bus),
        signal_name="PrepareForSleep",
        dbus_interface="org.freedesktop.login1.Manager",
        path="/org/freedesktop/login1",
    )

    bus.add_signal_receiver(
        on_prepare_for_shutdown,
        signal_name="PrepareForShutdown",
        dbus_interface="org.freedesktop.login1.Manager",
        path="/org/freedesktop/login1",
    )

    # Fast 2-second ACPI _LID poll (bypasses dead pinctrl_amd edge IRQs after resume)
    GLib.timeout_add_seconds(2, poll_acpi_lid_state, bus)

    # Periodic 5-minute black-box heartbeat (and immediate thermal/lid watchdog)
    GLib.timeout_add_seconds(300, periodic_heartbeat, bus)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        log("Daemon stopped by user.", "STOP")
        sys.exit(0)


if __name__ == "__main__":
    main()
