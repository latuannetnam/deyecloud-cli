# Configuration Reference

## Battery Parameters

Read via: `deye_cli.py config-battery`

| Parameter | CLI Arg | Range | Description |
|-----------|---------|-------|-------------|
| Max Charge Current | `MAX_CHARGE_CURRENT` | 0–100 A | Maximum battery charge current |
| Max Discharge Current | `MAX_DISCHARGE_CURRENT` | 0–100 A | Maximum battery discharge current |
| Grid Charge Current | `GRID_CHARGE_AMPERE` | 0–100 A | Max current when charging from grid |
| Battery Low SOC | `BATT_LOW` | 5–100 % | Low battery shutdown threshold |

## System Work Modes

Read via: `deye_cli.py config-system`

| Mode | Description |
|------|-------------|
| `SELLING_FIRST` | Export excess solar to grid |
| `ZERO_EXPORT_TO_LOAD` | No grid export, power loads only |
| `ZERO_EXPORT_TO_CT` | No grid export, measured at CT clamp |

## TOU Schedule Structure

Read via: `deye_cli.py config-tou`

Time-of-Use supports 6 time intervals per day. Each interval:

```json
{
  "startTime": "00:00",
  "endTime": "06:00",
  "sellOrCharge": "charge",
  "power": 2000,
  "soc": 100
}
```

Fields:
- `startTime` / `endTime`: HH:MM format
- `sellOrCharge`: `"charge"` or `"sell"`
- `power`: Power limit in watts
- `soc`: Target SOC (%)

## Dynamic Read Flow

Command: `deye_cli.py dynamic-read`

Two-step process:
1. **Send read request**: `POST /strategy/dynamicControl/read` → returns immediately
2. **Poll for result**: `POST /strategy/dynamicControl/readResult` → poll every 2s, up to 5 retries

Returns all dynamic control parameters in a single response (battery settings, work mode, power limits, TOU, etc.).
