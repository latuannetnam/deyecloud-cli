#!/usr/bin/env python3
"""Deye Cloud Core — Shared business logic for CLI and MCP server.

This module contains all API interaction logic, returning dicts/lists
instead of printing. No argparse, no sys.exit, no print (except to stderr
for status messages in get_session).
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

# ── Constants ──────────────────────────────────────────
DEFAULT_ENV_PATH = os.path.join(Path.home(), '.deye', '.env')
TIMEOUT = 15
TOKEN_MARGIN_SEC = 3600  # 1 hour safety margin before token expiry
LOCAL_TZ = timezone(timedelta(hours=7))  # UTC+7


# ── .env Parser ────────────────────────────────────────

def load_env(path: str) -> dict:
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


def save_env(path: str, updates: dict) -> None:
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


# ── HTTP Client ────────────────────────────────────────

def http_post(url: str, payload: dict, headers: dict) -> dict:
    """POST JSON, return parsed response dict."""
    data = json.dumps(payload).encode('utf-8')
    hdrs = {**headers, 'Content-Type': 'application/json'}
    req = Request(url, data=data, headers=hdrs, method='POST')
    with urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def http_get(url: str, headers: dict) -> dict:
    """GET request, return parsed response dict."""
    req = Request(url, headers=headers, method='GET')
    with urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


# ── Auth Module ────────────────────────────────────────

def hash_password(plain: str) -> str:
    """SHA256 hash of password string."""
    return hashlib.sha256(plain.encode('utf-8')).hexdigest()


def obtain_token(base_url: str, app_id: str, app_secret: str,
                 email: str, password: str, company_id: str) -> dict:
    """Call /account/token and return the full response dict."""
    url = f"{base_url}/account/token?appId={app_id}"
    payload = {
        "appSecret": app_secret,
        "email": email,
        "password": hash_password(password),
        "companyId": company_id,
    }
    return http_post(url, payload, {"Content-Type": "application/json"})


def discover_device(base_url: str, headers: dict) -> str:
    """Auto-discover the first INVERTER serial number via station/list → station/device."""
    # Step 1: get station list
    station_data = http_post(f"{base_url}/station/list", {"page": 1, "size": 10}, headers)
    if not station_data.get('success'):
        raise RuntimeError(f"station/list failed: {station_data.get('msg')}")

    stations = station_data.get('stationList', [])
    if not stations:
        raise RuntimeError("No stations found on this account.")

    station_id = stations[0]['id']

    # Step 2: get devices for that station
    device_data = http_post(
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
    env_path = env_path or DEFAULT_ENV_PATH
    env = load_env(env_path)

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
    needs_new_token = (not cached_token) or (time.time() + TOKEN_MARGIN_SEC >= expires_at)

    if needs_new_token:
        print("🔑 Obtaining new token...", file=sys.stderr)
        result = obtain_token(base_url, app_id, app_secret, email, password, company_id)
        if not result.get('success'):
            raise RuntimeError(f"Auth failed: {result.get('msg')} (code={result.get('code')})")

        cached_token = result['accessToken']
        expires_in = int(result.get('expiresIn', 86400))
        expires_at = int(time.time()) + expires_in

        save_env(env_path, {
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
        device_sn = discover_device(base_url, headers)
        save_env(env_path, {'DEYE_DEVICE_SN': device_sn})
        print(f"   ✅ Device SN cached: {device_sn}", file=sys.stderr)
    else:
        print(f"📡 Using cached device SN: {device_sn}", file=sys.stderr)

    return base_url, headers, device_sn


# ── Timestamp Formatting ───────────────────────────────

def format_timestamp(raw) -> str:
    """Convert Unix timestamp to readable local time."""
    try:
        return datetime.fromtimestamp(int(raw), tz=LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return str(raw)


# ── Public API Functions (return dicts, never print) ───

def get_status(device_sn=None, env_path=None):
    """Return current device status as dict."""
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    result = http_post(f"{base_url}/device/latest", {"deviceList": [sn]}, headers)
    if not result.get('success'):
        return {"success": False, "device_sn": sn, "error": result.get('msg'), "api_code": result.get('code'),
                "suggested_actions": ["Run deye_setup to verify credentials", "Check network connectivity"]}
    data_points = {}
    for dev in result.get('deviceDataList', []):
        if dev['deviceSn'] == sn:
            for point in dev.get('dataList', []):
                data_points[point['key']] = f"{point['value']} {point.get('unit', '')}".strip()
    return {"success": True, "device_sn": sn, "data": data_points}


def get_devices(command="list_devices", station_id=None, device_sn=None, env_path=None):
    """Return device/station list as dict."""
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    if command == "list_stations":
        result = http_post(f"{base_url}/station/list", {"page": 1, "size": 100}, headers)
        if not result.get('success'):
            return {"success": False, "device_sn": sn, "error": result.get('msg'),
                    "suggested_actions": ["Run deye_setup to verify credentials"]}
        return {"success": True, "device_sn": sn, "data": {"stations": result.get('stationList', [])}}
    elif command == "station_info":
        if not station_id:
            return {"success": False, "device_sn": sn, "error": "station_id is required for station_info",
                    "suggested_actions": ["Call with command='list_stations' first to find station IDs"]}
        result = http_post(f"{base_url}/station/info", {"stationId": station_id}, headers)
        if not result.get('success'):
            return {"success": False, "device_sn": sn, "error": result.get('msg'),
                    "suggested_actions": ["Verify station_id with command='list_stations'"]}
        data = {k: v for k, v in result.items() if k not in ('success', 'code', 'msg')}
        return {"success": True, "device_sn": sn, "data": data}
    elif command == "measure_points":
        result = http_post(f"{base_url}/device/measurePoints", {"deviceSn": sn}, headers)
        if not result.get('success'):
            return {"success": False, "device_sn": sn, "error": result.get('msg'),
                    "suggested_actions": ["Verify device is online with deye_status"]}
        return {"success": True, "device_sn": sn, "data": {
            "deviceType": result.get('deviceType', 'DEVICE'),
            "productId": result.get('productId', ''),
            "count": len(result.get('measurePoints', [])),
            "measurePoints": sorted(result.get('measurePoints', [])),
        }}
    else:  # list_devices
        station_data = http_post(f"{base_url}/station/list", {"page": 1, "size": 100}, headers)
        if not station_data.get('success'):
            return {"success": False, "device_sn": sn, "error": station_data.get('msg'),
                    "suggested_actions": ["Run deye_setup to verify credentials"]}
        stations = station_data.get('stationList', [])
        all_devices = []
        for station in stations:
            dev_data = http_post(f"{base_url}/station/device",
                                 {"page": 1, "size": 100, "stationIds": [station['id']]}, headers)
            if dev_data.get('success'):
                for dev in dev_data.get('deviceListItems', []):
                    dev['stationName'] = station.get('name', '')
                    all_devices.append(dev)
        return {"success": True, "device_sn": sn, "data": {"stations": len(stations), "devices": all_devices}}


def get_history(granularity, start, end, measure_points=None, station_id=None,
                raw=False, device_sn=None, env_path=None):
    """Return history data as dict."""
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    # Map string granularity to int
    gran_map = {"intraday": 1, "daily": 2, "monthly": 3}
    gran = gran_map.get(granularity, granularity) if isinstance(granularity, str) else granularity

    if station_id:
        result = http_post(f"{base_url}/station/history", {
            "stationId": station_id, "granularity": gran, "startAt": start, "endAt": end,
        }, headers)
        if not result.get('success'):
            return {"success": False, "device_sn": sn, "error": result.get('msg'),
                    "suggested_actions": ["Verify station_id with deye_devices command='list_stations'"]}
        return {"success": True, "device_sn": sn, "data": {
            "stationId": station_id, "count": len(result.get('dataList', [])),
            "records": result.get('dataList', []),
        }}

    payload = {'deviceSn': sn, 'granularity': gran, 'startAt': start, 'endAt': end}
    if measure_points:
        payload['measurePoints'] = [p.strip() for p in measure_points.split(',')]
    result = http_post(f"{base_url}/device/history", payload, headers)
    if raw:
        return {"success": True, "device_sn": sn, "data": result}
    if not result.get('success'):
        return {"success": False, "device_sn": sn, "error": result.get('msg'),
                "suggested_actions": ["Check date format (YYYY-MM-DD for intraday/daily, YYYY-MM for monthly)"]}
    records = []
    for row in result.get('dataList', []):
        t = format_timestamp(row.get('time', row.get('collectTime', '')))
        items = {it['key']: f"{it['value']} {it.get('unit', '')}" for it in row.get('itemList', [])}
        records.append({"time": t, **items})
    return {"success": True, "device_sn": sn, "data": {
        "granularity": gran, "period": f"{start} to {end}",
        "count": len(records), "records": records,
    }}


def get_alerts(station_id=None, device_sn=None, env_path=None):
    """Return alerts as dict."""
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    if station_id:
        result = http_post(f"{base_url}/station/alert/list", {
            "stationId": station_id, "page": 1, "size": 50,
        }, headers)
    else:
        result = http_post(f"{base_url}/device/alert/list", {
            "deviceSn": sn, "page": 1, "size": 50,
        }, headers)
    if not result.get('success'):
        return {"success": False, "device_sn": sn, "error": result.get('msg'),
                "suggested_actions": ["Run deye_setup to verify credentials"]}
    return {"success": True, "device_sn": sn, "data": {
        "count": len(result.get('alertList', [])),
        "alerts": result.get('alertList', []),
    }}


def get_config(section="all", device_sn=None, env_path=None):
    """Return config data as dict."""
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    endpoints = {
        "battery": "/config/battery",
        "system": "/config/system",
        "tou": "/config/tou",
    }
    if section == "all":
        # Use dynamic-read (two-step)
        read_result = http_post(f"{base_url}/strategy/dynamicControl/read", {"deviceSn": sn}, headers)
        if not read_result.get('success'):
            return {"success": False, "device_sn": sn, "error": read_result.get('msg'),
                    "suggested_actions": ["Verify device is online with deye_status"]}
        import time as _time
        for _ in range(5):
            _time.sleep(2)
            result = http_post(f"{base_url}/strategy/dynamicControl/readResult", {"deviceSn": sn}, headers)
            if result.get('success') and result.get('data'):
                return {"success": True, "device_sn": sn, "data": result.get('data', result)}
        return {"success": False, "device_sn": sn, "error": "Timeout waiting for dynamic read result",
                "suggested_actions": ["Device may be offline — try deye_status", "Retry in a few minutes"]}

    endpoint = endpoints.get(section)
    if not endpoint:
        return {"success": False, "device_sn": sn, "error": f"Unknown config section: {section}"}
    result = http_post(f"{base_url}{endpoint}", {"deviceSn": sn}, headers)
    if not result.get('success'):
        return {"success": False, "device_sn": sn, "error": result.get('msg'),
                "suggested_actions": ["Try section='all' to read via dynamic control"]}
    data = {k: v for k, v in result.items() if k not in ('success', 'code', 'msg', 'requestId')}
    return {"success": True, "device_sn": sn, "data": data}


# Control action → (endpoint, payload builder)
_CONTROL_ACTIONS = {
    "set_work_mode": ("/order/sys/workMode/update", lambda p: {"workMode": p["mode"]}),
    "set_solar_sell": ("/order/sys/solarSell/control", lambda p: {"solarSell": 1 if p.get("action") == "on" else 0}),
    "set_battery_param": ("/order/battery/parameter/update", lambda p: {"paramName": p["param"], "paramValue": p["value"]}),
    "set_battery_mode": ("/order/battery/modeControl", lambda p: {"chargeMode": p["mode"], "action": 1 if p.get("action") == "on" else 0}),
    "set_battery_type": ("/order/battery/type/update", lambda p: {"batteryType": p["type"]}),
    "set_tou": ("/order/sys/tou/update", lambda p: {"touSettings": p.get("settings", p)}),
    "set_tou_switch": ("/order/sys/tou/switch", lambda p: {"touSwitch": 1 if p.get("action") == "on" else 0, "days": p.get("days", [])}),
    "set_energy_pattern": ("/order/sys/energyPattern/update", lambda p: {"energyPattern": p["pattern"]}),
    "set_power": ("/order/sys/power/update", lambda p: {"powerType": p["type"], "powerValue": p["value"]}),
    "set_grid_peak_shaving": ("/order/gridPeakShaving/control", lambda p: {
        "gridPeakShaving": 1 if p.get("action") == "on" else 0,
        **({
            "peakShavingPower": p["power"]} if "power" in p else {}),
    }),
    "set_smart_load": ("/order/smartload/update", lambda p: {
        k: v for k, v in {
            "smartLoadOnSOC": p.get("on_soc"), "smartLoadOffSOC": p.get("off_soc"),
            "smartLoadOnVoltage": p.get("on_voltage"), "smartLoadOffVoltage": p.get("off_voltage"),
        }.items() if v is not None
    }),
    "set_limit_control": ("/order/sys/limitControl", lambda p: {"limitControlType": p["type"]}),
    "dynamic_control": ("/strategy/dynamicControl", lambda p: p),
}


def run_control(action, params, device_sn=None, env_path=None):
    """Execute a control command. Returns dict with orderId."""
    if action not in _CONTROL_ACTIONS:
        return {"success": False, "error": f"Unknown control action: {action}",
                "suggested_actions": [f"Valid actions: {', '.join(sorted(_CONTROL_ACTIONS.keys()))}"]}
    endpoint, build_payload = _CONTROL_ACTIONS[action]
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    payload = build_payload(params)
    payload["deviceSn"] = sn
    result = http_post(f"{base_url}{endpoint}", payload, headers)
    if result.get('success'):
        order_id = result.get('orderId', result.get('data', {}).get('orderId', 'N/A') if isinstance(result.get('data'), dict) else 'N/A')
        return {"success": True, "device_sn": sn, "data": {"orderId": order_id}}
    return {"success": False, "device_sn": sn, "error": result.get('msg'), "api_code": result.get('code'),
            "suggested_actions": ["Check params match the expected format for this action", "Use deye_config to read current settings first"]}


def check_setup(env_path=None):
    """Check or create credentials file. Returns dict."""
    env_path = env_path or DEFAULT_ENV_PATH
    env = load_env(env_path)
    if env.get('DEYE_APP_ID') and env.get('DEYE_EMAIL'):
        return {"success": True, "data": {
            "status": "already_configured",
            "env_path": env_path,
            "keys_found": list(env.keys()),
        }}
    import os as _os
    _os.makedirs(_os.path.dirname(env_path), exist_ok=True)
    with open(env_path, 'w', encoding='utf-8') as fh:
        fh.write(
            "# Deye Cloud credentials\n"
            "DEYE_BASE_URL=https://api.deye.com.cn/v1\n"
            "DEYE_APP_ID=\nDEYE_APP_SECRET=\n"
            "DEYE_EMAIL=\nDEYE_PASSWORD=\n"
            "DEYE_COMPANY_ID=0\n\n"
            "# Auto-cached (do not edit manually)\n"
            "# DEYE_TOKEN=\n# DEYE_TOKEN_EXPIRES_AT=\n# DEYE_DEVICE_SN=\n"
        )
    return {"success": True, "data": {
        "status": "template_created",
        "env_path": env_path,
        "message": "Edit the .env file with your Deye Cloud credentials.",
    }}


def get_order_status(order_id, device_sn=None, env_path=None):
    """Check control order status. Returns dict."""
    base_url, headers, sn = get_session(env_path=env_path)
    if device_sn:
        sn = device_sn
    result = http_post(f"{base_url}/order/status", {"orderId": order_id}, headers)
    if result.get('success'):
        return {"success": True, "device_sn": sn, "data": result}
    return {"success": False, "device_sn": sn, "error": result.get('msg'), "api_code": result.get('code'),
            "suggested_actions": ["Verify the orderId is correct", "Orders expire after a timeout period"]}
