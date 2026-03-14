# Deye Cloud MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an MCP server so the Deye Cloud skill works in Claude Desktop and other MCP clients, while keeping the existing CLI fully functional.

**Architecture:** Extract business logic from the monolithic `deye_cli.py` into `deye_core.py`, then build two thin wrappers: `deye_cli.py` (argparse, for Antigravity) and `deye_mcp.py` (FastMCP, 7 grouped tools, for Claude Desktop).

**Tech Stack:** Python 3.8+, `fastmcp` (Anthropic's official MCP SDK), stdlib (`urllib.request`, `hashlib`, `json`, `argparse`)

**Design doc:** `docs/plans/2026-03-14-mcp-server-design.md`

---

### Task 1: Install FastMCP Dependency

**Files:**
- Create: `requirements.txt`

**Step 1: Create requirements.txt**

```txt
fastmcp>=2.0.0
```

**Step 2: Install the dependency**

Run: `pip install fastmcp`
Expected: Successfully installed fastmcp and dependencies

**Step 3: Verify import works**

Run: `python -c "from fastmcp import FastMCP; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add fastmcp dependency"
```

---

### Task 2: Extract Core Library — `deye_core.py`

Extract all business logic from `deye_cli.py` into a reusable module. Every function must return data (dicts/lists) instead of printing. No argparse, no `sys.exit`, no `print`.

**Files:**
- Create: `skills/deye-cloud/scripts/deye_core.py`
- Test: `tests/test_core.py`

**Step 1: Write the failing tests**

Create `tests/test_core.py`:

```python
"""Tests for deye_core — shared business logic."""
import hashlib
import json
import os
import sys
import time
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))


class TestCoreEnvParser:
    """Verify _load_env and _save_env are available from deye_core."""

    def test_load_env_basic(self, tmp_path):
        from deye_core import load_env
        f = tmp_path / ".env"
        f.write_text("KEY1=value1\nKEY2=value2\n")
        result = load_env(str(f))
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_save_env_update(self, tmp_path):
        from deye_core import load_env, save_env
        f = tmp_path / ".env"
        f.write_text("KEY1=old\nKEY2=keep\n")
        save_env(str(f), {"KEY1": "new"})
        result = load_env(str(f))
        assert result["KEY1"] == "new"
        assert result["KEY2"] == "keep"


class TestCoreHttpClient:
    """Verify HTTP functions are available from deye_core."""

    @patch('deye_core.urlopen')
    def test_http_post(self, mock_urlopen):
        from deye_core import http_post
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"success": True}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = http_post("http://example.com/api", {"key": "val"}, {})
        assert result == {"success": True}


class TestCoreAuth:
    """Verify auth functions are available from deye_core."""

    def test_hash_password(self):
        from deye_core import hash_password
        result = hash_password("test123")
        assert result == hashlib.sha256(b"test123").hexdigest()

    def test_get_session_cached(self, tmp_path):
        from deye_core import get_session
        env = tmp_path / ".env"
        future = str(int(time.time()) + 7200)
        env.write_text(
            "DEYE_BASE_URL=http://base\n"
            "DEYE_APP_ID=aid\nDEYE_APP_SECRET=sec\n"
            "DEYE_EMAIL=e@m\nDEYE_PASSWORD=pw\n"
            "DEYE_COMPANY_ID=0\n"
            f"DEYE_TOKEN=cached_tok\nDEYE_TOKEN_EXPIRES_AT={future}\n"
            "DEYE_DEVICE_SN=12345\n"
        )
        base, headers, sn = get_session(env_path=str(env))
        assert headers["Authorization"] == "bearer cached_tok"
        assert sn == "12345"


class TestCoreMethods:
    """Verify core API methods return dicts (not print)."""

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_status(self, mock_session, mock_post):
        from deye_core import get_status
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "deviceDataList": [{
                "deviceSn": "SN123",
                "dataList": [
                    {"key": "SOC", "value": "85", "unit": "%"},
                ],
            }],
        }
        result = get_status(env_path="dummy")
        assert result["success"] is True
        assert "SOC" in result["data"]

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_devices(self, mock_session, mock_post):
        from deye_core import get_devices
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.side_effect = [
            {"success": True, "stationList": [{"id": 1, "name": "Home"}]},
            {"success": True, "deviceListItems": [
                {"deviceSn": "SN123", "deviceType": "INVERTER"},
            ]},
        ]
        result = get_devices(env_path="dummy")
        assert result["success"] is True

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_history(self, mock_session, mock_post):
        from deye_core import get_history
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "dataList": [
                {"time": "1710300000", "itemList": [
                    {"key": "SOC", "value": "85", "unit": "%"},
                ]},
            ],
        }
        result = get_history(granularity=1, start="2026-03-13", end="2026-03-13", env_path="dummy")
        assert result["success"] is True
        assert len(result["data"]["records"]) == 1

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_alerts(self, mock_session, mock_post):
        from deye_core import get_alerts
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "alertList": []}
        result = get_alerts(env_path="dummy")
        assert result["success"] is True

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_config(self, mock_session, mock_post):
        from deye_core import get_config
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "batteryCapacity": 5120}
        result = get_config(section="battery", env_path="dummy")
        assert result["success"] is True

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_run_control_returns_order_id(self, mock_session, mock_post):
        from deye_core import run_control
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "orderId": "ORD001"}
        result = run_control(action="set_solar_sell", params={"solarSell": 1}, env_path="dummy")
        assert result["success"] is True
        assert result["data"]["orderId"] == "ORD001"

    def test_check_setup_configured(self, tmp_path):
        from deye_core import check_setup
        env = tmp_path / ".env"
        env.write_text("DEYE_APP_ID=aid\nDEYE_EMAIL=e@m\n")
        result = check_setup(env_path=str(env))
        assert result["success"] is True
        assert result["data"]["status"] == "already_configured"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deye_core'`

**Step 3: Create `deye_core.py` with extracted logic**

Create `skills/deye-cloud/scripts/deye_core.py`. Extract the following sections from `deye_cli.py`, renaming private functions to public:

- `_load_env` → `load_env`
- `_save_env` → `save_env`
- `_http_post` → `http_post`
- `_http_get` → `http_get`
- `_hash_password` → `hash_password`
- `_obtain_token` → `obtain_token`
- `_discover_device` → `discover_device`
- `get_session` → `get_session` (keep public)
- `_format_timestamp` → `format_timestamp`
- `_DEFAULT_ENV_PATH` → `DEFAULT_ENV_PATH`
- `_TIMEOUT` → `TIMEOUT`
- `_TOKEN_MARGIN_SEC` → `TOKEN_MARGIN_SEC`
- `_LOCAL_TZ` → `LOCAL_TZ`

Then add **new public API functions** that return dicts (not print):

```python
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
        **({"peakShavingPower": p["power"]} if "power" in p else {}),
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add skills/deye-cloud/scripts/deye_core.py tests/test_core.py
git commit -m "feat: extract deye_core.py shared library with tests"
```

---

### Task 3: Rewrite `deye_cli.py` as Thin Wrapper

Replace the monolithic CLI with a thin wrapper that imports from `deye_core`.

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`
- Test: existing `tests/test_cli_commands.py`

**Step 1: Rewrite `deye_cli.py`**

The new `deye_cli.py` should:
1. Import everything from `deye_core`
2. Keep `_build_parser()` and `main()` for argparse
3. Each `cmd_*` function now calls core functions and handles JSON/human output formatting
4. Keep backward-compatible: same CLI interface, same output format

Key pattern for each command:
```python
from deye_core import get_status, get_devices, get_history, ...

def cmd_status(args):
    result = get_status(device_sn=args.device_sn, env_path=args.env_path)
    if args.json:
        _json_output(result["success"], "status", result.get("device_sn", ""),
                     data=result.get("data"), error=result.get("error"))
    else:
        if result["success"]:
            _human_output(f"Status — {result['device_sn']}", result["data"])
        else:
            print(f"Error: {result['error']}")
```

Keep `_json_output` and `_human_output` formatting functions in `deye_cli.py` since they are CLI-specific (they print to stdout).

**Step 2: Run existing CLI tests**

Run: `python -m pytest tests/test_cli_commands.py -v`
Expected: All tests PASS (may need mock path updates from `deye_cli._http_post` to `deye_core.http_post`)

**Step 3: Update mock paths in existing tests**

In `tests/test_cli_commands.py`, `tests/test_auth.py`, `tests/test_http_client.py`, and `tests/test_env_parser.py`:
- Update imports from `deye_cli` to `deye_core` for core functions
- Update `@patch('deye_cli._http_post')` to `@patch('deye_core.http_post')`
- Update `@patch('deye_cli.get_session')` to `@patch('deye_core.get_session')`

**Step 4: Run all existing tests to verify backward compatibility**

Run: `python -m pytest tests/ -v`
Expected: All 20+ tests PASS

**Step 5: Manual smoke test — CLI still works**

Run: `python skills/deye-cloud/scripts/deye_cli.py --json status`
Expected: Same JSON output as before (live API call or cached token error)

**Step 6: Commit**

```bash
git add skills/deye-cloud/scripts/deye_cli.py tests/
git commit -m "refactor: rewrite deye_cli.py as thin wrapper over deye_core"
```

---

### Task 4: Build MCP Server — `deye_mcp.py`

Create the FastMCP server with 7 grouped tools.

**Files:**
- Create: `skills/deye-cloud/scripts/deye_mcp.py`
- Test: `tests/test_mcp.py`

**Step 1: Write the failing tests**

Create `tests/test_mcp.py`:

```python
"""Tests for MCP server — tool registration, parameter validation, and error handling."""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))


class TestMcpToolRegistration:
    """Verify all 7 tools are registered."""

    def test_server_has_seven_tools(self):
        from deye_mcp import mcp
        tools = mcp._tool_manager._tools
        assert len(tools) == 7

    def test_expected_tool_names(self):
        from deye_mcp import mcp
        tool_names = set(mcp._tool_manager._tools.keys())
        expected = {"deye_status", "deye_history", "deye_devices",
                    "deye_alerts", "deye_config", "deye_control", "deye_setup"}
        assert tool_names == expected


class TestMcpStatusTool:
    """Verify deye_status tool calls core and returns structured result."""

    @patch('deye_core.get_session')
    @patch('deye_core.http_post')
    def test_status_returns_data(self, mock_post, mock_session):
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "deviceDataList": [{
                "deviceSn": "SN123",
                "dataList": [{"key": "SOC", "value": "85", "unit": "%"}],
            }],
        }
        from deye_mcp import deye_status
        import asyncio
        result = asyncio.run(deye_status())
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert "SOC" in parsed["data"]


class TestMcpParameterValidation:
    """Verify MCP tools validate parameters before calling core."""

    def test_history_invalid_granularity_raises_tool_error(self):
        from deye_mcp import deye_history
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="granularity"):
            asyncio.run(deye_history(
                granularity="hourly", start_date="2026-03-13", end_date="2026-03-13"
            ))

    def test_config_invalid_section_raises_tool_error(self):
        from deye_mcp import deye_config
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="section"):
            asyncio.run(deye_config(section="invalid"))

    def test_control_invalid_action_raises_tool_error(self):
        from deye_mcp import deye_control
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="action"):
            asyncio.run(deye_control(
                action="invalid_action", params={}, confirmed=True
            ))

    def test_devices_invalid_command_raises_tool_error(self):
        from deye_mcp import deye_devices
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="command"):
            asyncio.run(deye_devices(command="invalid"))

    def test_setup_invalid_command_raises_tool_error(self):
        from deye_mcp import deye_setup
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="command"):
            asyncio.run(deye_setup(command="invalid"))


class TestMcpControlTool:
    """Verify deye_control requires confirmation and returns focused diff."""

    @patch('deye_core.get_session')
    @patch('deye_core.http_post')
    def test_control_without_confirm_returns_diff(self, mock_post, mock_session):
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "data": {"solarSell": 0, "workMode": 1}}
        from deye_mcp import deye_control
        import asyncio
        result = asyncio.run(deye_control(
            action="set_solar_sell", params={"action": "on"}, confirmed=False
        ))
        parsed = json.loads(result)
        assert parsed["confirmation_required"] is True
        assert "changes" in parsed


class TestMcpErrorHandling:
    """Verify API failures raise ToolError (isError=true in MCP protocol)."""

    @patch('deye_core.get_session')
    @patch('deye_core.http_post')
    def test_status_api_failure_raises_tool_error(self, mock_post, mock_session):
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": False, "msg": "Token expired", "code": 401}
        from deye_mcp import deye_status
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="Token expired"):
            asyncio.run(deye_status())
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deye_mcp'`

**Step 3: Create `deye_mcp.py`**

Create `skills/deye-cloud/scripts/deye_mcp.py`:

```python
#!/usr/bin/env python3
"""Deye Cloud MCP Server — 7 tools for inverter management via Model Context Protocol."""

import json
from typing import Optional
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

import deye_core

mcp = FastMCP(
    "Deye Cloud",
    description="Monitor, configure, and control Deye Hybrid Inverters via the DeyeCloud API.",
)

# --- Validation constants ---
_VALID_GRANULARITIES = {"intraday", "daily", "monthly"}
_VALID_CONFIG_SECTIONS = {"battery", "system", "tou", "all"}
_VALID_DEVICE_COMMANDS = {"list_devices", "list_stations", "station_info", "measure_points"}
_VALID_SETUP_COMMANDS = {"check", "order_status"}
_VALID_CONTROL_ACTIONS = {
    "set_work_mode", "set_solar_sell", "set_battery_param", "set_battery_mode",
    "set_battery_type", "set_tou", "set_tou_switch", "set_energy_pattern",
    "set_power", "set_grid_peak_shaving", "set_smart_load", "set_limit_control",
    "dynamic_control",
}


def _check_result(result: dict) -> dict:
    """Raise ToolError if core returned a failure, propagating isError to MCP clients."""
    if not result.get("success"):
        msg = result.get("error", "Unknown error")
        actions = result.get("suggested_actions", [])
        detail = f"{msg}. Try: {', '.join(actions)}" if actions else msg
        raise ToolError(detail)
    return result


@mcp.tool
async def deye_status() -> str:
    """Get current inverter status: PV production, battery SOC, grid power, consumption.
    Use when the user asks about current power, battery level, or solar production."""
    result = deye_core.get_status()
    return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


@mcp.tool
async def deye_history(
    granularity: str,
    start_date: str,
    end_date: str,
    measure_points: Optional[str] = None,
    station_id: Optional[int] = None,
    raw: bool = False,
) -> str:
    """Get historical energy data (production, consumption, battery, grid).
    Use when the user asks about past energy usage, daily/monthly totals, or trends.

    Args:
        granularity: Data resolution — "intraday" (5-min intervals), "daily", or "monthly"
        start_date: Start date as YYYY-MM-DD (intraday/daily) or YYYY-MM (monthly)
        end_date: End date as YYYY-MM-DD (intraday/daily) or YYYY-MM (monthly)
        measure_points: Optional comma-separated keys to filter, e.g. "SOC,BatV,GridW"
        station_id: Optional station ID for station-level history
        raw: If true, return raw API response without formatting
    """
    if granularity not in _VALID_GRANULARITIES:
        raise ToolError(f"Invalid granularity '{granularity}'. Must be one of: {', '.join(sorted(_VALID_GRANULARITIES))}")
    result = deye_core.get_history(
        granularity=granularity, start=start_date, end=end_date,
        measure_points=measure_points, station_id=station_id, raw=raw,
    )
    return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


@mcp.tool
async def deye_devices(
    command: str = "list_devices",
    station_id: Optional[int] = None,
) -> str:
    """List devices and stations, or get available measure points.
    Use when the user asks about connected devices, stations, available data points, or wants to see what's available.

    Args:
        command: "list_devices" (all devices), "list_stations" (all stations),
                 "station_info" (details for one station), or "measure_points" (available data points for the device)
        station_id: Required when command is "station_info"
    """
    if command not in _VALID_DEVICE_COMMANDS:
        raise ToolError(f"Invalid command '{command}'. Must be one of: {', '.join(sorted(_VALID_DEVICE_COMMANDS))}")
    result = deye_core.get_devices(command=command, station_id=station_id)
    return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


@mcp.tool
async def deye_alerts(station_id: Optional[int] = None) -> str:
    """Get device or station alerts and warnings.
    Use when the user asks about faults, warnings, or error conditions.

    Args:
        station_id: If provided, get station-level alerts instead of device alerts
    """
    result = deye_core.get_alerts(station_id=station_id)
    return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


@mcp.tool
async def deye_config(section: str = "all") -> str:
    """Read current inverter configuration settings.
    Use when the user asks about battery settings, work mode, or TOU schedule.

    Args:
        section: "battery", "system", "tou", or "all" (reads all dynamic parameters)
    """
    if section not in _VALID_CONFIG_SECTIONS:
        raise ToolError(f"Invalid section '{section}'. Must be one of: {', '.join(sorted(_VALID_CONFIG_SECTIONS))}")
    result = deye_core.get_config(section=section)
    return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


@mcp.tool
async def deye_control(
    action: str,
    params: dict,
    confirmed: bool = False,
) -> str:
    """Execute a control command on the inverter (WRITE operation).
    ⚠️ SAFETY: Call first with confirmed=false to see what will change.
    Only call with confirmed=true after the user explicitly confirms.

    Args:
        action: Control action — set_work_mode, set_solar_sell, set_battery_param,
                set_battery_mode, set_battery_type, set_tou, set_tou_switch,
                set_energy_pattern, set_power, set_grid_peak_shaving,
                set_smart_load, set_limit_control, dynamic_control
        params: Action-specific parameters as a dict
        confirmed: Must be true to execute. When false, returns current config for comparison.
    """
    if action not in _VALID_CONTROL_ACTIONS:
        raise ToolError(f"Invalid action '{action}'. Must be one of: {', '.join(sorted(_VALID_CONTROL_ACTIONS))}")

    if not confirmed:
        # Read current config and build a focused before/after diff
        current = deye_core.get_config(section="all")
        current_data = current.get("data", {})
        # Build changes list: show only the keys that the proposed params would affect
        changes = []
        for key, new_val in params.items():
            old_val = current_data.get(key, "<not set>")
            changes.append({"param": key, "current": old_val, "proposed": new_val})
        return json.dumps({
            "confirmation_required": True,
            "action": action,
            "changes": changes,
            "message": "Review the changes above. Call again with confirmed=true to execute.",
        }, indent=2, ensure_ascii=False)

    result = deye_core.run_control(action=action, params=params)
    return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


@mcp.tool
async def deye_setup(
    command: str = "check",
    order_id: Optional[str] = None,
) -> str:
    """Check credential setup or track a control order status.
    Use for initial configuration or to verify if a control command succeeded.

    Args:
        command: "check" (verify credentials) or "order_status" (check control order result)
        order_id: Required when command is "order_status"
    """
    if command not in _VALID_SETUP_COMMANDS:
        raise ToolError(f"Invalid command '{command}'. Must be one of: {', '.join(sorted(_VALID_SETUP_COMMANDS))}")
    if command == "order_status":
        if not order_id:
            raise ToolError("order_id is required when command is 'order_status'")
        result = deye_core.get_order_status(order_id=order_id)
        return json.dumps(_check_result(result), indent=2, ensure_ascii=False)
    else:
        result = deye_core.check_setup()
        return json.dumps(_check_result(result), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
```

**Step 4: Run MCP tests**

Run: `python -m pytest tests/test_mcp.py -v`
Expected: All tests PASS

**Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add skills/deye-cloud/scripts/deye_mcp.py tests/test_mcp.py
git commit -m "feat: add MCP server with 7 grouped tools"
```

---

### Task 5: Update SKILL.md for Dual CLI/MCP Mode

**Files:**
- Modify: `skills/deye-cloud/SKILL.md`

**Step 1: Update SKILL.md**

Add an MCP section at the top, before the existing CLI instructions. The skill should detect the runtime:

```markdown
---
name: deye-cloud
description: Monitor, configure, and control Deye Hybrid Inverters via the DeyeCloud API. Use when the user asks about solar panels, battery status, inverter settings, energy production, grid export, or any Deye/solar-related topic.
---

# Deye Cloud Skill

Manage Deye Hybrid Inverters through natural language. Supports two modes:

## Mode Detection

- **MCP Mode** (Claude Desktop, Cursor, Cline): If `deye_status`, `deye_history`, etc. tools are available → use them directly.
- **CLI Mode** (Antigravity, Claude Code): If MCP tools are NOT available → use `python3 skills/deye-cloud/scripts/deye_cli.py --json <command>`.

---

## MCP Mode — Tool Reference
[... 7 tool descriptions with parameters ...]

## CLI Mode — Command Reference
[... existing CLI documentation ...]
```

**Step 2: Verify SKILL.md is valid YAML frontmatter**

Run: `python -c "import yaml; yaml.safe_load(open('skills/deye-cloud/SKILL.md').read().split('---')[1])"`
Expected: No error (or skip if pyyaml not installed — frontmatter format is unchanged)

**Step 3: Commit**

```bash
git add skills/deye-cloud/SKILL.md
git commit -m "docs: update SKILL.md for dual CLI/MCP mode"
```

---

### Task 6: Update README.md and Add Deployment Docs

**Files:**
- Modify: `README.md`

**Step 1: Update README.md**

Add MCP server deployment instructions alongside the existing CLI docs:
- New "Deploy to Claude Desktop" section with `claude_desktop_config.json` example
- Update the architecture diagram to show both CLI and MCP paths
- Add `pip install fastmcp` to prerequisites

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add MCP server deployment instructions to README"
```

---

### Task 7: End-to-End Verification

**Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (core, CLI, MCP, auth, env, http)

**Step 2: Verify CLI still works (Antigravity path)**

Run: `python skills/deye-cloud/scripts/deye_cli.py --json status`
Expected: JSON output with inverter status (or token error if offline)

**Step 3: Verify MCP server starts**

Run: `python skills/deye-cloud/scripts/deye_mcp.py`
Expected: Server starts on stdio transport without errors (Ctrl+C to stop)

**Step 4: Test with FastMCP dev inspector (optional)**

Run: `fastmcp dev skills/deye-cloud/scripts/deye_mcp.py`
Expected: Opens browser-based inspector showing 7 tools with descriptions and schemas

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes"
```
