# Deye Daily Analysis — Methodology

## Overview

`deye_daily.py` computes an hourly energy balance for a given day by fetching 4 independent data series from the Deye Cloud API (intraday granularity = ~1-minute intervals) and performing per-interval energy arithmetic.

---

## Data Series

| Key | Measure Points | What it represents |
|-----|---------------|--------------------|
| `pv` | `DailyActiveProduction` | Cumulative PV production (kWh), resets daily |
| `cons` | `DailyConsumption` | Cumulative total consumption (kWh), resets daily |
| `pwr` | `BatteryPower`, `SOC`, `TotalDCInputPower`, `TotalConsumptionPower`, `GridVoltageL1L2` | Instantaneous power readings (W) + SOC (%) |
| `grid` | `DailyEnergyPurchased`, `DailyGridFeedIn` | Cumulative grid import/export (kWh) |

All series are fetched with `granularity=1` (intraday, approximately 1-minute intervals).

---

## Cumulative → Delta Conversion

The API returns **cumulative** counters (they grow monotonically within a day). To get energy-per-interval, we compute the first difference:

```
delta[i] = max(0, cumulative[i] - cumulative[i-1])
```

The `max(0, ...)` guards against any rare negative deltas caused by API correction rolls. This produces a list of energy amounts (in kWh) for each record interval.

### Why not use instantaneous power?

`TotalDCInputPower` and `BatteryPower` are instantaneous readings (W). They can be used to compute energy (`W * hours = Wh`) but introduce integration error because each reading is only valid for the interval until the next sample. The cumulative counters (`DailyActiveProduction`, etc.) are **already integrated** by the inverter's internal measurement, so their delta is more accurate. We use cumulative-delta for PV, consumption, and grid energy; we use instantaneous `BatteryPower` for battery charge/discharge because no cumulative battery energy counter is exposed by this API.

---

## Battery Power Sign Convention

Confirmed from raw data inspection:

| BatteryPower value | Meaning |
|--------------------|---------|
| Negative (e.g., `-4254 W`) | Battery is **charging** (energy flowing into battery) |
| Positive (e.g., `+800 W`) | Battery is **discharging** (energy flowing out of battery) |

Battery energy per interval:

```
interval_secs = seconds from record[i] to record[i+1]
bat_wh = BatteryPower_W * (interval_secs / 3600)
# Negative bat_wh = stored energy, Positive bat_wh = extracted energy
```

---

## Hourly Aggregation

Each record is bucketed into its UTC+7 hour (`"YYYY-MM-DD HH"`). Within each hour, energy values are summed:

- `pv_kwh`, `load_kwh`, `grid_kwh` are already in kWh from delta conversion
- `bat_charge_wh`, `bat_dis_wh` are in Wh (converted from W × time), then divided by 1000 for display

The last hour (23:00) may be incomplete if the last record arrives before 23:59:59.

---

## Cross-Validation

After aggregation, the totals are compared against the API-reported final daily values (last record of each cumulative series):

| Check | How |
|-------|-----|
| PV total | `pv_kwh` sum vs `DailyActiveProduction` last value |
| Consumption total | `load_kwh` sum vs `DailyConsumption` last value |
| Grid total | `grid_kwh` sum vs `DailyEnergyPurchased` last value |
| SOC delta | `(soc_end - soc_start)% × battery_capacity_kWh ≈ net_bat_kwh` |

A discrepancy of ≤ 0.1 kWh is expected due to floating-point rounding. Larger discrepancies indicate a missing interval or API reporting error.

---

## Units Convention

| Variable | Internal unit | Display unit |
|----------|--------------|-------------|
| `pv_kwh`, `load_kwh`, `grid_kwh` | kWh | kWh (rounded to 2 dp) |
| `bat_charge_wh`, `bat_dis_wh` | Wh | kWh (÷1000, rounded to 2 dp) |
| `BatteryPower` | W | — |
| `SOC` | % | % |

---

## Timezone

All timestamps are UTC+7 (Vietnam). The `LOCAL_TZ = timezone(timedelta(hours=7))` constant controls date boundary interpretation.
