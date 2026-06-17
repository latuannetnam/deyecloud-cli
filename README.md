# deyecloud-cli

CLI, MCP Server, and AI Skills for managing Deye Hybrid Inverters via the [DeyeCloud Developer API](https://developer.deyecloud.com). Provides **29 CLI subcommands**, **7 MCP tools**, and **two Claude Code skills** covering real-time monitoring, configuration reading, and remote control.

## Two Skills, One Purpose

Skill | Best for
------ | -------
**`/deye-cloud`** | Real-time status, history, config, control — all inverter operations
**`/deye-cloud-daily`** | Detailed hourly energy balance report for a specific day
**`/deye-cloud-monthly`** | Monthly / multi-month energy summary with EVN tiered pricing and solar savings

## Features

- ☀️ **Monitor** — Live PV production, battery SOC, grid power, consumption, alerts, and history
- ⚙️ **Configure** — Read battery settings, system work mode, Time-of-Use schedules
- 🔧 **Control** — Change work mode, battery parameters, power limits, TOU, smart load, and more
- 🤖 **AI-Native** — Built as an [Antigravity](https://github.com/google-deepmind/antigravity) / Claude Code skill with structured JSON output
- 🔒 **Safety Protocol** — Mandatory read-before-write, comparison table, and user confirmation for all control operations
- 🔌 **MCP Server** — 7 grouped tools for [Claude Desktop](https://claude.ai/download), Cursor, Cline, and other MCP clients
- 📦 **Minimal Dependencies** — CLI uses only Python stdlib; MCP server adds only `fastmcp`

## Prerequisites

1. **Python 3.8+**
2. **Deye Cloud Developer Account** — Register at [developer.deyecloud.com](https://developer.deyecloud.com) to get your `App ID` and `App Secret`
3. **For MCP Server:** `pip install fastmcp` (not needed for CLI-only usage)

---

## Quick Start

### 1. Install the Claude Code skills

Both skills are installed together in one step:

```bash
# Global (default) -> ~/.claude/skills/
python install.py

# Per-project       -> ./.claude/skills/
python install.py --scope local

# Explicit target   -> <PATH>/.claude/skills/
python install.py --target /path/to/project

# Preview without writing
python install.py --dry-run
```

Windows wrapper: `.\install-skill.ps1 --scope local` · POSIX wrapper: `./install.sh --scope local`

Then start a **new Claude Code session**:

```
/deye-cloud setup          # configure credentials (first run only)
/deye-cloud status         # real-time inverter status
/deye-cloud-daily          # yesterday's hourly energy report
/deye-cloud-daily --date 2026-04-01
```

> On first run, `/deye-cloud setup` creates `~/.deye/.env` — see [Step 2](#2-setup-credentials) below to fill in your credentials. Both skills share the same credentials file.

---

### 2. Setup credentials {#setup-credentials}

```bash
python3 skills/deye-cloud/scripts/deye_cli.py setup
```

This creates `~/.deye/.env`. Edit it with your credentials:

```ini
DEYE_BASE_URL=https://eu1-developer.deyecloud.com/v1.0
DEYE_APP_ID=your_app_id
DEYE_APP_SECRET=your_app_secret
DEYE_EMAIL=your_email
DEYE_PASSWORD=your_password
DEYE_COMPANY_ID=0
```

> **Note:** Use the base URL matching your region: `eu1-developer` (Europe), `us1-developer` (US), or `api.deye.com.cn` (China).

### 2. Check inverter status

```bash
# Human-readable output
python3 skills/deye-cloud/scripts/deye_cli.py status

# JSON output (for scripts and AI agents)
python3 skills/deye-cloud/scripts/deye_cli.py --json status
```

### 3. View history

```bash
# Today's 5-minute intervals
python3 skills/deye-cloud/scripts/deye_cli.py history --granularity 1 --start 2026-03-14 --end 2026-03-14

# Monthly totals
python3 skills/deye-cloud/scripts/deye_cli.py history --granularity 3 --start 2026-01 --end 2026-03
```

---

## CLI Usage

```
python3 skills/deye-cloud/scripts/deye_cli.py [--json] [--device-sn SN] [--env-path PATH] <command> [args...]
```

### Global Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Structured JSON output (recommended for automation) |
| `--device-sn` | auto-discovered | Override device serial number |
| `--env-path` | `~/.deye/.env` | Override credentials file path |

### Commands

#### 🟢 Monitor (read-only)

| Command | Description |
|---------|-------------|
| `setup` | Create or validate credentials file |
| `status` | Live PV, battery, grid, and consumption data |
| `devices` | List all stations and devices |
| `measure-points` | Available data points for the device |
| `history` | Historical data with `--granularity 1\|2\|3\|4 --start DATE --end DATE` |
| `history-raw` | Raw history JSON by timestamps |
| `alerts` | Device warnings and faults |
| `station-list` | List all stations |
| `station-info` | Station details (`--station-id ID`) |
| `station-history` | Station-level history |
| `station-alerts` | Station-level alerts |
| `order-status` | Check control command result (`--order-id ID`) |

#### 🔵 Config (read-only settings)

| Command | Description |
|---------|-------------|
| `config-battery` | Battery capacity, SOC limits, charge/discharge current |
| `config-system` | Current system work mode |
| `config-tou` | Time-of-Use schedule |
| `dynamic-read` | All dynamic control parameters (two-step poll) |

#### 🔴 Control (write operations)

| Command | Description |
|---------|-------------|
| `set-work-mode` | System mode: `SELLING_FIRST`, `ZERO_EXPORT_TO_LOAD`, `ZERO_EXPORT_TO_CT` |
| `set-solar-sell` | Enable/disable solar selling (`--action on\|off`) |
| `set-battery-param` | Adjust `MAX_CHARGE_CURRENT`, `MAX_DISCHARGE_CURRENT`, `GRID_CHARGE_AMPERE`, `BATT_LOW` |
| `set-battery-mode` | Grid/generator charge mode (`--mode --action on\|off`) |
| `set-battery-type` | Battery type: `LI`, `BATT_V`, `BATT_SOC`, `NO_BATTERY` |
| `set-tou` | Set TOU schedule (`--settings JSON`) |
| `set-tou-switch` | Enable/disable TOU (`--action on\|off --days MON,TUE,...`) |
| `set-energy-pattern` | Priority: `BATTERY_FIRST` or `LOAD_FIRST` |
| `set-power` | Power limits: `MAX_SELL_POWER`, `MAX_SOLAR_POWER`, `ZERO_EXPORT_POWER` |
| `set-grid-peak-shaving` | Peak shaving control |
| `set-smart-load` | Smart load SOC/voltage thresholds |
| `set-limit-control` | Limit control function |
| `dynamic-control` | Set multiple parameters at once (`--params JSON`) |

> ⚠️ **All control commands modify real inverter settings.** Always read the current config first and verify the result via `order-status`.

---

## AI Skill Usage

This project ships **two AI coding agent skills** — instruction sets that teach an AI assistant to manage your Deye inverter through natural language.

### Skill Overview

Skill | Use when the user asks about...
:--- | :----------------------------
**`/deye-cloud`** | Real-time status, history, config, control
**`/deye-cloud-daily`** | A specific day's hourly energy balance

### How `/deye-cloud` Works

```
                          ┌─── CLI Mode (Antigravity, Claude Code) ───┐
You ──> AI Agent ──> SKILL.md ──> python3 deye_cli.py --json <cmd>
                          │                                           │
                          └─── MCP Mode (Claude Desktop, Cursor) ────┘
                                    deye_mcp.py (7 tools)
                                           │
                              ┌─── deye_core.py (shared logic) ───┐
                              │                                    │
                              └──────── Deye Cloud API ───────────┘
```

### Example prompts

With **`/deye-cloud`**:

- *"What's my current battery level?"*
- *"Show me yesterday's solar production"*
- *"What work mode is my inverter in?"*
- *"Change the max charge current to 50A"* (the AI will confirm before executing)

With **`/deye-cloud-daily`**:

- *"Show me yesterday's energy report"*
- *"What was my solar production on April 1st?"*
- *"Give me the hourly breakdown for last Monday"*

### Safety Protocol

The `SKILL.md` instructs the AI agent to follow a mandatory 6-step safety protocol before any control operation:

1. **READ** current configuration
2. **PRESENT** comparison table (Current vs Proposed)
3. **EXPLAIN** the impact
4. **WAIT** for explicit user confirmation
5. **EXECUTE** the command
6. **VERIFY** the result via `order-status`

---

## Deployment

### Deploy to Claude Desktop (MCP)

Add to your `claude_desktop_config.json`:

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

Make sure `fastmcp` is installed: `pip install fastmcp`

The MCP server exposes 7 tools (`deye_status`, `deye_history`, `deye_devices`, `deye_alerts`, `deye_config`, `deye_control`, `deye_setup`) that Claude Desktop can call directly.

### Deploy to Antigravity

Copy the `skills/deye-cloud/` folder into your Antigravity skills directory:

```bash
# The skill directory should be placed where Antigravity discovers skills
cp -r skills/deye-cloud/ /path/to/your-project/skills/deye-cloud/
```

Antigravity auto-discovers skills via the `skills/` directory. Once deployed, it will detect the `SKILL.md` frontmatter and activate the skill when solar/inverter topics arise.

### Install the skill suite

The suite is always installed together. Use the cross-platform installer:

```bash
# Global (default) -> ~/.claude/skills/
python install.py

# Per-project       -> ./.claude/skills/
python install.py --scope local

# Explicit target   -> <PATH>/.claude/skills/
python install.py --target /path/to/project

# Preview without writing
python install.py --dry-run
```

Windows wrapper: `.\install-skill.ps1 --scope local` · POSIX wrapper: `./install.sh --scope local`

The installer handles everything for each skill:

- Copies `SKILL.md`, `references/`, and `scripts/` as-is (no frontmatter rewriting)
- Reads the `description` field from each skill's own `SKILL.md`

Once installed, start a **new Claude Code session**:

```text
/deye-cloud setup
/deye-cloud status
/deye-cloud-daily
```

> **Why a personal install?** Skills in `~/.claude/skills/` are available in every Claude Code project. If you prefer project-scoped installs instead, copy individual `skills/<name>/` folders directly into `.claude/skills/` within any project.

### Deploy to Any AI Agent

The CLI works standalone. Any agent that can execute shell commands can use it:

1. Copy `skills/deye-cloud/scripts/deye_cli.py` to the target system
2. Run `python3 deye_cli.py setup` and configure credentials
3. Instruct the agent to use `python3 deye_cli.py --json <command>` for structured output
4. Optionally provide `SKILL.md` as context for the agent to understand the command catalog and safety protocol

### Run from the repo (no install)

Point any CLI harness at this repo's `skills/` folder. Scripts self-locate the
shared core (`deye_core.py`) and your `.env`, so no install step is required:

```bash
python3 skills/deye-cloud-daily/scripts/deye_daily.py --date yesterday --output text
```

### Adding a new deye-* skill

1. `cp -r skills/_template skills/deye-cloud-<x>`
2. Edit `skills/deye-cloud-<x>/SKILL.md` (`name` + `description`) and write
   `scripts/deye_<x>.py` (it already does `import _bootstrap; import deye_core`).
3. Run `python install.py` (or just point a harness at the repo).

`_bootstrap.py` comes from the template and is identical across skills. The
installer auto-discovers the new folder; no installer changes needed.

---

## Project Structure

```
deyecloud-cli/
├── install.py                           # Cross-platform installer (global/local/target/dry-run)
├── install-skill.ps1                    # thin wrapper -> install.py
├── install.sh                           # POSIX thin wrapper -> install.py
├── skills/
│   ├── _template/                       # Scaffold for new deye-* skills
│   ├── deye-cloud/
│   │   ├── SKILL.md                    # AI agent instructions (CLI + MCP)
│   │   ├── scripts/
│   │   │   ├── deye_core.py            # Shared business logic (returns dicts)
│   │   │   ├── deye_cli.py             # CLI wrapper (argparse, 29 subcommands)
│   │   │   └── deye_mcp.py             # MCP server (FastMCP, 7 grouped tools)
│   │   └── references/
│   │       ├── api-overview.md         # Base URLs, auth flow, response format
│   │       ├── monitoring.md           # Measure point codes, history granularity
│   │       ├── configuration.md        # Battery params, work modes, TOU structure
│   │       └── control.md               # Enum values, order flow, safety warnings
│   ├── deye-cloud-daily/
│   │   ├── SKILL.md                    # AI agent instructions (hourly energy report)
│   │   └── scripts/
│   │       └── deye_daily.py           # Hourly energy balance analyzer (reuses deye_core.py)
│   └── deye-cloud-monthly/
│       ├── SKILL.md                    # AI agent instructions (monthly/multi-month energy report with EVN pricing)
│       └── scripts/
│           └── deye_monthly.py         # Monthly/multi-month energy balance analyzer (reuses deye_core.py)
├── tests/                              # pytest unit tests (55 tests)
├── requirements.txt                     # fastmcp dependency (MCP server only)
├── samples/                             # Reference Python scripts from Deye API docs
└── docs/plans/                          # Design and implementation plan documents
```

## Running Tests

```bash
pip install pytest fastmcp
python -m pytest tests/ -v
```

## License

MIT
