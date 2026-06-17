---
name: deye-cloud-monthly
description: >
  Use this skill whenever the user asks about monthly or multi-monthly solar energy
  summaries, electricity bills, solar savings, or any date range longer than one day.
  Examples: "solar this month", "electricity bill last month", "tháng 3", "how much did
  I save with solar in March", "solar summary March 2026", "tong hop thang 4", "bao cao
  thang nay", "summarize energy for Q1 2026", "tong san luong thang 2". Also triggers
  for queries like "how much did I spend on electricity this month", "tien dien thang nay",
  "EVN bill this month", or any question about accumulated solar production, consumption,
  or savings over weeks or months. This skill supersedes deye-cloud-daily for anything
  longer than one day.
compatibility: python3.12+, deye-cloud skill installed (reuses deye_core.py)
---

# deye-cloud-monthly Skill

Provides a monthly (or arbitrary date range) energy balance report with EVN tiered pricing
and solar savings calculations for Deye hybrid inverter systems.

---

## Running scripts

This skill ships Python scripts in its own `scripts/` folder. Invoke them with:

- **Claude Code:** `python3 "${CLAUDE_SKILL_DIR}/scripts/<file>.py" ...`
- **Other harnesses (Antigravity, Codex, Gemini, Copilot):** the skill directory
  is the folder containing this `SKILL.md`. Run
  `python3 <skill-dir>/scripts/<file>.py ...` — e.g. from the repo that is
  `python3 skills/deye-cloud-monthly/scripts/<file>.py ...`.

Scripts self-locate both the shared core and the `.env`, so there are no
working-directory assumptions — you only need to run the correct `.py` file.

---

## Workflow

### Step 1 — Parse the date / range

Interpret the user's request to determine start and end dates:

| Input | Interpreted as |
|-------|---------------|
| `this month`, `tháng nay`, `hôm nay` | Current calendar month (UTC+7) |
| `last month`, `tháng trước` | Previous calendar month |
| `2026-04`, `tháng 4/2026`, `thang 4/2026` | April 2026 |
| `2026-03 --end 2026-04` | March–April 2026 |
| `03/2026`, `3/2026` | March 2026 |

If no date given, default to `this month`.

### Step 2 — Run the analyzer

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/deye_monthly.py" --date <DATE> --output text
```

Use `--output json` for scripting. The script auto-detects credentials via the same
`.env` priority as `deye-cloud`.

### Step 3 — Present the report

Display the table exactly as printed by the script:
- **Daily table**: Ngày | Solar | Tải | Pin nạp | Pin xả | Lưới mua | Feed-in
- **Totals row**: sum of each column
- **Energy summary block**: totals + self-sufficiency %
- **Financial block**: EVN 6-tier cost, bill without solar, savings

### Step 4 — Disclaimer for incomplete months

If the requested period includes today (current month not yet finished), add:

> ⚠️ Dữ liệu tháng này chưa hoàn chỉnh — bảng phản ánh năng lượng tính đến thời điểm hiện tại.

---

## EVN 6-Tier Pricing (May 2024, VAT-inclusive)

| Bậc | Mức kWh/tháng | Giá (VND/kWh) |
|-----|-------------|--------------|
| 1 | 0 – 50 | 1,806 |
| 2 | 51 – 100 | 2,062 |
| 3 | 101 – 200 | 2,357 |
| 4 | 201 – 300 | 2,838 |
| 5 | 301 – 400 | 3,338 |
| 6 | 401+ | 4,044 |

## Savings Formula

```
savings = bill_without_solar(cons_kwh) - bill_with_grid(grid_kwh)
```
Where `bill_without_solar` = what the electricity bill would be if all consumption
was purchased from the grid at EVN tiered rates, and `bill_with_grid` = the actual
bill paid after solar offsets part of the consumption.

---

## Output Formats

### Text (default — for chat)

Human-readable ASCII table with financial summary.

### JSON (for scripting)

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/deye_monthly.py" --date 2026-04 --output json
```

Returns:
```json
{
  "period": { "start": "2026-04-01", "end": "2026-04-30", "incomplete": true },
  "daily_records": [...],
  "totals_kwh": {
    "pv_kwh": 154.5, "cons_kwh": 141.0,
    "bat_charge_kwh": 111.6, "bat_dis_kwh": 94.2,
    "net_bat_kwh": 17.4, "grid_kwh": 3.9,
    "grid_feed_kwh": 0.0, "self_sufficiency_pct": 109.6
  },
  "financials_vnd": {
    "grid_bill_vnd": 7043,
    "bill_without_solar_vnd": 290037,
    "savings_vnd": 282994,
    "avg_rate_vnd_per_kwh": 2057
  }
}
```

---

## Error Handling

| Situation | Response |
|-----------|----------|
| No data for period | "Không có dữ liệu cho khoảng này. Thiết bị có thể offline hoặc chưa có bản ghi." |
| Auth error | "Lỗi xác thực — chạy `deye-cloud setup` để kiểm tra credentials." |
| Invalid date | "Không nhận diện được ngày. Dùng: YYYY-MM, tháng M/YYYY, 'this month', 'last month'" |

---

## Script Location

- **Script**: Claude Code: `"${CLAUDE_SKILL_DIR}/scripts/deye_monthly.py"` — other harnesses: `skills/deye-cloud-monthly/scripts/deye_monthly.py`
- **Reuses**: `deye-cloud/scripts/deye_core.py` (API calls, auth, session)
- **Dependencies**: stdlib only (json, re, datetime, calendar, pathlib, argparse)
- **Python**: 3.12+

Locates `deye_core.py` via `_bootstrap.py` (`$DEYE_CORE_DIR` → sibling `deye-cloud/scripts/`).
