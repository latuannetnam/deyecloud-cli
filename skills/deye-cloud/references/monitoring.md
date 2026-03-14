# Monitoring Reference

## Measure Point Codes

### Solar PV
| Key | Description | Unit |
|-----|-------------|------|
| `DCVoltagePV1`–`PV4` | DC voltage per string | V |
| `DCCurrentPV1`–`PV4` | DC current per string | A |
| `DCPowerPV1`–`PV4` | DC power per string | W |
| `TotalDCInputPower` | Total solar input | W |

### Battery
| Key | Description | Unit |
|-----|-------------|------|
| `SOC` | State of Charge | % |
| `BatteryPower` | Battery power (+charge, -discharge) | W |
| `BatteryVoltage` | Battery voltage | V |
| `BatteryCurrent` | Battery current | A |
| `BatteryRatedCapacity` | Rated capacity | Ah |
| `DailyChargingEnergy` | Today's charge | kWh |
| `DailyDischargingEnergy` | Today's discharge | kWh |
| `TotalChargeEnergy` | Lifetime charge | kWh |
| `TotalDischargeEnergy` | Lifetime discharge | kWh |
| `Temperature- Battery` | Battery temperature | °C |

### Grid
| Key | Description | Unit |
|-----|-------------|------|
| `TotalGridPower` | Grid power (+export, -import) | W |
| `GridVoltageL1L2` | Grid voltage | V |
| `GridCurrentL1L2` | Grid current | A |
| `GridFrequency` | Grid frequency | Hz |
| `ExternalCTPowerL1L2` | External CT measurement | W |

### Consumption
| Key | Description | Unit |
|-----|-------------|------|
| `TotalConsumptionPower` | Current load consumption | W |
| `DailyConsumption` | Today's consumption | kWh |
| `CumulativeConsumption` | Lifetime consumption | kWh |

### Production
| Key | Description | Unit |
|-----|-------------|------|
| `RatedPower` | Inverter rated power | W |
| `DailyActiveProduction` | Today's production | kWh |
| `TotalActiveProduction` | Lifetime production | kWh |

### Feed-in / Purchase
| Key | Description | Unit |
|-----|-------------|------|
| `DailyGridFeedIn` | Today's grid export | kWh |
| `CumulativeGridFeedIn` | Lifetime grid export | kWh |
| `DailyEnergyPurchased` | Today's grid import | kWh |
| `CumulativeEnergyPurchased` | Lifetime grid import | kWh |

### Temperature
| Key | Description | Unit |
|-----|-------------|------|
| `DC Temperature` | DC-side temperature | °C |
| `AC Temperature` | AC-side temperature | °C |

## History Granularity

| Value | Meaning | Date Format | Max Span |
|-------|---------|-------------|----------|
| 1 | Intraday (5-min intervals) | `YYYY-MM-DD` | 1 day |
| 2 | Daily totals | `YYYY-MM-DD` | ~1 year |
| 3 | Monthly totals | `YYYY-MM` | ~1 year |
| 4 | Yearly totals | `YYYY` | multiple years |

## Alert Levels

| Level | Meaning |
|-------|---------|
| 1 | Information |
| 2 | Warning |
| 3 | Fault |
| 4 | Critical |
