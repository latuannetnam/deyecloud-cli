# Control Reference

> ⚠️ **All control commands modify real inverter settings. ALWAYS read current config first and confirm with user before executing.**

## Order Execution Flow

1. **Send** control command → response includes `orderId`
2. **Poll** order status: `deye_cli.py order-status --order-id <ID>`
3. **Check** status code:
   - `666` = Success (command executed on device)
   - `0` = Pending (device hasn't responded yet)
   - Other = Error

## Control Commands

### set-work-mode
**Endpoint:** `POST /order/sys/workMode/update`

| Value | Description |
|-------|-------------|
| `SELLING_FIRST` | Export excess to grid |
| `ZERO_EXPORT_TO_LOAD` | No export, power loads only |
| `ZERO_EXPORT_TO_CT` | No export, CT-measured |

### set-solar-sell
**Endpoint:** `POST /order/sys/solarSell/control`

| Action | Effect |
|--------|--------|
| `on` | Enable selling solar to grid |
| `off` | Disable selling solar to grid |

### set-battery-param
**Endpoint:** `POST /order/battery/parameter/update`

| Param | Range | Unit |
|-------|-------|------|
| `MAX_CHARGE_CURRENT` | 0–100 | A |
| `MAX_DISCHARGE_CURRENT` | 0–100 | A |
| `GRID_CHARGE_AMPERE` | 0–100 | A |
| `BATT_LOW` | 5–100 | % |

### set-battery-mode
**Endpoint:** `POST /order/battery/modeControl`

| Mode | Action | Effect |
|------|--------|--------|
| `GRID_CHARGE` | `on`/`off` | Enable/disable grid charging |
| `GEN_CHARGE` | `on`/`off` | Enable/disable generator charging |

### set-battery-type
**Endpoint:** `POST /order/battery/type/update`

| Type | Description |
|------|-------------|
| `LI` | Lithium battery |
| `BATT_V` | Lead-acid (voltage-based) |
| `BATT_SOC` | Lead-acid (SOC-based) |
| `NO_BATTERY` | No battery connected |

### set-tou
**Endpoint:** `POST /order/sys/tou/update`

Pass `--settings` as JSON string with array of 6 intervals.

### set-tou-switch
**Endpoint:** `POST /order/sys/tou/switch`

| Action | Days | Effect |
|--------|------|--------|
| `on`/`off` | `MON,TUE,...` | Enable/disable TOU for specified days |

### set-energy-pattern
**Endpoint:** `POST /order/sys/energyPattern/update`

| Pattern | Description |
|---------|-------------|
| `BATTERY_FIRST` | Prioritize battery over grid |
| `LOAD_FIRST` | Prioritize load over battery |

### set-power
**Endpoint:** `POST /order/sys/power/update`

| Type | Description | Unit |
|------|-------------|------|
| `MAX_SELL_POWER` | Maximum grid export power | W |
| `MAX_SOLAR_POWER` | Maximum solar input power | W |
| `ZERO_EXPORT_POWER` | Zero-export threshold | W |

### set-grid-peak-shaving
**Endpoint:** `POST /order/gridPeakShaving/control`

Params: `--action on|off`, `--power <watts>`

### set-smart-load
**Endpoint:** `POST /order/smartload/update`

Params: `--on-soc`, `--off-soc`, `--on-voltage`, `--off-voltage`

### set-limit-control
**Endpoint:** `POST /order/sys/limitControl`

| Type | Description |
|------|-------------|
| `SELL_FIRST` | Sell excess first |
| `ZERO_EXPORT_TO_UPS_LOAD` | Zero export to UPS load |
| `ZERO_EXPORT_TO_CT` | Zero export measured at CT |
| `ZERO_EXPORT_TO_WIRELESS_CT` | Zero export via wireless CT |

### dynamic-control
**Endpoint:** `POST /strategy/dynamicControl`

Pass `--params` as JSON string with key-value pairs for multiple parameters.

## Device Compatibility

- **Hybrid Inverters**: All commands supported
- **Micro Inverters**: Only monitor commands; no config/control
- **ESS**: Most commands supported; check device-specific documentation
