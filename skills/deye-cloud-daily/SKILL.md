---
name: deye-cloud-daily
description: >-
  Use this skill whenever the user asks about daily solar production, electric usage,
  battery charge/discharge, grid energy, or any per-day energy summary from their
  Deye hybrid inverter system. Also use when the user asks to analyze, summarize,
  or report on a specific day's performance.

  This includes phrases like:
  - "daily report", "bao cao ngay", "thong ke ngay"
  - "ngay hom qua", "hom qua", "yesterday"
  - "summarize today", "ngay hom nay", "tong hop hom nay"
  - "thong ke dien theo gio", "hourly electricity stats"
  - "phan tich dien solar", "phan tich ngay"
  - "bao cao solar", "solar report"
  - Any request for energy data for a specific past date (e.g. "ngay 01/04/2026",
    "2026-04-07", "date 07/04/2026")

  Do NOT trigger for real-time status ("current solar power right now") — use
  deye-cloud skill for that. This skill is specifically for daily historical
  analysis with hourly breakdown.
---

# deye-cloud-daily

Provides a detailed hourly energy balance report for any specific day (past or
current) from the Deye Cloud API.

---

## Workflow

### Step 1 — Detect the date

Parse the date from user input. Supported formats:

| Input example | Interpreted as |
|---------------|----------------|
| `yesterday`, `hôm qua` | The day before today (UTC+7) |
| `today`, `hôm nay` | Today (UTC+7) |
| `2026-04-07` | 7 April 2026 (ISO) |
| `07/04/2026` | 7 April 2026 (DD/MM/YYYY) |
| `ngay 07/04/2026` | 7 April 2026 (Vietnamese) |

Default: `yesterday` if no date is specified.

### Step 2 — Run the analyzer

```bash
python3 skills/deye-cloud-daily/scripts/deye_daily.py --date <DATE> --output text
```

- The script auto-detects credentials via the same `.env` priority as `deye-cloud`
- If no `--date` is given, it defaults to yesterday
- Use `--output json` for machine-readable output

### Step 3 — Present the report

Display the hourly table exactly as printed by the script:

- **7 columns**: Giờ | Solar (kWh) | Pin nạp (kWh) | Pin xả (kWh) | Tải (kWh) | Lưới mua (kWh) | Tự dùng?
- **Totals row**: sum of each column
- **Cross-check summary**: API-reported totals vs computed totals
- **Battery net**: charge - discharge in kWh, compared to SOC delta

### Step 4 — Note for current-day analysis

If the user asks for today, add this disclaimer:
> "⚠️ Dữ liệu hôm nay chưa hoàn chỉnh — bảng phản ánh năng lượng tính đến thời điểm hiện tại và sẽ thay đổi khi ngày kết thúc."

---

## Output Formats

### Text (default — for chat)

Human-readable ASCII table, suitable for copying into a conversation response.

```
======================================================================
  Bao cao nang luong ngay 07/04/2026
======================================================================
  Gio       Solar    Pin nap   Pin xa      Tai  Luoi mua   Tudung?
------------------------------------------------------------------------------
  00           0.0       0.0       0.9      0.8       0.0
  ...
  TONG        18.20    14.41    11.88    16.60      0.40

  [Cross-check]  PV: 18.20 kWh  |  Tai: 16.20 kWh  |  Luoi: 0.40 kWh
  [Tong pin]  Nap: 14.41 kWh  -  Xa: 11.88 kWh  =  +2.53 kWh
```

### JSON (for scripting / piping)

Use `--output json` to get structured data:

```bash
python3 skills/deye-cloud-daily/scripts/deye_daily.py --date yesterday --output json
```

Returns:

```json
{
  "date": "2026-04-07",
  "hourly_records": [
    {"hour": "00", "pv_kwh": 0.0, "bat_charge_kwh": 0.0, "bat_dis_kwh": 0.9, "load_kwh": 0.8, "grid_kwh": 0.0},
    ...
  ],
  "totals": {
    "pv_kwh": 18.2,
    "bat_charge_kwh": 14.41,
    "bat_dis_kwh": 11.88,
    "net_bat_kwh": 2.53,
    "load_kwh": 16.6,
    "grid_kwh": 0.4,
    "self_sufficiency_pct": 109.6
  },
  "cross_check": {
    "pv_api": 18.2,
    "cons_api": 16.2,
    "grid_api": 0.4,
    "soc_start": 73,
    "soc_end": 76
  }
}
```

---

## Error Handling

| Situation | Response |
|-----------|----------|
| API returns no records | "Không có dữ liệu cho ngày này. Thiết bị có thể offline hoặc API chưa có bản ghi. Thử lại sau." |
| Auth / credential error | "Lỗi xác thực — chạy `deye-cloud setup` để kiểm tra credentials." |
| Partial series failure | Print table with what was retrieved + warning listing failed series |
| Invalid date format | "Không nhận diện được ngày. Dùng định dạng: YYYY-MM-DD, DD/MM/YYYY, 'today', 'yesterday'" |

---

## Column Definitions

| Vietnamese | English | Unit |
|------------|---------|------|
| Gio | Hour (UTC+7) | HH:00 |
| Solar | PV production that hour | kWh |
| Pin nap | Energy stored in battery that hour | kWh |
| Pin xa | Energy extracted from battery that hour | kWh |
| Tai | Total consumption that hour | kWh |
| Luoi mua | Energy imported from grid that hour | kWh |
| Tudung? | "OK" if Solar >= Tai (self-sufficient) | — |

---

## Cross-Check Summary

Always show the cross-check block after the table. It validates the table totals against the API's own daily counters. A discrepancy ≤ 0.1 kWh is normal (rounding). If larger, mention it.

---

## Script Location & Dependencies

- **Script**: `skills/deye-cloud-daily/scripts/deye_daily.py`
- **Reuses**: `deye-cloud/scripts/deye_core.py` (API calls, auth, session)
- **No new pip dependencies** — stdlib only (json, re, datetime, argparse)
- **Python**: 3.12+

The script locates `deye_core.py` via a sibling-directory import
(`../../deye-cloud/scripts/`). No extra configuration needed if `deye-cloud`
skill is installed.
