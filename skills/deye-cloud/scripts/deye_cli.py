#!/usr/bin/env python3
"""Deye Cloud CLI — Zero-dependency inverter management.

This is a thin CLI wrapper over deye_core. All business logic lives in deye_core.py.
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

from deye_core import (
    DEFAULT_ENV_PATH, LOCAL_TZ,
    load_env, save_env, http_post, http_get, hash_password,
    obtain_token, discover_device, get_session, format_timestamp,
    get_status, get_devices, get_history, get_alerts, get_config,
    run_control, check_setup, get_order_status,
)


# ── Output Formatting (CLI-specific — prints to stdout) ─

def _json_output(success: bool, command: str, device_sn: str,
                 data=None, error=None, api_code=None, api_msg=None):
    """Print structured JSON output."""
    out = {
        "success": success,
        "command": command,
        "device_sn": device_sn,
        "timestamp": datetime.now(tz=LOCAL_TZ).isoformat(),
    }
    if success:
        out["data"] = data
    else:
        out["error"] = error
        if api_code:
            out["api_code"] = api_code
        if api_msg:
            out["api_msg"] = api_msg
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _human_output(title: str, data: dict, indent: int = 0):
    """Print human-readable formatted output."""
    prefix = "  " * indent
    print(f"\n{prefix}{'='*60}")
    print(f"{prefix}  {title}")
    print(f"{prefix}{'='*60}")
    for key, val in data.items():
        if isinstance(val, dict):
            print(f"{prefix}  {key}:")
            for k2, v2 in val.items():
                print(f"{prefix}    {k2}: {v2}")
        else:
            print(f"{prefix}  {key}: {val}")


# ── CLI Command Handlers ───────────────────────────────

def cmd_setup(args):
    """Create or validate ~/.deye/.env credentials file."""
    result = check_setup(env_path=args.env_path)
    if args.json:
        _json_output(True, "setup", "", data=result.get("data"))
    else:
        status = result["data"]["status"]
        if status == "already_configured":
            _human_output("Setup", {
                "Status": "Already configured",
                "Env path": result["data"]["env_path"],
                "Keys found": ", ".join(result["data"]["keys_found"]),
            })
        else:
            _human_output("Setup", {
                "Status": "Template created",
                "Env path": result["data"]["env_path"],
                "Next step": result["data"].get("message", "Edit the .env file with your Deye Cloud credentials."),
            })


def cmd_status(args):
    """Fetch latest device data (PV, battery, grid, consumption)."""
    result = get_status(device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "status", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"),
                     api_code=result.get("api_code"))
    else:
        if result["success"]:
            _human_output(f"Status — {result['device_sn']}", result["data"])
        else:
            print(f"Error: {result['error']}")


def cmd_devices(args):
    """List all devices across all stations."""
    result = get_devices(command="list_devices", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "devices", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            devices = result["data"]["devices"]
            _human_output(f"Devices ({len(devices)} total)", {
                dev.get('deviceSn', 'unknown'): f"{dev.get('deviceType', '')} @ {dev.get('stationName', '')}"
                for dev in devices
            })
        else:
            print(f"Error: {result['error']}")


def cmd_measure_points(args):
    """List available measure points for the device."""
    result = get_devices(command="measure_points", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "measure-points", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            data = result["data"]
            _human_output(f"Measure Points — {result['device_sn']} ({data['deviceType']})", {
                "Product ID": data["productId"],
                "Total available": data["count"],
                "Points": ", ".join(data["measurePoints"]),
            })
        else:
            print(f"Error: {result['error']}")


def cmd_history(args):
    """Fetch device history data with granularity control."""
    result = get_history(
        granularity=args.granularity, start=args.start, end=args.end,
        measure_points=args.points, device_sn=args.device_sn, env_path=args.env_path,
    )
    if args.json:
        _json_output(result["success"], "history", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            data = result["data"]
            gran_labels = {1: 'Intraday (5-min)', 2: 'Daily', 3: 'Monthly'}
            _human_output(
                f"History — {result['device_sn']} — {gran_labels.get(data.get('granularity'), data.get('granularity'))}",
                {"Period": data["period"], "Records": data["count"]},
            )
            for rec in data["records"]:
                parts = ' | '.join(f"{k}: {v}" for k, v in rec.items() if k != 'time')
                print(f"  {rec['time']}  {parts}")
        else:
            print(f"Error: {result['error']}")


def cmd_history_raw(args):
    """Fetch raw history JSON without formatting."""
    result = get_history(
        granularity=args.granularity, start=args.start, end=args.end,
        measure_points=args.points, raw=True, device_sn=args.device_sn, env_path=args.env_path,
    )
    if result["success"]:
        print(json.dumps(result["data"], indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_alerts(args):
    """Fetch device alerts/warnings."""
    result = get_alerts(device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "alerts", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            data = result["data"]
            _human_output(f"Alerts — {result['device_sn']}", {"Count": data["count"]})
            for alert in data["alerts"]:
                print(f"  [{alert.get('alertLevel', '?')}] {alert.get('alertMsg', '')} "
                      f"({format_timestamp(alert.get('alertTime', ''))})")
        else:
            print(f"Error: {result['error']}")


def cmd_order_status(args):
    """Check the status of a control order by ID."""
    result = get_order_status(order_id=args.order_id, device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        if result["success"]:
            _json_output(True, "order-status", result.get("device_sn", ""), data=result["data"])
        else:
            _json_output(False, "order-status", result.get("device_sn", ""),
                         error=result.get("error"), api_code=result.get("api_code"))
    else:
        if result["success"]:
            _human_output(f"Order Status — {args.order_id}", {
                k: v for k, v in result["data"].items() if k != 'success'
            })
        else:
            print(f"Error: {result['error']}")


# ── Station Commands ───────────────────────────────────

def cmd_station_list(args):
    """List all stations on the account."""
    result = get_devices(command="list_stations", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "station-list", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            stations = result["data"]["stations"]
            _human_output(f"Stations ({len(stations)} total)", {
                s.get('name', f"Station {s.get('id', '?')}"): f"ID={s.get('id')}"
                for s in stations
            })
        else:
            print(f"Error: {result['error']}")


def cmd_station_info(args):
    """Get detailed info about a station."""
    result = get_devices(command="station_info", station_id=args.station_id,
                         device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "station-info", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            _human_output(f"Station Info — {args.station_id}", result["data"])
        else:
            print(f"Error: {result['error']}")


def cmd_station_history(args):
    """Fetch station-level history data."""
    result = get_history(
        granularity=args.granularity, start=args.start, end=args.end,
        station_id=args.station_id, device_sn=args.device_sn, env_path=args.env_path,
    )
    if args.json:
        _json_output(result["success"], "station-history", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            _human_output(f"Station History — {args.station_id}", {
                "Period": f"{args.start} to {args.end}",
                "Records": result["data"]["count"],
            })
        else:
            print(f"Error: {result['error']}")


def cmd_station_alerts(args):
    """Fetch station-level alerts."""
    result = get_alerts(station_id=args.station_id, device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "station-alerts", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            data = result["data"]
            _human_output(f"Station Alerts — {args.station_id}", {"Count": data["count"]})
            for alert in data["alerts"]:
                print(f"  [{alert.get('alertLevel', '?')}] {alert.get('alertMsg', '')} "
                      f"({format_timestamp(alert.get('alertTime', ''))})")
        else:
            print(f"Error: {result['error']}")


# ── Config Commands (read-only settings) ───────────────

def cmd_config_battery(args):
    """Read battery configuration."""
    result = get_config(section="battery", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "config-battery", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            _human_output(f"config-battery — {result['device_sn']}", result["data"])
        else:
            print(f"Error: {result['error']}")


def cmd_config_system(args):
    """Read system work mode configuration."""
    result = get_config(section="system", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "config-system", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            _human_output(f"config-system — {result['device_sn']}", result["data"])
        else:
            print(f"Error: {result['error']}")


def cmd_config_tou(args):
    """Read Time-of-Use schedule configuration."""
    result = get_config(section="tou", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "config-tou", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            _human_output(f"config-tou — {result['device_sn']}", result["data"])
        else:
            print(f"Error: {result['error']}")


def cmd_dynamic_read(args):
    """Read all dynamic control parameters (two-step: send read → poll result)."""
    result = get_config(section="all", device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "dynamic-read", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            data = result["data"]
            _human_output(f"Dynamic Control Parameters — {result['device_sn']}",
                          data if isinstance(data, dict) else {"data": data})
        else:
            print(f"Error: {result['error']}")


# ── Control Commands (write operations) ────────────────

def _control_cmd_wrapper(args, action: str, command_name: str, params: dict):
    """Generic handler for control commands."""
    result = run_control(action=action, params=params, device_sn=args.device_sn, env_path=args.env_path)
    if result.get("success"):
        order_id = result["data"]["orderId"]
        if args.json:
            _json_output(True, command_name, result.get("device_sn", ""), data={
                "orderId": order_id,
                "message": f"Command sent. Track with: deye_cli.py order-status --order-id {order_id}",
            })
        else:
            _human_output(f"{command_name} — Sent", {
                "Order ID": order_id,
                "Track": f"deye_cli.py order-status --order-id {order_id}",
            })
    else:
        if args.json:
            _json_output(False, command_name, result.get("device_sn", ""),
                         error=result.get("error"), api_code=result.get("api_code"))
        else:
            print(f"Error: {result.get('error')}")


def cmd_set_work_mode(args):
    """Set system work mode."""
    _control_cmd_wrapper(args, "set_work_mode", "set-work-mode", {"mode": args.mode})


def cmd_set_solar_sell(args):
    """Enable/disable solar sell."""
    _control_cmd_wrapper(args, "set_solar_sell", "set-solar-sell", {"action": args.action})


def cmd_set_battery_param(args):
    """Set battery parameter."""
    _control_cmd_wrapper(args, "set_battery_param", "set-battery-param",
                         {"param": args.param, "value": args.value})


def cmd_set_battery_mode(args):
    """Enable/disable battery charge mode."""
    _control_cmd_wrapper(args, "set_battery_mode", "set-battery-mode",
                         {"mode": args.mode, "action": args.action})


def cmd_set_battery_type(args):
    """Set battery type."""
    _control_cmd_wrapper(args, "set_battery_type", "set-battery-type", {"type": args.type})


def cmd_set_tou(args):
    """Set TOU schedule."""
    settings = json.loads(args.settings)
    _control_cmd_wrapper(args, "set_tou", "set-tou", {"settings": settings})


def cmd_set_tou_switch(args):
    """Enable/disable TOU."""
    days = [d.strip() for d in args.days.split(',')] if args.days else []
    _control_cmd_wrapper(args, "set_tou_switch", "set-tou-switch",
                         {"action": args.action, "days": days})


def cmd_set_energy_pattern(args):
    """Set energy priority pattern."""
    _control_cmd_wrapper(args, "set_energy_pattern", "set-energy-pattern", {"pattern": args.pattern})


def cmd_set_power(args):
    """Set power limits."""
    _control_cmd_wrapper(args, "set_power", "set-power", {"type": args.type, "value": args.value})


def cmd_set_grid_peak_shaving(args):
    """Grid peak shaving control."""
    params = {"action": args.action}
    if args.power is not None:
        params["power"] = args.power
    _control_cmd_wrapper(args, "set_grid_peak_shaving", "set-grid-peak-shaving", params)


def cmd_set_smart_load(args):
    """Set smart load settings."""
    params = {}
    if args.on_soc is not None:
        params["on_soc"] = args.on_soc
    if args.off_soc is not None:
        params["off_soc"] = args.off_soc
    if args.on_voltage is not None:
        params["on_voltage"] = args.on_voltage
    if args.off_voltage is not None:
        params["off_voltage"] = args.off_voltage
    _control_cmd_wrapper(args, "set_smart_load", "set-smart-load", params)


def cmd_set_limit_control(args):
    """Set limit control function."""
    _control_cmd_wrapper(args, "set_limit_control", "set-limit-control", {"type": args.type})


def cmd_dynamic_control(args):
    """Set multiple dynamic control parameters at once."""
    params = {}
    if args.params:
        params = json.loads(args.params)
    _control_cmd_wrapper(args, "dynamic_control", "dynamic-control", params)


# ── CLI Parser ─────────────────────────────────────────

def _build_parser():
    """Build the argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog='deye_cli',
        description='Deye Cloud CLI — Zero-dependency inverter management.',
    )
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    parser.add_argument('--device-sn', default=None, help='Override device serial number')
    parser.add_argument('--env-path', default=DEFAULT_ENV_PATH, help='Path to .env file')

    subs = parser.add_subparsers(dest='command', help='Available commands')

    # setup
    subs.add_parser('setup', help='Create or validate credentials file')

    # monitor commands
    subs.add_parser('status', help='Fetch latest device data')
    subs.add_parser('devices', help='List all devices')
    subs.add_parser('measure-points', help='List available measure points')

    # history commands
    p_hist = subs.add_parser('history', help='Fetch device history')
    p_hist.add_argument('--granularity', type=int, default=1,
                        help='1=intraday(5min), 2=daily, 3=monthly')
    p_hist.add_argument('--start', required=True, help='Start date (YYYY-MM-DD or YYYY-MM)')
    p_hist.add_argument('--end', required=True, help='End date (YYYY-MM-DD or YYYY-MM)')
    p_hist.add_argument('--points', default=None, help='Comma-separated measure point keys')

    p_raw = subs.add_parser('history-raw', help='Fetch raw history JSON')
    p_raw.add_argument('--granularity', type=int, default=1)
    p_raw.add_argument('--start', required=True)
    p_raw.add_argument('--end', required=True)
    p_raw.add_argument('--points', default=None)

    subs.add_parser('alerts', help='Fetch device alerts')

    p_order = subs.add_parser('order-status', help='Check control order status')
    p_order.add_argument('--order-id', required=True, help='Order ID to check')

    # station commands
    subs.add_parser('station-list', help='List all stations')

    p_sinfo = subs.add_parser('station-info', help='Get station details')
    p_sinfo.add_argument('--station-id', type=int, required=True, help='Station ID')

    p_shist = subs.add_parser('station-history', help='Fetch station history')
    p_shist.add_argument('--station-id', type=int, required=True, help='Station ID')
    p_shist.add_argument('--granularity', type=int, default=2)
    p_shist.add_argument('--start', required=True)
    p_shist.add_argument('--end', required=True)

    p_salert = subs.add_parser('station-alerts', help='Fetch station alerts')
    p_salert.add_argument('--station-id', type=int, required=True, help='Station ID')

    # config commands
    subs.add_parser('config-battery', help='Read battery configuration')
    subs.add_parser('config-system', help='Read system work mode')
    subs.add_parser('config-tou', help='Read TOU schedule')
    subs.add_parser('dynamic-read', help='Read all dynamic control parameters')

    # control commands
    p_wm = subs.add_parser('set-work-mode', help='Set system work mode')
    p_wm.add_argument('--mode', required=True,
                       choices=['SELLING_FIRST', 'ZERO_EXPORT_TO_LOAD', 'ZERO_EXPORT_TO_CT'])

    p_ss = subs.add_parser('set-solar-sell', help='Enable/disable solar sell')
    p_ss.add_argument('--action', required=True, choices=['on', 'off'])

    p_bp = subs.add_parser('set-battery-param', help='Set battery parameter')
    p_bp.add_argument('--param', required=True,
                       choices=['MAX_CHARGE_CURRENT', 'MAX_DISCHARGE_CURRENT',
                                'GRID_CHARGE_AMPERE', 'BATT_LOW'])
    p_bp.add_argument('--value', type=int, required=True)

    p_bm = subs.add_parser('set-battery-mode', help='Set battery charge mode')
    p_bm.add_argument('--mode', required=True, choices=['GRID_CHARGE', 'GEN_CHARGE'])
    p_bm.add_argument('--action', required=True, choices=['on', 'off'])

    p_bt = subs.add_parser('set-battery-type', help='Set battery type')
    p_bt.add_argument('--type', required=True,
                       choices=['BATT_V', 'BATT_SOC', 'LI', 'NO_BATTERY'])

    p_tou = subs.add_parser('set-tou', help='Set TOU schedule')
    p_tou.add_argument('--settings', required=True, help='JSON string of TOU settings')

    p_ts = subs.add_parser('set-tou-switch', help='Enable/disable TOU')
    p_ts.add_argument('--action', required=True, choices=['on', 'off'])
    p_ts.add_argument('--days', default=None, help='Comma-separated days (MON,TUE,...)')

    p_ep = subs.add_parser('set-energy-pattern', help='Set energy priority')
    p_ep.add_argument('--pattern', required=True,
                       choices=['BATTERY_FIRST', 'LOAD_FIRST'])

    p_pw = subs.add_parser('set-power', help='Set power limits')
    p_pw.add_argument('--type', required=True,
                       choices=['MAX_SELL_POWER', 'MAX_SOLAR_POWER', 'ZERO_EXPORT_POWER'])
    p_pw.add_argument('--value', type=int, required=True)

    p_gps = subs.add_parser('set-grid-peak-shaving', help='Grid peak shaving')
    p_gps.add_argument('--action', required=True, choices=['on', 'off'])
    p_gps.add_argument('--power', type=int, default=None, help='Peak shaving power')

    p_sl = subs.add_parser('set-smart-load', help='Smart load settings')
    p_sl.add_argument('--on-soc', type=int, default=None)
    p_sl.add_argument('--off-soc', type=int, default=None)
    p_sl.add_argument('--on-voltage', type=float, default=None)
    p_sl.add_argument('--off-voltage', type=float, default=None)

    p_lc = subs.add_parser('set-limit-control', help='Set limit control')
    p_lc.add_argument('--type', required=True,
                       choices=['SELL_FIRST', 'ZERO_EXPORT_TO_UPS_LOAD',
                                'ZERO_EXPORT_TO_CT', 'ZERO_EXPORT_TO_WIRELESS_CT'])

    p_dc = subs.add_parser('dynamic-control', help='Set dynamic control parameters')
    p_dc.add_argument('--params', required=True, help='JSON string of parameters')

    return parser, subs


def main():
    """CLI entry point."""
    parser, subs = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        'setup': cmd_setup,
        'status': cmd_status,
        'devices': cmd_devices,
        'measure-points': cmd_measure_points,
        'history': cmd_history,
        'history-raw': cmd_history_raw,
        'alerts': cmd_alerts,
        'order-status': cmd_order_status,
        'station-list': cmd_station_list,
        'station-info': cmd_station_info,
        'station-history': cmd_station_history,
        'station-alerts': cmd_station_alerts,
        'config-battery': cmd_config_battery,
        'config-system': cmd_config_system,
        'config-tou': cmd_config_tou,
        'dynamic-read': cmd_dynamic_read,
        'set-work-mode': cmd_set_work_mode,
        'set-solar-sell': cmd_set_solar_sell,
        'set-battery-param': cmd_set_battery_param,
        'set-battery-mode': cmd_set_battery_mode,
        'set-battery-type': cmd_set_battery_type,
        'set-tou': cmd_set_tou,
        'set-tou-switch': cmd_set_tou_switch,
        'set-energy-pattern': cmd_set_energy_pattern,
        'set-power': cmd_set_power,
        'set-grid-peak-shaving': cmd_set_grid_peak_shaving,
        'set-smart-load': cmd_set_smart_load,
        'set-limit-control': cmd_set_limit_control,
        'dynamic-control': cmd_dynamic_control,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
