# Deye Cloud MCP Server Design

Add an MCP (Model Context Protocol) server to the existing deyecloud-cli project so the Deye Cloud skill works in Claude Desktop and other MCP-compatible clients (Cursor, Cline, Windsurf), while keeping the existing CLI-based Antigravity/Claude Code skill fully functional.

## Problem

The current skill works by having the AI agent shell out to `deye_cli.py`, which uses `urllib.request` to call the Deye Cloud API. Claude Desktop sandboxes network access, blocking this flow. MCP servers run as separate processes with full network access, solving this restriction.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   deye_core.py                        │
│  (shared library: env parser, HTTP, auth, API calls)  │
└──────────┬──────────────────────┬────────────────────┘
           │                      │
    ┌──────▼──────┐       ┌───────▼───────┐
    │ deye_cli.py │       │ deye_mcp.py   │
    │ (argparse)  │       │ (FastMCP)     │
    └──────┬──────┘       └───────┬───────┘
           │                      │
    Antigravity /          Claude Desktop /
    Claude Code            Cursor / Cline
    (shell out)            (MCP protocol)
```

### Key Decisions

1. **`deye_core.py`** (NEW) — All business logic extracted from the current monolithic `deye_cli.py`. Each API operation becomes a standalone function returning a dict (no printing, no argparse dependency).

2. **`deye_cli.py`** (MODIFIED) — Thin argparse wrapper importing `deye_core`. The existing Antigravity skill continues to work unchanged.

3. **`deye_mcp.py`** (NEW) — FastMCP server exposing 7 grouped tools. Imports `deye_core` for all logic.

4. **Credentials** — Both CLI and MCP use `~/.deye/.env` via `Path.home()` (cross-platform: Windows, macOS, Linux).

## MCP Tool Design (7 Tools)

Follows MCP best practices: coarse-grained declarative tools grouped by user intent, keeping count under 10 for optimal LLM accuracy.

### 1. `deye_status` — Current Inverter State

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| *(none)* | — | — | Returns current PV, battery, grid, consumption |

### 2. `deye_history` — Historical Energy Data

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `granularity` | enum: `intraday`, `daily`, `monthly` | yes | Data resolution |
| `start_date` | string `YYYY-MM-DD` or `YYYY-MM` | yes | Period start |
| `end_date` | string `YYYY-MM-DD` or `YYYY-MM` | yes | Period end |
| `measure_points` | string (comma-separated) | no | Filter specific data points |
| `station_id` | int | no | If set, fetches station-level history |
| `raw` | bool (default: false) | no | Return unformatted API response |

### 3. `deye_devices` — Device & Station Discovery

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | enum: `list_devices`, `list_stations`, `station_info`, `measure_points` | no (default: `list_devices`) | What to list |
| `station_id` | int | for `station_info` | Station ID |

### 4. `deye_alerts` — Warnings & Faults

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `station_id` | int | no | If set, fetches station-level alerts |

### 5. `deye_config` — Read Current Settings

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `section` | enum: `battery`, `system`, `tou`, `all` | no (default: `all`) | Which config section |

`all` uses `dynamic-read` to fetch everything in one call.

### 6. `deye_control` — Write Operations ⚠️

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | enum: `set_work_mode`, `set_solar_sell`, `set_battery_param`, `set_battery_mode`, `set_battery_type`, `set_tou`, `set_tou_switch`, `set_energy_pattern`, `set_power`, `set_grid_peak_shaving`, `set_smart_load`, `set_limit_control`, `dynamic_control` | yes | Control action |
| `params` | dict | yes | Action-specific parameters |
| `confirmed` | bool (default: false) | no | Must be `true` to execute |

**Server-side safety protocol:**
1. First call (confirmed=false): reads current config, returns comparison table + `"confirmation_required": true`
2. Second call (confirmed=true): executes the command, returns `order_id`

### 7. `deye_setup` — Configuration & Order Tracking

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | enum: `check`, `order_status` | no (default: `check`) | What to do |
| `order_id` | string | for `order_status` | Order ID to check |

## Error Handling

- All tool results: `{"success": true/false, "data": ..., "error": ...}`
- API failures → MCP `isError: true` with actionable message
- Invalid parameters → validated server-side before hitting the API
- Network errors → caught and returned as tool error (not crash)
- Suggested next actions included in error responses

## SKILL.md Update

The SKILL.md will be updated to support dual-mode operation:
- **MCP mode**: If MCP tools are available, use `deye_status`, `deye_history`, etc.
- **CLI mode**: If MCP is not available, fall back to `python3 deye_cli.py --json <cmd>`

Same SKILL.md works in both Antigravity (CLI) and Claude Desktop (MCP).

## Deployment

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "deye-cloud": {
      "command": "python",
      "args": ["path/to/skills/deye-cloud/scripts/deye_mcp.py"]
    }
  }
}
```

### Antigravity / Claude Code
No change — existing skill continues to shell out to `deye_cli.py`.

## Dependencies

- **New**: `fastmcp` (pip install) — Anthropic's official Python MCP SDK
- **Existing CLI path**: remains zero-dependency (stdlib only)

## File Changes

```
skills/deye-cloud/
├── SKILL.md                    # [MODIFY] Dual CLI/MCP instructions
├── scripts/
│   ├── deye_core.py            # [NEW] Shared business logic (~500 lines)
│   ├── deye_cli.py             # [MODIFY] Thin CLI wrapper (~300 lines)
│   └── deye_mcp.py             # [NEW] FastMCP server, 7 tools (~250 lines)
└── references/                 # Unchanged
tests/
├── test_core.py                # [NEW] Tests for deye_core functions
├── test_mcp.py                 # [NEW] MCP tool registration & validation
├── test_cli_commands.py        # [MODIFY] Update imports to use deye_core
├── test_auth.py                # [MODIFY] Update imports to use deye_core
├── test_env_parser.py          # [MODIFY] Update imports to use deye_core
└── test_http_client.py         # [MODIFY] Update imports to use deye_core
```
