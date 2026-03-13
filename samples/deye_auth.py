"""
deye_auth.py — Auto auth + device discovery with .env caching.

Usage:
    from deye_auth import get_session
    base_url, headers, device_sn = get_session()

The .env file must contain at minimum:
    DEYE_BASE_URL, DEYE_APP_ID, DEYE_APP_SECRET, DEYE_EMAIL, DEYE_PASSWORD
"""
import hashlib
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

# Always load from the .env file beside this script
ENV_PATH = Path(__file__).parent / '.env'
load_dotenv(ENV_PATH, override=True)

# One hour safety margin before token expiry
_TOKEN_MARGIN_SEC = 3600


def _hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode('utf-8')).hexdigest()


def _obtain_token(base_url: str, app_id: str, app_secret: str, email: str, password: str, company_id: str) -> dict:
    """Call /account/token and return the full response dict."""
    url = f"{base_url}/account/token?appId={app_id}"
    data = {
        "appSecret": app_secret,
        "email": email,
        "password": _hash_password(password),
        "companyId": company_id,
    }
    resp = requests.post(url, json=data, headers={"Content-Type": "application/json"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _discover_device_sn(base_url: str, headers: dict) -> str:
    """
    Auto-discover the first INVERTER serial number.
    Flow: /station/list  →  /station/device
    Returns the deviceSn string.
    """
    # Step 1: get station list
    resp = requests.post(f"{base_url}/station/list", headers=headers,
                         json={"page": 1, "size": 10}, timeout=15)
    resp.raise_for_status()
    station_data = resp.json()
    if not station_data.get('success'):
        raise RuntimeError(f"station/list failed: {station_data.get('msg')}")

    stations = station_data.get('stationList', [])
    if not stations:
        raise RuntimeError("No stations found on this account.")

    station_id = stations[0]['id']

    # Step 2: get devices for that station
    resp2 = requests.post(f"{base_url}/station/device", headers=headers,
                          json={"page": 1, "size": 20, "stationIds": [station_id]}, timeout=15)
    resp2.raise_for_status()
    device_data = resp2.json()
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


def get_session() -> tuple[str, dict, str]:
    """
    Return (base_url, headers, device_sn), refreshing token and/or
    discovering device SN as needed, and caching results to .env.
    """
    base_url  = os.environ['DEYE_BASE_URL'].rstrip('/')
    app_id    = os.environ['DEYE_APP_ID']
    app_secret = os.environ['DEYE_APP_SECRET']
    email     = os.environ['DEYE_EMAIL']
    password  = os.environ['DEYE_PASSWORD']
    company_id = os.environ.get('DEYE_COMPANY_ID', '0')

    # ---------- Token ----------
    cached_token    = os.environ.get('DEYE_TOKEN', '')
    expires_at      = int(os.environ.get('DEYE_TOKEN_EXPIRES_AT', '0'))
    needs_new_token = (not cached_token) or (time.time() + _TOKEN_MARGIN_SEC >= expires_at)

    if needs_new_token:
        print("🔑 Obtaining new token...")
        result = _obtain_token(base_url, app_id, app_secret, email, password, company_id)
        if not result.get('success'):
            raise RuntimeError(f"Auth failed: {result.get('msg')} (code={result.get('code')})")

        cached_token = result['accessToken']
        expires_in   = int(result.get('expiresIn', 86400))
        expires_at   = int(time.time()) + expires_in

        set_key(str(ENV_PATH), 'DEYE_TOKEN', cached_token)
        set_key(str(ENV_PATH), 'DEYE_TOKEN_EXPIRES_AT', str(expires_at))
        print(f"   ✅ Token cached (valid for {expires_in // 86400} days)")
    else:
        remaining = (expires_at - int(time.time())) // 86400
        print(f"🔑 Using cached token (expires in ~{remaining} days)")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'bearer {cached_token}',
    }

    # ---------- Device SN ----------
    device_sn = os.environ.get('DEYE_DEVICE_SN', '')

    if not device_sn:
        print("🔍 Discovering device serial number...")
        device_sn = _discover_device_sn(base_url, headers)
        set_key(str(ENV_PATH), 'DEYE_DEVICE_SN', device_sn)
        print(f"   ✅ Device SN cached: {device_sn}")
    else:
        print(f"📡 Using cached device SN: {device_sn}")

    return base_url, headers, device_sn
