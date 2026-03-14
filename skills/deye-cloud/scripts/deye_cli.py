#!/usr/bin/env python3
"""Deye Cloud CLI — Zero-dependency inverter management."""

import hashlib
import json
import os
import sys
import time
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
