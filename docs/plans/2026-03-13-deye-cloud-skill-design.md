# Deye Cloud Antigravity Skill — Design Document

> **Date**: 2026-03-13
> **Status**: Approved
> **Scope**: Full management (monitor + config + control) for Deye Hybrid Inverters

---

## 1. Problem Statement

Managing a Deye Hybrid Inverter currently requires either the DeyeCloud mobile app or manual API calls. An Antigravity/Claude skill would let an AI assistant monitor inverter status, review historical data, read configuration, and send control commands — all through natural language conversation.

**Requirements:**
- Cross-OS (Windows, Mac, Linux) with zero external Python dependencies
- Credentials stored in `~/.deye/.env` with guided first-run setup
- Always-confirm safety protocol for all control operations
- Single CLI script with structured JSON output for AI parsing

---

## 2. Architecture

### Approach: Rich Skill (SKILL.md + script + references)

```
skills/deye-cloud/
├── SKILL.md                     # Core instructions, workflow, safety rules
├── scripts/
│   └── deye_cli.py              # Single CLI, stdlib-only, 28 subcommands
└── references/
    ├── api-overview.md           # Endpoint catalog, auth flow, base URLs
    ├── monitoring.md             # Status, history, alerts, measure points
    ├── configuration.md          # Battery, TOU, system mode reads
    └── control.md                # All write operations, parameter enums, safety
```

### Data Flow

```
User ──(natural language)──> AI ──(reads SKILL.md)──> run_command
  │                                                        │
  │                                                  python3 deye_cli.py <cmd> --json
  │                                                        │
  │                                                  ┌─────▼──────┐
  │                                                  │ deye_cli.py │
  │                                                  │  - parse .env│
  │                                                  │  - auto-auth │
  │                                                  │  - API call  │
  │                                                  │  - JSON out  │
  │                                                  └─────┬──────┘
  │                                                        │
  │◄──────(formatted response)──── AI ◄───(parse JSON)─────┘
```

---

## 3. Credential Management

### Location: `~/.deye/.env`

```ini
# User-provided (one-time setup)
DEYE_BASE_URL=https://eu1-developer.deyecloud.com/v1.0
DEYE_APP_ID=your_app_id
DEYE_APP_SECRET=your_app_secret
DEYE_EMAIL=your_email
DEYE_PASSWORD=your_password
DEYE_COMPANY_ID=0

# Auto-managed by deye_cli.py (do not edit)
DEYE_TOKEN=eyJhbGciOi...
DEYE_TOKEN_EXPIRES_AT=1778559837
DEYE_DEVICE_SN=2511183967
```

### Auth Flow (from samples/deye_auth.py)

1. Read credentials from `~/.deye/.env`
2. Check cached token expiry (1-hour safety margin)
3. If expired: POST `/account/token?appId={appId}` with SHA256-hashed password
4. Cache new token + expiry to `.env`
5. If no `DEYE_DEVICE_SN`: auto-discover via `/station/list` → `/station/device`
6. Return `(base_url, headers, device_sn)` tuple

### Stdlib Replacements

| Was (external) | Now (stdlib) | Notes |
|----------------|-------------|-------|
| `requests.post()` | `urllib.request.Request` + `urlopen` | JSON body via `data=json.dumps(payload).encode()` |
| `requests.get()` | `urllib.request.urlopen(url)` | Add auth header manually |
| `dotenv.load_dotenv()` | Custom `_load_env(path)` | Read lines, skip `#`, split on first `=`, strip quotes |
| `dotenv.set_key()` | Custom `_save_env(path, updates)` | Read all, update dict, write back |

---

## 4. CLI Design — `deye_cli.py`

### Global Options

```
python3 deye_cli.py [--json] [--device-sn SN] [--env-path PATH] <command> [args...]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Output structured JSON (AI mode) |
| `--device-sn` | from .env | Override device serial number |
| `--env-path` | `~/.deye/.env` | Override credentials file location |

### Subcommands Catalog

#### 🟢 Monitor (read-only)

| Command | API | Args | Description |
|---------|-----|------|-------------|
| `setup` | — | — | Validate/create `~/.deye/.env` |
| `status` | `POST /device/latest` | — | Live PV, battery, grid, consumption |
| `devices` | `POST /station/list` + `POST /station/device` | — | List all stations and devices |
| `history` | `POST /device/history` | `--granularity 1\|2\|3\|4` `--start DATE` `--end DATE` `--points KEY,KEY` | Historical data (intraday/daily/monthly/yearly) |
| `history-raw` | `POST /device/historyRaw` | `--start TS` `--end TS` `--points KEY,KEY` | Raw history by Unix timestamps (≤5 day span) |
| `measure-points` | `POST /device/measurePoints` + `POST /device/latest` | — | Available measure points with live values |
| `alerts` | `POST /device/alertList` | `--start TS` `--end TS` `--page N` `--size N` | Device alerts (≤30 day span) |
| `station-list` | `POST /station/list` | `--page N` `--size N` | List stations |
| `station-info` | `POST /station/latest` | `--station-id ID` | Station real-time data |
| `station-history` | `POST /station/history` | `--station-id ID` `--granularity 1\|2\|3\|4` `--start DATE` `--end DATE` | Station history |
| `station-alerts` | `POST /station/alertList` | `--station-id ID` `--start TS` `--end TS` | Station alerts (≤180 day span) |
| `order-status` | `GET /order/{orderId}` | `--order-id ID` | Check control command result |

#### 🔵 Config (read-only settings)

| Command | API | Description |
|---------|-----|-------------|
| `config-battery` | `POST /config/battery` | Battery capacity, low/shutdown SOC, max charge/discharge current |
| `config-system` | `POST /config/system` | System work mode |
| `config-tou` | `POST /config/tou` | Time-of-Use schedule |
| `dynamic-read` | `POST /strategy/dynamicControl/read` + `POST .../readResult` | Read all dynamic control parameters at once |

#### 🔴 Control (write operations — ALWAYS CONFIRM)

| Command | API | Key Args | Description |
|---------|-----|----------|-------------|
| `set-work-mode` | `POST /order/sys/workMode/update` | `--mode SELLING_FIRST\|ZERO_EXPORT_TO_LOAD\|ZERO_EXPORT_TO_CT` | Set system work mode |
| `set-solar-sell` | `POST /order/sys/solarSell/control` | `--action on\|off` | Enable/disable solar sell |
| `set-battery-param` | `POST /order/battery/parameter/update` | `--param MAX_CHARGE_CURRENT\|MAX_DISCHARGE_CURRENT\|GRID_CHARGE_AMPERE\|BATT_LOW` `--value N` | Set battery parameter |
| `set-battery-mode` | `POST /order/battery/modeControl` | `--mode GRID_CHARGE\|GEN_CHARGE` `--action on\|off` | Enable/disable charge mode |
| `set-battery-type` | `POST /order/battery/type/update` | `--type BATT_V\|BATT_SOC\|LI\|NO_BATTERY` | Set battery type |
| `set-tou` | `POST /order/sys/tou/update` | `--settings JSON` | Set TOU schedule (6 time intervals) |
| `set-tou-switch` | `POST /order/sys/tou/switch` | `--action on\|off` `--days MON,TUE,...` | Enable/disable TOU |
| `set-energy-pattern` | `POST /order/sys/energyPattern/update` | `--pattern BATTERY_FIRST\|LOAD_FIRST` | Set energy priority |
| `set-power` | `POST /order/sys/power/update` | `--type MAX_SELL_POWER\|MAX_SOLAR_POWER\|ZERO_EXPORT_POWER` `--value N` | Set power limits |
| `set-grid-peak-shaving` | `POST /order/gridPeakShaving/control` | `--action on\|off` `--power N` | Grid peak shaving |
| `set-smart-load` | `POST /order/smartload/update` | `--on-soc N` `--off-soc N` `--on-voltage N` `--off-voltage N` | Smart load settings |
| `set-limit-control` | `POST /order/sys/limitControl` | `--type SELL_FIRST\|ZERO_EXPORT_TO_UPS_LOAD\|ZERO_EXPORT_TO_CT\|ZERO_EXPORT_TO_WIRELESS_CT` | Limit control function |
| `dynamic-control` | `POST /strategy/dynamicControl` | Multiple optional args | Set multiple parameters at once |

---

## 5. JSON Output Schema

### Success Response

```json
{
  "success": true,
  "command": "<subcommand>",
  "device_sn": "2511183967",
  "timestamp": "2026-03-13T22:00:00+07:00",
  "data": { ... }
}
```

### Error Response

```json
{
  "success": false,
  "command": "<subcommand>",
  "error": "Token expired",
  "api_code": "1000001",
  "api_msg": "Token invalid"
}
```

### Key Measure Point Codes (for `status` and `history`)

| Group | Key Codes |
|-------|-----------|
| Solar PV | `DCPowerPV1`..`PV4`, `TotalDCInputPower` |
| Battery | `SOC`, `BatteryPower`, `BatteryVoltage`, `BatteryCurrent` |
| Grid | `TotalGridPower`, `GridVoltageL1L2`, `GridFrequency` |
| Consumption | `TotalConsumptionPower`, `DailyConsumption` |
| Production | `DailyActiveProduction`, `TotalActiveProduction` |
| Feed-in | `DailyGridFeedIn`, `DailyEnergyPurchased` |
| Temperature | `DC Temperature`, `AC Temperature`, `Temperature- Battery` |

---

## 6. Safety Protocol

### SKILL.md rules for AI behavior:

```
CRITICAL SAFETY RULE:
Before executing ANY 🔴 Control command, you MUST:

1. READ the current configuration related to the change
   (e.g., run `config-battery` before `set-battery-param`)

2. PRESENT a comparison table to the user:
   | Parameter | Current | Proposed |
   |-----------|---------|----------|
   | Max Charge Current | 30 A | 50 A |

3. EXPLAIN the impact:
   "This will increase the battery charge rate from 30A to 50A,
    which charges faster but may reduce battery lifespan."

4. WAIT for explicit user confirmation.
   Acceptable: "Yes", "Confirm", "Go ahead", "Do it"
   NOT acceptable: Ambiguous responses, no response

5. EXECUTE the command via deye_cli.py

6. VERIFY the result by checking order-status
   Report success or failure to the user.
```

---

## 7. Implementation Modules (inside deye_cli.py)

The single file is organized into logical sections:

```python
#!/usr/bin/env python3
"""Deye Cloud CLI — Zero-dependency inverter management."""

# ── Section 1: .env Parser ─────────────────────────────
# _load_env(), _save_env(), _update_env_value()

# ── Section 2: HTTP Client ──────────────────────────────
# _http_post(), _http_get() — wrappers around urllib.request

# ── Section 3: Auth ─────────────────────────────────────
# _hash_password(), _obtain_token(), _discover_device(),
# get_session() — mirrors samples/deye_auth.py logic

# ── Section 4: Monitor Commands ─────────────────────────
# cmd_status(), cmd_devices(), cmd_history(), cmd_alerts(),
# cmd_measure_points(), cmd_station_*(), cmd_order_status()

# ── Section 5: Config Commands ──────────────────────────
# cmd_config_battery(), cmd_config_system(), cmd_config_tou(),
# cmd_dynamic_read()

# ── Section 6: Control Commands ─────────────────────────
# cmd_set_work_mode(), cmd_set_solar_sell(), cmd_set_battery_param(),
# cmd_set_battery_mode(), cmd_set_tou(), cmd_set_tou_switch(),
# cmd_set_energy_pattern(), cmd_set_power(), cmd_set_grid_peak_shaving(),
# cmd_set_smart_load(), cmd_set_limit_control(), cmd_dynamic_control()

# ── Section 7: Output Formatting ────────────────────────
# _json_output(), _human_output(), _format_timestamp()

# ── Section 8: CLI Entry Point ──────────────────────────
# argparse setup, subcommand routing, main()
```

---

## 8. Reference Documents

### references/api-overview.md
- Base URLs per region (EU, US)
- Auth flow with SHA256 password encoding
- Token lifecycle (60-day validity, no invalidation on re-request)
- Common response envelope (`success`, `code`, `msg`, `requestId`)
- Rate limits and batch size constraints

### references/monitoring.md
- Complete measure point code table with descriptions and units
- History granularity options (1=intraday/5min, 2=daily, 3=monthly, 4=yearly)
- Date format requirements per granularity
- Alert level/impact/status code meanings

### references/configuration.md
- Battery parameter definitions and ranges
- System work mode options and behavior descriptions
- TOU schedule structure (6 time intervals)
- Dynamic control read flow (two-step: send read → poll result)

### references/control.md
- Complete enum values for each control parameter
- Order execution flow: send → get orderId → poll order status (status=666 = success)
- Safety warnings per operation
- Device type compatibility notes (some commands only for Hybrid, some only for Micro ESS)
