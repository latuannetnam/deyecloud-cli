#!/usr/bin/env python3
"""Deye Cloud CLI — Zero-dependency inverter management."""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

# ── Section 1: .env Parser ─────────────────────────────
_DEFAULT_ENV_PATH = os.path.join(Path.home(), '.deye', '.env')


def _load_env(path: str) -> dict:
    """Read a .env file, return dict. Skip comments/blanks, split on first =, strip quotes."""
    env = {}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Strip surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                env[key] = value
    except FileNotFoundError:
        pass
    return env


def _save_env(path: str, updates: dict) -> None:
    """Update/add keys in a .env file, preserving comments and order."""
    lines = []
    seen = set()
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                raw = line.rstrip('\n').rstrip('\r')
                stripped = raw.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    if key in updates:
                        lines.append(f"{key}={updates[key]}")
                        seen.add(key)
                        continue
                lines.append(raw)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)

    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')


# ── Section 2: HTTP Client ─────────────────────────────
_TIMEOUT = 15


def _http_post(url: str, payload: dict, headers: dict) -> dict:
    """POST JSON, return parsed response dict."""
    data = json.dumps(payload).encode('utf-8')
    hdrs = {**headers, 'Content-Type': 'application/json'}
    req = Request(url, data=data, headers=hdrs, method='POST')
    with urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def _http_get(url: str, headers: dict) -> dict:
    """GET request, return parsed response dict."""
    req = Request(url, headers=headers, method='GET')
    with urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


# ── Section 3: Auth Module ─────────────────────────────
_TOKEN_MARGIN_SEC = 3600  # 1 hour safety margin before token expiry


def _hash_password(plain: str) -> str:
    """SHA256 hash of password string."""
    return hashlib.sha256(plain.encode('utf-8')).hexdigest()


def _obtain_token(base_url: str, app_id: str, app_secret: str,
                  email: str, password: str, company_id: str) -> dict:
    """Call /account/token and return the full response dict."""
    url = f"{base_url}/account/token?appId={app_id}"
    payload = {
        "appSecret": app_secret,
        "email": email,
        "password": _hash_password(password),
        "companyId": company_id,
    }
    return _http_post(url, payload, {"Content-Type": "application/json"})


def _discover_device(base_url: str, headers: dict) -> str:
    """Auto-discover the first INVERTER serial number via station/list → station/device."""
    # Step 1: get station list
    station_data = _http_post(f"{base_url}/station/list", {"page": 1, "size": 10}, headers)
    if not station_data.get('success'):
        raise RuntimeError(f"station/list failed: {station_data.get('msg')}")

    stations = station_data.get('stationList', [])
    if not stations:
        raise RuntimeError("No stations found on this account.")

    station_id = stations[0]['id']

    # Step 2: get devices for that station
    device_data = _http_post(
        f"{base_url}/station/device",
        {"page": 1, "size": 20, "stationIds": [station_id]},
        headers,
    )
    if not device_data.get('success'):
        raise RuntimeError(f"station/device failed: {device_data.get('msg')}")

    devices = device_data.get('deviceListItems', [])
    # Prefer INVERTER, fall back to first device
    for dev in devices:
        if dev.get('deviceType') == 'INVERTER':
            return dev['deviceSn']
    if devices:
        return devices[0]['deviceSn']
    raise RuntimeError("No devices found under station.")


def get_session(env_path: str = None) -> tuple:
    """Return (base_url, headers, device_sn), refreshing token and discovering device as needed."""
    env_path = env_path or _DEFAULT_ENV_PATH
    env = _load_env(env_path)

    base_url = env.get('DEYE_BASE_URL', '').rstrip('/')
    app_id = env.get('DEYE_APP_ID', '')
    app_secret = env.get('DEYE_APP_SECRET', '')
    email = env.get('DEYE_EMAIL', '')
    password = env.get('DEYE_PASSWORD', '')
    company_id = env.get('DEYE_COMPANY_ID', '0')

    if not all([base_url, app_id, app_secret, email, password]):
        raise RuntimeError(
            "Missing credentials. Run 'deye_cli.py setup' to configure ~/.deye/.env"
        )

    # ---------- Token ----------
    cached_token = env.get('DEYE_TOKEN', '')
    expires_at = int(env.get('DEYE_TOKEN_EXPIRES_AT', '0'))
    needs_new_token = (not cached_token) or (time.time() + _TOKEN_MARGIN_SEC >= expires_at)

    if needs_new_token:
        print("🔑 Obtaining new token...", file=sys.stderr)
        result = _obtain_token(base_url, app_id, app_secret, email, password, company_id)
        if not result.get('success'):
            raise RuntimeError(f"Auth failed: {result.get('msg')} (code={result.get('code')})")

        cached_token = result['accessToken']
        expires_in = int(result.get('expiresIn', 86400))
        expires_at = int(time.time()) + expires_in

        _save_env(env_path, {
            'DEYE_TOKEN': cached_token,
            'DEYE_TOKEN_EXPIRES_AT': str(expires_at),
        })
        print(f"   ✅ Token cached (valid for {expires_in // 86400} days)", file=sys.stderr)
    else:
        remaining = (expires_at - int(time.time())) // 86400
        print(f"🔑 Using cached token (expires in ~{remaining} days)", file=sys.stderr)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'bearer {cached_token}',
    }

    # ---------- Device SN ----------
    device_sn = env.get('DEYE_DEVICE_SN', '')

    if not device_sn:
        print("🔍 Discovering device serial number...", file=sys.stderr)
        device_sn = _discover_device(base_url, headers)
        _save_env(env_path, {'DEYE_DEVICE_SN': device_sn})
        print(f"   ✅ Device SN cached: {device_sn}", file=sys.stderr)
    else:
        print(f"📡 Using cached device SN: {device_sn}", file=sys.stderr)

    return base_url, headers, device_sn


# ── Section 7: Output Formatting ───────────────────────
_LOCAL_TZ = timezone(timedelta(hours=7))  # UTC+7


def _format_timestamp(raw) -> str:
    """Convert Unix timestamp to readable local time."""
    try:
        return datetime.fromtimestamp(int(raw), tz=_LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return str(raw)


def _json_output(success: bool, command: str, device_sn: str,
                 data=None, error=None, api_code=None, api_msg=None):
    """Print structured JSON output."""
    out = {
        "success": success,
        "command": command,
        "device_sn": device_sn,
        "timestamp": datetime.now(tz=_LOCAL_TZ).isoformat(),
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


# ── Section 8: CLI Entry Point ─────────────────────────
import argparse

_ENV_TEMPLATE = """\
# Deye Cloud credentials
DEYE_BASE_URL=https://api.deye.com.cn/v1
DEYE_APP_ID=
DEYE_APP_SECRET=
DEYE_EMAIL=
DEYE_PASSWORD=
DEYE_COMPANY_ID=0

# Auto-cached (do not edit manually)
# DEYE_TOKEN=
# DEYE_TOKEN_EXPIRES_AT=
# DEYE_DEVICE_SN=
"""


def cmd_setup(args):
    """Create or validate ~/.deye/.env credentials file."""
    env_path = args.env_path
    env = _load_env(env_path)

    if env.get('DEYE_APP_ID') and env.get('DEYE_EMAIL'):
        if args.json:
            _json_output(True, "setup", "", data={
                "status": "already_configured",
                "env_path": env_path,
                "keys_found": list(env.keys()),
            })
        else:
            _human_output("Setup", {
                "Status": "Already configured",
                "Env path": env_path,
                "Keys found": ", ".join(env.keys()),
            })
        return

    # Create template
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    with open(env_path, 'w', encoding='utf-8') as fh:
        fh.write(_ENV_TEMPLATE)

    if args.json:
        _json_output(True, "setup", "", data={
            "status": "template_created",
            "env_path": env_path,
            "message": "Edit the .env file with your Deye Cloud credentials.",
        })
    else:
        _human_output("Setup", {
            "Status": "Template created",
            "Env path": env_path,
            "Next step": "Edit the .env file with your Deye Cloud credentials.",
        })


# ── Section 4: Monitor Commands ─────────────────────────

def _get_device_sn(args):
    """Resolve device SN from --device-sn flag or session auto-discovery."""
    base_url, headers, device_sn = get_session(env_path=args.env_path)
    if args.device_sn:
        device_sn = args.device_sn
    return base_url, headers, device_sn


def cmd_status(args):
    """Fetch latest device data (PV, battery, grid, consumption)."""
    base_url, headers, device_sn = _get_device_sn(args)
    result = _http_post(f"{base_url}/device/latest",
                        {"deviceList": [device_sn]}, headers)
    if not result.get('success'):
        if args.json:
            _json_output(False, "status", device_sn,
                        error=result.get('msg'), api_code=result.get('code'))
        else:
            print(f"Error: {result.get('msg')}")
        return

    # Parse data points
    data_points = {}
    for dev in result.get('deviceDataList', []):
        if dev['deviceSn'] == device_sn:
            for point in dev.get('dataList', []):
                data_points[point['key']] = f"{point['value']} {point.get('unit', '')}".strip()

    if args.json:
        _json_output(True, "status", device_sn, data=data_points)
    else:
        _human_output(f"Status — {device_sn}", data_points)


def cmd_devices(args):
    """List all devices across all stations."""
    base_url, headers, device_sn = _get_device_sn(args)
    # Get stations
    station_data = _http_post(f"{base_url}/station/list",
                              {"page": 1, "size": 100}, headers)
    if not station_data.get('success'):
        if args.json:
            _json_output(False, "devices", device_sn,
                        error=station_data.get('msg'), api_code=station_data.get('code'))
        else:
            print(f"Error: {station_data.get('msg')}")
        return

    stations = station_data.get('stationList', [])
    all_devices = []
    for station in stations:
        dev_data = _http_post(f"{base_url}/station/device",
                              {"page": 1, "size": 100, "stationIds": [station['id']]}, headers)
        if dev_data.get('success'):
            for dev in dev_data.get('deviceListItems', []):
                dev['stationName'] = station.get('name', '')
                all_devices.append(dev)

    if args.json:
        _json_output(True, "devices", device_sn, data={
            "stations": len(stations),
            "devices": all_devices,
        })
    else:
        _human_output(f"Devices ({len(all_devices)} total)", {
            dev.get('deviceSn', 'unknown'): f"{dev.get('deviceType', '')} @ {dev.get('stationName', '')}"
            for dev in all_devices
        })


def cmd_measure_points(args):
    """List available measure points for the device."""
    base_url, headers, device_sn = _get_device_sn(args)
    result = _http_post(f"{base_url}/device/measurePoints",
                        {"deviceSn": device_sn}, headers)
    if not result.get('success'):
        if args.json:
            _json_output(False, "measure-points", device_sn,
                        error=result.get('msg'), api_code=result.get('code'))
        else:
            print(f"Error: {result.get('msg')}")
        return

    points = result.get('measurePoints', [])
    device_type = result.get('deviceType', 'DEVICE')
    product_id = result.get('productId', '')

    if args.json:
        _json_output(True, "measure-points", device_sn, data={
            "deviceType": device_type,
            "productId": product_id,
            "count": len(points),
            "measurePoints": sorted(points),
        })
    else:
        _human_output(f"Measure Points — {device_sn} ({device_type})", {
            "Product ID": product_id,
            "Total available": len(points),
            "Points": ", ".join(sorted(points)),
        })


# ── Section 5: History & Alert Commands ─────────────────

def cmd_history(args):
    """Fetch device history data with granularity control."""
    base_url, headers, device_sn = _get_device_sn(args)
    payload = {
        'deviceSn': device_sn,
        'granularity': args.granularity,
        'startAt': args.start,
        'endAt': args.end,
    }
    if args.points:
        payload['measurePoints'] = [p.strip() for p in args.points.split(',')]

    result = _http_post(f"{base_url}/device/history", payload, headers)
    if not result.get('success'):
        if args.json:
            _json_output(False, "history", device_sn,
                        error=result.get('msg'), api_code=result.get('code'))
        else:
            print(f"Error: {result.get('msg')}")
        return

    records = []
    for row in result.get('dataList', []):
        t = _format_timestamp(row.get('time', row.get('collectTime', '')))
        items = {it['key']: f"{it['value']} {it.get('unit', '')}" for it in row.get('itemList', [])}
        records.append({"time": t, **items})

    if args.json:
        _json_output(True, "history", device_sn, data={
            "granularity": args.granularity,
            "period": f"{args.start} to {args.end}",
            "count": len(records),
            "records": records,
        })
    else:
        gran_labels = {1: 'Intraday (5-min)', 2: 'Daily', 3: 'Monthly'}
        _human_output(
            f"History — {device_sn} — {gran_labels.get(args.granularity, args.granularity)}",
            {"Period": f"{args.start} to {args.end}", "Records": len(records)},
        )
        for rec in records:
            parts = ' | '.join(f"{k}: {v}" for k, v in rec.items() if k != 'time')
            print(f"  {rec['time']}  {parts}")


def cmd_history_raw(args):
    """Fetch raw history JSON without formatting."""
    base_url, headers, device_sn = _get_device_sn(args)
    payload = {
        'deviceSn': device_sn,
        'granularity': args.granularity,
        'startAt': args.start,
        'endAt': args.end,
    }
    if args.points:
        payload['measurePoints'] = [p.strip() for p in args.points.split(',')]

    result = _http_post(f"{base_url}/device/history", payload, headers)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_alerts(args):
    """Fetch device alerts/warnings."""
    base_url, headers, device_sn = _get_device_sn(args)
    result = _http_post(f"{base_url}/device/alert/list", {
        "deviceSn": device_sn,
        "page": 1,
        "size": 50,
    }, headers)
    if not result.get('success'):
        if args.json:
            _json_output(False, "alerts", device_sn,
                        error=result.get('msg'), api_code=result.get('code'))
        else:
            print(f"Error: {result.get('msg')}")
        return

    alerts = result.get('alertList', [])
    if args.json:
        _json_output(True, "alerts", device_sn, data={
            "count": len(alerts),
            "alerts": alerts,
        })
    else:
        _human_output(f"Alerts — {device_sn}", {"Count": len(alerts)})
        for alert in alerts:
            print(f"  [{alert.get('alertLevel', '?')}] {alert.get('alertMsg', '')} "
                  f"({_format_timestamp(alert.get('alertTime', ''))})")


def cmd_order_status(args):
    """Check the status of a control order by ID."""
    base_url, headers, device_sn = _get_device_sn(args)
    result = _http_post(f"{base_url}/order/status", {
        "orderId": args.order_id,
    }, headers)
    if args.json:
        if result.get('success'):
            _json_output(True, "order-status", device_sn, data=result)
        else:
            _json_output(False, "order-status", device_sn,
                        error=result.get('msg'), api_code=result.get('code'))
    else:
        if result.get('success'):
            _human_output(f"Order Status — {args.order_id}", {
                k: v for k, v in result.items() if k != 'success'
            })
        else:
            print(f"Error: {result.get('msg')}")


def _build_parser():
    """Build the argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog='deye_cli',
        description='Deye Cloud CLI — Zero-dependency inverter management.',
    )
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    parser.add_argument('--device-sn', default=None, help='Override device serial number')
    parser.add_argument('--env-path', default=_DEFAULT_ENV_PATH, help='Path to .env file')

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
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
