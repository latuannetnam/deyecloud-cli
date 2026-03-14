#!/usr/bin/env python3
"""Deye Cloud MCP Server — 7 tools for inverter management via Model Context Protocol."""

import json
from typing import Optional
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

import deye_core

mcp = FastMCP(
    "Deye Cloud",
    instructions="Monitor, configure, and control Deye Hybrid Inverters via the DeyeCloud API.",
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
