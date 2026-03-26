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

When MCP tools are available, use these 7 tools directly:

### `deye_status`
Get current inverter status (PV, battery SOC, grid, consumption). No parameters needed.

### `deye_history`
Get historical energy data.
- `granularity`: `"intraday"`, `"daily"`, or `"monthly"`
- `start_date`: `YYYY-MM-DD` (intraday/daily) or `YYYY-MM` (monthly)
- `end_date`: same format as start_date
- `measure_points` (optional): comma-separated keys, e.g. `"SOC,BatV,GridW"`
- `station_id` (optional): for station-level history
- `raw` (optional): `true` for raw API response

### `deye_devices`
List devices, stations, or measure points.
- `command`: `"list_devices"` (default), `"list_stations"`, `"station_info"`, or `"measure_points"`
- `station_id` (optional): required for `station_info`

### `deye_alerts`
Get device or station alerts.
- `station_id` (optional): for station-level alerts

### `deye_config`
Read inverter configuration.
- `section`: `"battery"`, `"system"`, `"tou"`, or `"all"` (default, reads all dynamic params)

### `deye_control`
Execute a control command (WRITE operation). ⚠️ **Safety: always call with `confirmed=false` first.**
- `action`: e.g. `"set_solar_sell"`, `"set_work_mode"`, `"set_battery_param"`, etc.
- `params`: action-specific dict
- `confirmed`: `false` to preview changes, `true` to execute after user confirms

### `deye_setup`
Check credentials or track order status.
- `command`: `"check"` (default) or `"order_status"`
- `order_id`: required when command is `"order_status"`

---

## CLI Mode — Command Reference

### First-Run Setup

If credentials are not configured yet:

```bash
python3 skills/deye-cloud/scripts/deye_cli.py --json setup
```

Then guide the user to edit `~/.deye/.env` with their Deye Cloud developer credentials:
- `DEYE_BASE_URL` — API base URL (default: EU endpoint)
- `DEYE_APP_ID` — Developer app ID from [developer.deyecloud.com](https://developer.deyecloud.com)
- `DEYE_APP_SECRET` — Developer app secret
- `DEYE_EMAIL` — Account email
- `DEYE_PASSWORD` — Account password (stored locally, hashed before transmission)
- `DEYE_COMPANY_ID` — Company ID (default: `0`)

After setup, all subsequent commands auto-authenticate and cache the token.

### 🟢 Monitor (read-only)

| Command | Use When |
|---------|----------|
| `status` | User asks about current power, battery SOC, grid status |
| `devices` | User wants to see all connected devices |
| `measure-points` | User asks what data points are available |
| `history --granularity 1\|2\|3\|4 --start DATE --end DATE` | User asks about past production, consumption, etc. |
| `history-raw --start DATE --end DATE` | User needs raw timestamped data |
| `alerts` | User asks about warnings or faults |
| `station-list` | User asks about their stations |
| `station-info --station-id ID` | User wants station details |
| `station-history --station-id ID --start --end` | Station-level history |
| `station-alerts --station-id ID` | Station-level alerts |
| `order-status --order-id ID` | Check result of a control command |

### 🔵 Config (read-only settings)

| Command | Use When |
|---------|----------|
| `config-battery` | User asks about battery settings (capacity, SOC limits, charge current) |
| `config-system` | User asks about current work mode |
| `config-tou` | User asks about time-of-use schedule |
| `dynamic-read` | User wants all dynamic control parameters at once |

### 🔴 Control (write operations)

| Command | Use When |
|---------|----------|
| `set-work-mode --mode MODE` | User wants to change work mode |
| `set-solar-sell --action on\|off` | User wants to enable/disable grid selling |
| `set-battery-param --param PARAM --value N` | User wants to adjust battery parameters |
| `set-battery-mode --mode MODE --action on\|off` | User wants to change charge mode |
| `set-battery-type --type TYPE` | User wants to change battery type |
| `set-tou --settings JSON` | User wants to set TOU schedule |
| `set-tou-switch --action on\|off --days DAYS` | User wants to enable/disable TOU |
| `set-energy-pattern --pattern PATTERN` | User wants to change energy priority |
| `set-power --type TYPE --value N` | User wants to set power limits |
| `set-grid-peak-shaving --action on\|off --power N` | User wants to control peak shaving |
| `set-smart-load --on-soc N --off-soc N` | User wants to configure smart load |
| `set-limit-control --type TYPE` | User wants to change limit control function |
| `dynamic-control --params JSON` | User wants to set multiple parameters at once |

### Running Commands

Always use `--json` flag for structured output:

```bash
python3 skills/deye-cloud/scripts/deye_cli.py --json <command> [args...]
```

The CLI auto-detects credentials in this order:
1. **`$DEYE_ENV_PATH`** — explicit environment variable override
2. **`{cwd}/.env`** — project `.env` in the current working directory (default)
3. **`~/.deye/.env`** — fallback

This means you don't need to specify `--env-path` when running from the project root — it picks up your `DeyeCloud-cli/.env` automatically.

Optional global flags:
- `--device-sn SN` — Override device serial number (default: auto-discovered)
- `--env-path PATH` — Explicitly override the .env path

## ⚠️ CRITICAL SAFETY PROTOCOL

**Before executing ANY 🔴 Control command, you MUST follow this protocol:**

### Step 1: READ current configuration
Run the corresponding config command first:
- Before `set-battery-param` → run `config-battery`
- Before `set-work-mode` → run `config-system`
- Before `set-tou` → run `config-tou`
- Before any `set-*` → run `dynamic-read`

### Step 2: PRESENT comparison table
Show the user what will change:

| Parameter | Current | Proposed |
|-----------|---------|----------|
| Max Charge Current | 30 A | 50 A |

### Step 3: EXPLAIN the impact
Describe what the change does in plain language and any risks.

### Step 4: WAIT for explicit confirmation
Acceptable confirmations: "Yes", "Confirm", "Go ahead", "Do it"
**NOT acceptable**: Ambiguous responses, no response, implicit agreement

### Step 5: EXECUTE the command

### Step 6: VERIFY the result
```bash
python3 skills/deye-cloud/scripts/deye_cli.py --json order-status --order-id <ID>
```
Report success (status=666) or failure to the user.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Token expired` | Delete `DEYE_TOKEN` and `DEYE_TOKEN_EXPIRES_AT` from `.env`, re-run any command |
| `Device not found` | Delete `DEYE_DEVICE_SN` from `.env` to trigger re-discovery |
| `Permission denied` | Verify `DEYE_APP_ID` and `DEYE_APP_SECRET` at developer.deyecloud.com |
| `Connection error` | Check `DEYE_BASE_URL` matches your region (EU/US/CN) |
| `dynamic-read timeout` | Device may be offline; try again later |

## References

For detailed API information, see:
- [api-overview.md](references/api-overview.md) — Base URLs, auth flow, response format
- [monitoring.md](references/monitoring.md) — Measure point codes, history granularity
- [configuration.md](references/configuration.md) — Battery parameters, work modes, TOU
- [control.md](references/control.md) — Enum values, order flow, safety warnings
