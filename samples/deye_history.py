"""
Deye Inverter - Historical Data
Run: python deye_history.py
Credentials and cache are managed automatically via .env
"""
import requests
from datetime import datetime, timezone, timedelta, date

from deye_auth import get_session

LOCAL_TZ = timezone(timedelta(hours=7))  # UTC+7 (Vietnam)
TODAY = date.today().strftime('%Y-%m-%d')
THIS_MONTH = date.today().strftime('%Y-%m')
MONTH_START = date.today().replace(day=1).strftime('%Y-%m-%d')


def fmt_time(raw):
    """Convert Unix timestamp or date string to readable local time."""
    try:
        return datetime.fromtimestamp(int(raw), tz=LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return str(raw)


def fetch(base_url, headers, payload):
    url = base_url + '/device/history'
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    return resp.json()


def print_section(label, data, show_last=None):
    print(f'\n{"="*70}')
    print(f'  {label}')
    print('='*70)
    if not data.get('success'):
        print(f'  Error: {data.get("msg")} (code={data.get("code")})')
        return
    rows = data.get('dataList', [])
    print(f'  Total records: {len(rows)}')
    if show_last:
        rows = rows[-show_last:]
    for row in rows:
        t = fmt_time(row.get('time', row.get('collectTime', '')))
        items = {it['key']: f"{it['value']} {it['unit']}" for it in row.get('itemList', [])}
        parts = '  |  '.join(f"{k}: {v}" for k, v in items.items())
        print(f"  {t}  {parts}")


# ── Bootstrap: auto-auth + device discovery ───────────────────────────────
base_url, headers, DEVICE_SN = get_session()
print()

# ── 1. Intraday today ────────────────────────────────────────────────────
print_section(
    f'TODAY {TODAY} — intraday (last 20 of 5-min readings)',
    fetch(base_url, headers, {
        'deviceSn': DEVICE_SN, 'granularity': 1,
        'startAt': TODAY, 'endAt': TODAY,
        'measurePoints': ['TotalDCInputPower', 'TotalConsumptionPower', 'SOC', 'BatteryPower', 'TotalGridPower']
    }),
    show_last=20
)

# ── 2. Daily totals — current month ──────────────────────────────────────
print_section(
    f'{THIS_MONTH} — daily totals (granularity=2)',
    fetch(base_url, headers, {
        'deviceSn': DEVICE_SN, 'granularity': 2,
        'startAt': MONTH_START, 'endAt': TODAY,
    })
)

# ── 3. Monthly totals — last 12 months ───────────────────────────────────
today = date.today()
# Go back 11 months to get a 12-month window (current month inclusive)
if today.month > 11:
    start_month = today.replace(year=today.year - 1, month=today.month - 11, day=1)
else:
    start_month = today.replace(year=today.year - 1, month=today.month + 1, day=1)
print_section(
    'LAST 12 MONTHS — monthly totals (granularity=3)',
    fetch(base_url, headers, {
        'deviceSn': DEVICE_SN, 'granularity': 3,
        'startAt': start_month.strftime('%Y-%m'),
        'endAt': THIS_MONTH,
    })
)
