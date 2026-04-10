#!/usr/bin/env python3
"""Deye Cloud Monthly Analyzer — monthly / multi-month energy summary with EVN pricing.

Fetches daily granularity history for a given month (or arbitrary date range),
aggregates energy flows, calculates EVN tiered electricity cost, and estimates
solar savings.

Usage:
    python3 deye_monthly.py --date 2026-04
    python3 deye_monthly.py --date "tháng 4/2026"
    python3 deye_monthly.py --date "last month"
    python3 deye_monthly.py --date 2026-03 --end 2026-04
"""
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import os
import re
from calendar import monthrange
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

# ── Add deye-cloud scripts to import path ──────────────────────────────
_SCRIPT_DIR = Path(__file__).parent.resolve()
_DEYE_CLOUD_DIR = _SCRIPT_DIR.parent.parent / "deye-cloud" / "scripts"

if _DEYE_CLOUD_DIR.is_dir():
    sys.path.insert(0, str(_DEYE_CLOUD_DIR))

import deye_core

LOCAL_TZ = timezone(timedelta(hours=7))

# ── EVN 6-Tier Pricing (May 2024, VAT-inclusive) ────────────────────
# https://evn.com.vn — biểu giá bán lẻ điện sinh hoạt bậc thang
EVN_TIERS = [
    (50,  1806),   # Bậc 1: 0–50 kWh
    (50,  2062),   # Bậc 2: 51–100 kWh   (50 kWh)
    (100, 2357),   # Bậc 3: 101–200 kWh  (100 kWh)
    (100, 2838),   # Bậc 4: 201–300 kWh  (100 kWh)
    (100, 3338),   # Bậc 5: 301–400 kWh  (100 kWh)
    (9999, 4044),  # Bậc 6: 401+ kWh
]

def calc_evn_tiered(kwh: float) -> int:
    """Calculate EVN tiered electricity bill in VND for a monthly kWh amount."""
    bill = 0
    remaining = kwh
    for tier_kwh, rate in EVN_TIERS:
        if remaining <= 0:
            break
        used = min(remaining, tier_kwh)
        bill += used * rate
        remaining -= used
    return round(bill)


def calc_savings(cons_kwh: float, grid_kwh: float) -> tuple[int, int, int]:
    """Return (grid_bill, bill_without_solar, savings) in VND.

    savings = (bill_without_solar) - (bill_with_grid_only)
    i.e. value of the solar-generated electricity that replaced grid purchase.
    """
    grid_bill = calc_evn_tiered(grid_kwh)
    bill_without_solar = calc_evn_tiered(cons_kwh)
    savings = bill_without_solar - grid_bill
    return grid_bill, bill_without_solar, savings


# ── Date Parsing ───────────────────────────────────────────────────────

def parse_month(raw: str) -> tuple[date, date]:
    """Parse month string to (first_day, last_day) of that month in UTC+7.

    Supports: YYYY-MM, tháng M/YYYY, thang M/YYYY, this month, last month,
              previous month, month YYYY, M/YYYY
    """
    raw = raw.strip().lower()

    now = datetime.now(LOCAL_TZ).date()
    today = datetime.now(LOCAL_TZ).date()

    if raw in ("this month", "thang nay", "tháng nay", "hien tai", "hiện tại"):
        first = date(today.year, today.month, 1)
        last  = date(today.year, today.month, monthrange(today.year, today.month)[1])
        return first, last

    if raw in ("last month", "thang truoc", "tháng trước", "previous month"):
        m = datetime.now(LOCAL_TZ).replace(day=1) - timedelta(days=1)
        first = date(m.year, m.month, 1)
        last  = date(m.year, m.month, monthrange(m.year, m.month)[1])
        return first, last

    # "tháng M/YYYY" (with á or bare a)
    m = re.match(r"tháng?\s+(\d{1,2})[/\-.](\d{4})", raw)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        d = date(y, mo, 1)
        return d, date(y, mo, monthrange(y, mo)[1])

    # "M/YYYY"
    m = re.match(r"^(\d{1,2})[/\-.](\d{4})$", raw)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        d = date(y, mo, 1)
        return d, date(y, mo, monthrange(y, mo)[1])

    # "YYYY-MM"
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})$", raw)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        d = date(y, mo, 1)
        return d, date(y, mo, monthrange(y, mo)[1])

    raise ValueError(f"Nhận diện được tháng: {raw!r}. Dùng định dạng: YYYY-MM, tháng M/YYYY, 'this month', 'last month'")


# ── Number Parsing ─────────────────────────────────────────────────────

def parse_kwh(s: str) -> float:
    return float(re.sub(r"[^\d.\-]", "", s))


# ── Data Fetching ─────────────────────────────────────────────────────

def fetch_daily_history(device_sn: str, env_path: str,
                        start: date, end: date) -> list[dict]:
    """Fetch daily granularity history. Returns list of day records."""
    result = deye_core.get_history(
        granularity=2,
        start=str(start),
        end=str(end),
        device_sn=device_sn,
        env_path=env_path,
    )
    if result.get("success") and result["data"]["records"]:
        return result["data"]["records"]

    # Fallback: station-level
    # Discover station_id
    env = deye_core.load_env(env_path)
    device_sn_fallback = env.get("DEYE_DEVICE_SN", device_sn)
    station_result = deye_core.get_devices(
        command="list_stations",
        env_path=env_path,
    )
    if station_result.get("success"):
        stations = station_result["data"].get("stations", [])
        if stations:
            station_id = stations[0]["id"]
            st_result = deye_core.get_history(
                granularity=2,
                start=str(start),
                end=str(end),
                station_id=station_id,
            )
            if st_result.get("success") and st_result["data"]["records"]:
                return st_result["data"]["records"]

    if not result.get("success"):
        print(f"WARNING: {result.get('error', 'unknown error')}", file=sys.stderr)
    return []


# ── Aggregation ────────────────────────────────────────────────────────

def aggregate(records: list[dict]) -> dict:
    """Aggregate daily records into totals."""
    totals = {
        "pv_kwh": 0.0,
        "cons_kwh": 0.0,
        "bat_charge_kwh": 0.0,
        "bat_dis_kwh": 0.0,
        "grid_kwh": 0.0,
        "grid_feed_kwh": 0.0,
    }
    days = []
    for rec in records:
        time_str = rec.get("time", "")
        pv   = parse_kwh(rec.get("Production", "0"))
        cons = parse_kwh(rec.get("Consumption", "0"))
        chg  = parse_kwh(rec.get("ChargingCapacity", "0"))
        dis  = parse_kwh(rec.get("DischargingCapacity", "0"))
        grid = parse_kwh(rec.get("ElectricityPurchasing", "0"))
        feed = parse_kwh(rec.get("GridFeed-in", "0"))

        totals["pv_kwh"]         += pv
        totals["cons_kwh"]       += cons
        totals["bat_charge_kwh"] += chg
        totals["bat_dis_kwh"]    += dis
        totals["grid_kwh"]       += grid
        totals["grid_feed_kwh"]  += feed

        days.append({
            "date":   time_str,
            "pv":     round(pv, 2),
            "cons":   round(cons, 2),
            "charge": round(chg, 2),
            "dis":    round(dis, 2),
            "grid":   round(grid, 2),
            "feed":   round(feed, 2),
        })

    return {"days": days, "totals": {k: round(v, 2) for k, v in totals.items()}}


# ── Output ─────────────────────────────────────────────────────────────

def fmt_vnd(n: int) -> str:
    """Format Vietnamese Dong, e.g. 282994 → '282.994₫', 7043 → '7.043₫'."""
    if n < 1000:
        return f"{n}₫"
    return f"{n:,}".replace(",", ".") + "₫"


def print_text(first: date, last: date, agg: dict, incomplete: bool = False) -> None:
    days = agg["days"]
    t    = agg["totals"]

    sep = "-" * 80
    header = (f"{'Ngày':<12} {'Solar':>7} {'Tải':>7} {'Pin nạp':>8} "
               f"{'Pin xả':>8} {'Lưới mua':>9} {'Feed-in':>9}")
    print(f"\n{'='*80}")
    print(f"  Báo cáo năng lượng {first.strftime('%m/%Y')}"
          f"{' — (hiện tại, chưa hoàn chỉnh)' if incomplete else ''}")
    print(f"{'='*80}")
    print(header)
    print(sep)

    for d in days:
        print(f"{d['date']:<12} {d['pv']:>7} {d['cons']:>7} {d['charge']:>8} "
              f"{d['dis']:>8} {d['grid']:>9} {d['feed']:>9}")

    print(sep)
    print(f"{'TỔNG':<12} {t['pv_kwh']:>7} {t['cons_kwh']:>7} "
          f"{t['bat_charge_kwh']:>8} {t['bat_dis_kwh']:>8} "
          f"{t['grid_kwh']:>9} {t['grid_feed_kwh']:>9}")
    print(sep)

    pv    = t["pv_kwh"]
    cons  = t["cons_kwh"]
    grid  = t["grid_kwh"]
    feed  = t["grid_feed_kwh"]
    net_bat = t["bat_charge_kwh"] - t["bat_dis_kwh"]
    self_suff = (pv / cons * 100) if cons > 0 else 0

    grid_bill, bill_no_solar, savings = calc_savings(cons, grid)
    avg_rate = (bill_no_solar / cons) if cons > 0 else 0

    print(f"\n  [Tổng kết]")
    print(f"    ☀️  Solar tạo ra     : {pv:>8.2f} kWh")
    print(f"    ⚡  Tải tiêu thụ    : {cons:>8.2f} kWh")
    print(f"    🔋  Pin nạp / xả    : +{t['bat_charge_kwh']:.2f} / -{t['bat_dis_kwh']:.2f} kWh  "
          f"(net {net_bat:+.2f} kWh)")
    print(f"    🏠  Lưới mua / bán  : {grid:.2f} / {feed:.2f} kWh")
    print(f"    🏠  Tự dùng         : {self_suff:.1f}%")
    print(f"\n  [Giá điện — EVN 6 bậc thang]")
    print(f"    ⚡  Điện mua lưới   : {grid:>7.2f} kWh  →  {fmt_vnd(grid_bill)}")
    print(f"    💡  Nếu không có solar: {cons:>6.2f} kWh →  {fmt_vnd(bill_no_solar)}")
    print(f"    💰  Tiết kiệm        : {savings:>7,}₫")
    print(f"    📊  Giá TB           : {avg_rate:>6.0f}₫/kWh")
    if incomplete:
        print(f"\n  ⚠️  Dữ liệu chưa hoàn chỉnh — tháng này chưa kết thúc.")
    print()


def build_json(first: date, last: date, agg: dict, incomplete: bool = False) -> dict:
    t    = agg["totals"]
    cons = t["cons_kwh"]
    grid = t["grid_kwh"]
    pv   = t["pv_kwh"]
    feed = t["grid_feed_kwh"]
    grid_bill, bill_no_solar, savings = calc_savings(cons, grid)
    avg_rate = round(bill_no_solar / cons, 0) if cons > 0 else 0

    return {
        "period": {
            "start": str(first),
            "end":   str(last),
            "incomplete": incomplete,
        },
        "daily_records": agg["days"],
        "totals_kwh": {
            "pv_kwh":          t["pv_kwh"],
            "cons_kwh":        t["cons_kwh"],
            "bat_charge_kwh":  t["bat_charge_kwh"],
            "bat_dis_kwh":     t["bat_dis_kwh"],
            "net_bat_kwh":     round(t["bat_charge_kwh"] - t["bat_dis_kwh"], 2),
            "grid_kwh":        t["grid_kwh"],
            "grid_feed_kwh":   t["grid_feed_kwh"],
            "self_sufficiency_pct": round(pv / cons * 100, 1) if cons > 0 else 0,
        },
        "financials_vnd": {
            "grid_bill_vnd":         grid_bill,
            "bill_without_solar_vnd": bill_no_solar,
            "savings_vnd":           savings,
            "avg_rate_vnd_per_kwh":  avg_rate,
        },
        "evn_tiers": [
            {"tier": 1, "from_kwh": 0,   "to_kwh": 50,  "rate_vnd": 1806},
            {"tier": 2, "from_kwh": 51,  "to_kwh": 100, "rate_vnd": 2062},
            {"tier": 3, "from_kwh": 101, "to_kwh": 200, "rate_vnd": 2357},
            {"tier": 4, "from_kwh": 201, "to_kwh": 300, "rate_vnd": 2838},
            {"tier": 5, "from_kwh": 301, "to_kwh": 400, "rate_vnd": 3338},
            {"tier": 6, "from_kwh": 401, "to_kwh": None,"rate_vnd": 4044},
        ],
    }


# ── Main ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Deye Cloud monthly energy analyzer.")
    parser.add_argument(
        "--date", default="this month",
        help="Month: YYYY-MM, tháng M/YYYY, 'this month', 'last month'",
    )
    parser.add_argument(
        "--end", default=None,
        help="End month for ranges (--date 2026-03 --end 2026-04 = Mar–Apr)",
    )
    parser.add_argument(
        "--output", "-o", choices=["text", "json"], default="text",
    )
    parser.add_argument("--device-sn", default=None)
    parser.add_argument("--env-path",  default=None)
    args = parser.parse_args()

    # Parse start month
    try:
        first, _ = parse_month(args.date)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse end month (optional)
    if args.end:
        try:
            _, last = parse_month(args.end)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        _, last = parse_month(args.date)

    if first > last:
        print("ERROR: --date must be before or equal to --end", file=sys.stderr)
        sys.exit(1)

    # Session — suppress deye_core status messages to stderr
    try:
        env_path = args.env_path or deye_core.DEFAULT_ENV_PATH()
        _old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            _, _, sn = deye_core.get_session(env_path=env_path)
        finally:
            sys.stderr = _old_stderr
        device_sn = args.device_sn or sn
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch
    records = fetch_daily_history(device_sn, env_path, first, last)
    if not records:
        print(f"Không có dữ liệu cho khoảng {first} → {last}. "
              f"Thiết bị có thể offline.", file=sys.stderr)
        sys.exit(1)

    # Filter records to the requested range
    filtered = [r for r in records if first <= date.fromisoformat(r["time"]) <= last]

    agg    = aggregate(filtered)
    today  = datetime.now(LOCAL_TZ).date()
    incomplete = first <= today <= last and today < last

    if args.output == "json":
        print(json.dumps(build_json(first, last, agg, incomplete),
                         indent=2, ensure_ascii=False))
    else:
        print_text(first, last, agg, incomplete)


if __name__ == "__main__":
    main()
