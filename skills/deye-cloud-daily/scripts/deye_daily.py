#!/usr/bin/env python3
"""Deye Cloud Daily Analyzer — hourly energy balance report.

Fetches intraday history for a given date, computes energy flows
(PV production, battery charge/discharge, load, grid), and prints an
hourly breakdown table with cross-validation against API totals.

Usage:
    python3 deye_daily.py --date 2026-04-07 --output text
    python3 deye_daily.py --date yesterday --output json
    python3 deye_daily.py --date "ngay 07/04/2026"
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

# ── Add deye-cloud scripts to import path ──────────────────────────────
_SCRIPT_DIR = Path(__file__).parent.resolve()
_DEYE_CLOUD_DIR = _SCRIPT_DIR.parent.parent / "deye-cloud" / "scripts"

# Check sibling path first, then allow override via env
if _DEYE_CLOUD_DIR.is_dir():
    sys.path.insert(0, str(_DEYE_CLOUD_DIR))

import deye_core

LOCAL_TZ = timezone(timedelta(hours=7))


# ── Date Parsing ──────────────────────────────────────────────────────

def parse_date(raw: str) -> date:
    """Parse a date string (today, yesterday, DD/MM/YYYY, YYYY-MM-DD, ngay DD/MM/YYYY)."""
    raw = raw.strip().lower()
    if raw in ("today", "hom-nay", "hôm nay"):
        return datetime.now(LOCAL_TZ).date()
    if raw in ("yesterday", "hom-qua", "hôm qua"):
        today = datetime.now(LOCAL_TZ).date()
        return date(today.year, today.month, today.day - 1) if today.day > 1 else date(
            today.year, today.month - 1 or 12, 28 + (today.month == 3 and (today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0) and 1))
        )
    # Strip Vietnamese "ngày " / "ngay " prefix
    stripped = re.sub(r"^ng[àa]y?\s+", "", raw, flags=re.IGNORECASE).strip()
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", stripped)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        return date(y, int(mo), int(d))
    # ISO YYYY-MM-DD
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", raw)
    if m:
        y, mo, d = m.groups()
        return date(int(y), int(mo), int(d))
    # DD/MM/YYYY fallback
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", raw)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        return date(y, int(mo), int(d))
    raise ValueError(f"Unrecognized date format: {raw!r}")


# ── Number Parsing ────────────────────────────────────────────────────

def parse_val(s: str) -> float:
    """Extract float, preserving leading minus sign for negative numbers."""
    return float(re.sub(r"[^\d.\-]", "", s))


def parse_w(s: str) -> float:
    """Extract float from strings like '4254 W' or '-4254 W'."""
    return parse_val(s)


# ── Data Fetching ────────────────────────────────────────────────────

def fetch_series(device_sn: str, env_path: str, start: date, end: date,
               measure_points: str) -> dict:
    """Fetch one intraday history series. Returns {'records': [...]}.
    On API error returns {'records': [], 'error': ...}."""
    result = deye_core.get_history(
        granularity=1,
        start=str(start),
        end=str(end),
        measure_points=measure_points,
        device_sn=device_sn,
        env_path=env_path,
    )
    if not result.get("success"):
        return {
            "records": [],
            "error": result.get("error", "Unknown error"),
            "code": result.get("api_code", ""),
        }
    return {"records": result["data"]["records"]}


def fetch_all(device_sn: str, env_path: str | None, target: date) -> dict:
    """Fetch all 4 required data series. Returns dict with keys:
    pv, cons, pwr, grid — each {'records': [...]}.
    """
    date_str = str(target)
    series = {
        "pv":   fetch_series(device_sn, env_path, target, target,
                            "DailyActiveProduction"),
        "cons": fetch_series(device_sn, env_path, target, target,
                            "DailyConsumption"),
        "pwr":  fetch_series(device_sn, env_path, target, target,
                             "BatteryPower,SOC,TotalDCInputPower,"
                             "TotalConsumptionPower,GridVoltageL1L2"),
        "grid": fetch_series(device_sn, env_path, target, target,
                            "DailyEnergyPurchased,DailyGridFeedIn"),
    }
    return series


# ── Energy Computation ────────────────────────────────────────────────

def cum_to_deltas(records: list, field: str) -> list:
    """Convert cumulative kWh counter to per-record energy deltas (kWh).
    Each record has shape {'time': ..., field: 'N.NN kWh'}.
    Returns list of same length as records.
    """
    vals = [parse_val(r.get(field, "0")) for r in records]
    deltas = []
    for i, v in enumerate(vals):
        prev = vals[i - 1] if i > 0 else 0.0
        deltas.append(max(0.0, v - prev))
    return deltas


def compute_hourly(pwr_records: list, series: dict) -> dict:
    """Aggregate all energy metrics to hourly buckets.

    Returns dict:
      hours[h_label] = {
        'pv_kwh': float,
        'load_kwh': float,
        'bat_charge_wh': float,
        'bat_dis_wh': float,
        'grid_kwh': float,
      }
    """
    # Build delta indices from cumulative series
    pv_delta   = cum_to_deltas(series["pv"]["records"],   "DailyActiveProduction")
    cons_delta = cum_to_deltas(series["cons"]["records"], "DailyConsumption")
    grid_delta = cum_to_deltas(series["grid"]["records"], "DailyEnergyPurchased")

    pv_idx   = {r["time"]: pv_delta[i]   for i, r in enumerate(series["pv"]["records"])}
    cons_idx = {r["time"]: cons_delta[i] for i, r in enumerate(series["cons"]["records"])}
    grid_idx = {r["time"]: grid_delta[i] for i, r in enumerate(series["grid"]["records"])}

    hours: dict = {}

    for i, r in enumerate(pwr_records):
        h_label = r["time"][:13]  # "YYYY-MM-DD HH"
        if h_label not in hours:
            hours[h_label] = {
                "pv_kwh": 0.0, "load_kwh": 0.0,
                "bat_charge_wh": 0.0, "bat_dis_wh": 0.0,
                "grid_kwh": 0.0,
            }

        # Interval length in seconds (to next record)
        next_t = pwr_records[i + 1]["time"] if i + 1 < len(pwr_records) else r["time"]
        h1, m1, s1 = int(r["time"][11:13]), int(r["time"][14:16]), int(r["time"][17:19])
        h2, m2, s2 = int(next_t[11:13]), int(next_t[14:16]), int(next_t[17:19])
        secs = (h2 * 3600 + m2 * 60 + s2) - (h1 * 3600 + m1 * 60 + s1)
        if secs < 0:
            secs += 86400

        # Battery energy (W * secs / 3600 = Wh)
        bat_w = parse_w(r.get("BatteryPower", "0"))
        if bat_w < 0:
            hours[h_label]["bat_charge_wh"] += abs(bat_w * secs / 3600)
        else:
            hours[h_label]["bat_dis_wh"]   += bat_w * secs / 3600

        # Cumulative deltas
        hours[h_label]["pv_kwh"]    += pv_idx.get(r["time"], 0.0)
        hours[h_label]["load_kwh"]  += cons_idx.get(r["time"], 0.0)
        hours[h_label]["grid_kwh"]  += grid_idx.get(r["time"], 0.0)

    return hours


# ── Output Formatting ────────────────────────────────────────────────

def print_table(hours: dict, target_date: date, cross_check: dict) -> None:
    """Print the hourly energy table to stdout (text mode)."""
    sep = "-" * 78
    header = f"{'Gio':<7} {'Solar':>8} {'Pin nap':>8} {'Pin xa':>8} {'Tai':>8} {'Luoi mua':>9} {'Tudung?':>9}"
    print(f"\n{'='*78}")
    print(f"  Bao cao nang luong ngay {target_date.strftime('%d/%m/%Y')}  ")
    print(f"{'='*78}")
    print(header)
    print(sep)

    sorted_keys = sorted(hours.keys())
    totals = {k: 0.0 for k in (
        "pv_kwh", "load_kwh", "bat_charge_wh", "bat_dis_wh", "grid_kwh")}

    for h in sorted_keys:
        d = hours[h]
        pv_kwh   = round(d["pv_kwh"], 2)
        bat_chg  = round(d["bat_charge_wh"] / 1000, 2)
        bat_dis  = round(d["bat_dis_wh"]    / 1000, 2)
        load_kwh = round(d["load_kwh"], 2)
        grid_kwh = round(d["grid_kwh"], 2)
        flag = " OK" if pv_kwh >= load_kwh else "    "
        print(f"{h[11:]:<7} {pv_kwh:>8} {bat_chg:>8} {bat_dis:>8} {load_kwh:>8} {grid_kwh:>9} {flag:>9}")

        for k in totals:
            totals[k] += d[k]

    print(sep)
    tpv = round(totals["pv_kwh"], 2)
    tbc = round(totals["bat_charge_wh"] / 1000, 2)
    tbd = round(totals["bat_dis_wh"]    / 1000, 2)
    tlo = round(totals["load_kwh"], 2)
    tgr = round(totals["grid_kwh"], 2)
    print(f"{'TONG':<7} {tpv:>8} {tbc:>8} {tbd:>8} {tlo:>8} {tgr:>9}")
    print(sep)

    # ── Summary block ───────────────────────────────────────────────────
    pv_api   = cross_check.get("pv_api",   tpv)
    con_api  = cross_check.get("cons_api", tlo)
    grd_api  = cross_check.get("grid_api", tgr)
    soc0     = cross_check.get("soc_start", 0)
    socN     = cross_check.get("soc_end",   0)
    net_bat  = tbc - tbd
    self_suff = (tpv / tlo * 100) if tlo > 0 else 0

    print(f"\n  [Cross-check]  PV: {pv_api:.2f} kWh  |  Tai: {con_api:.2f} kWh"
          f"  |  Luoi: {grd_api:.2f} kWh  |  SOC: {soc0:.0f}% -> {socN:.0f}%")
    print(f"  [Tong pin]  Nap: {tbc:.2f} kWh  -  Xa: {tbd:.2f} kWh  =  {net_bat:+.2f} kWh"
          f"  |  Tu dat tu: {self_suff:.1f}%")
    print()


def build_json(hours: dict, target_date: date, cross_check: dict) -> dict:
    """Return structured JSON dict for piping."""
    sorted_keys = sorted(hours.keys())
    records = []
    for h in sorted_keys:
        d = hours[h]
        records.append({
            "hour": h[11:],
            "pv_kwh":        round(d["pv_kwh"], 2),
            "bat_charge_kwh": round(d["bat_charge_wh"] / 1000, 2),
            "bat_dis_kwh":   round(d["bat_dis_wh"]    / 1000, 2),
            "load_kwh":      round(d["load_kwh"], 2),
            "grid_kwh":      round(d["grid_kwh"], 2),
        })

    tpv = round(sum(hours[h]["pv_kwh"]        for h in hours), 2)
    tbc = round(sum(hours[h]["bat_charge_wh"] for h in hours) / 1000, 2)
    tbd = round(sum(hours[h]["bat_dis_wh"]    for h in hours) / 1000, 2)
    tlo = round(sum(hours[h]["load_kwh"]       for h in hours), 2)
    tgr = round(sum(hours[h]["grid_kwh"]       for h in hours), 2)

    return {
        "date": str(target_date),
        "hourly_records": records,
        "totals": {
            "pv_kwh":         tpv,
            "bat_charge_kwh": tbc,
            "bat_dis_kwh":    tbd,
            "net_bat_kwh":    round(tbc - tbd, 2),
            "load_kwh":       tlo,
            "grid_kwh":       tgr,
            "self_sufficiency_pct": round(tpv / tlo * 100, 1) if tlo > 0 else 0,
        },
        "cross_check": cross_check,
    }


# ── Cross-Validation ──────────────────────────────────────────────────

def cross_validate(pwr_records: list, series: dict) -> dict:
    """Build cross-check dict from API-reported final daily values."""
    cc = {}

    pv_recs   = series["pv"]["records"]
    cons_recs = series["cons"]["records"]
    grid_recs = series["grid"]["records"]

    if pv_recs:
        cc["pv_api"]   = round(parse_val(pv_recs[-1].get("DailyActiveProduction", "0")), 2)
    if cons_recs:
        cc["cons_api"] = round(parse_val(cons_recs[-1].get("DailyConsumption", "0")), 2)
    if grid_recs:
        cc["grid_api"] = round(parse_val(grid_recs[-1].get("DailyEnergyPurchased", "0")), 2)
    if pwr_records:
        cc["soc_start"] = float(pwr_records[0].get("SOC", "0").replace(" %", ""))
        cc["soc_end"]   = float(pwr_records[-1].get("SOC", "0").replace(" %", ""))

    return cc


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deye Cloud daily energy analyzer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--date",
        default="yesterday",
        help="Date to analyze: YYYY-MM-DD, DD/MM/YYYY, 'ngay DD/MM/YYYY', "
             "'today', or 'yesterday' (default: yesterday)",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (table) or 'json' (for piping/scripting)",
    )
    parser.add_argument(
        "--device-sn",
        default=None,
        help="Override device serial number",
    )
    parser.add_argument(
        "--env-path",
        default=None,
        help="Path to .env credentials file",
    )
    args = parser.parse_args()

    # Parse date
    try:
        target = parse_date(args.date)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Establish session & get device SN (suppress deye_core status messages to stderr)
    try:
        env_path = args.env_path or deye_core.DEFAULT_ENV_PATH()
        import io
        _old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            base_url, headers, device_sn = deye_core.get_session(env_path=env_path)
        finally:
            sys.stderr = _old_stderr
        sn = args.device_sn or device_sn
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch all series
    series = fetch_all(sn, env_path, target)

    # Check for errors
    errors = {k: v["error"] for k, v in series.items() if "error" in v}
    if errors:
        print(f"WARNING: some series failed to fetch: {errors}", file=sys.stderr)

    pwr_records = series["pwr"]["records"]
    if not pwr_records:
        print(f"No data available for {target}. "
              f"The device may be offline or the date has no records yet.",
              file=sys.stderr)
        sys.exit(1)

    # Compute hourly aggregation
    hours = compute_hourly(pwr_records, series)

    # Cross-validation
    cross_check = cross_validate(pwr_records, series)

    # Output
    if args.output == "json":
        result = build_json(hours, target, cross_check)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_table(hours, target, cross_check)


if __name__ == "__main__":
    main()
