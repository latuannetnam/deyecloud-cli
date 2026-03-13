"""
Deye Inverter - Measure Points with Live Values
Run: python deye_measure_points.py

Displays all available measure points for the inverter,
with their current live values fetched from /device/latest.
"""
import requests
from deye_auth import get_session

# Logical grouping of measure point keys
GROUPS = {
    '☀️  Solar PV': [
        'DCVoltagePV1', 'DCVoltagePV2', 'DCVoltagePV3', 'DCVoltagePV4',
        'DCCurrentPV1', 'DCCurrentPV2', 'DCCurrentPV3', 'DCCurrentPV4',
        'DCPowerPV1', 'DCPowerPV2', 'DCPowerPV3', 'DCPowerPV4',
        'TotalDCInputPower',
    ],
    '⚡ AC Output / Grid': [
        'ACVoltageRUA', 'ACCurrentRUA', 'ACOutputFrequencyR',
        'InverterOutputPowerL1L2', 'GridVoltageL1L2', 'GridCurrentL1L2',
        'GridFrequency', 'ExternalCTPowerL1L2', 'TotalGridPower',
    ],
    '🏠 Load / Consumption': [
        'LoadVoltageL1L2', 'TotalConsumptionPower',
        'DailyConsumption', 'CumulativeConsumption',
    ],
    '🔋 Battery': [
        'BatteryVoltage', 'BatteryCurrent', 'BatteryPower', 'SOC',
        'BatteryRatedCapacity',
        'DailyChargingEnergy', 'DailyDischargingEnergy',
        'TotalChargeEnergy', 'TotalDischargeEnergy',
        'Temperature- Battery',
    ],
    '🌐 Grid Feed-in / Purchase': [
        'DailyGridFeedIn', 'CumulativeGridFeedIn',
        'DailyEnergyPurchased', 'CumulativeEnergyPurchased',
    ],
    '📊 Production': [
        'RatedPower', 'DailyActiveProduction', 'TotalActiveProduction',
    ],
    '🌡️  Temperature': [
        'DC Temperature', 'AC Temperature',
    ],
    '⚙️  Generator / UPS': [
        'GeneratorFrequency', 'GenVoltage',
        'TotalGeneratorProduction', 'UPSLoadPower', 'MIPower',
    ],
}


def main():
    base_url, headers, device_sn = get_session()
    print()

    # 1. Fetch measure point definitions
    resp = requests.post(f"{base_url}/device/measurePoints",
                         headers=headers, json={"deviceSn": device_sn}, timeout=15)
    mp_data = resp.json()
    if not mp_data.get('success'):
        print(f"Error fetching measure points: {mp_data.get('msg')}")
        return
    available_keys = set(mp_data.get('measurePoints', []))

    # 2. Fetch latest live values
    resp2 = requests.post(f"{base_url}/device/latest",
                          headers=headers, json={"deviceList": [device_sn]}, timeout=15)
    latest_data = resp2.json()
    live = {}
    if latest_data.get('success'):
        for dev in latest_data.get('deviceDataList', []):
            if dev['deviceSn'] == device_sn:
                for point in dev.get('dataList', []):
                    live[point['key']] = (point['value'], point.get('unit', ''))

    # 3. Print header
    device_type = mp_data.get('deviceType', 'DEVICE')
    product_id  = mp_data.get('productId', '')
    print(f"{'='*65}")
    print(f"  Measure Points — {device_sn} ({device_type}  |  product: {product_id})")
    print(f"  Total available: {len(available_keys)}")
    print(f"{'='*65}")

    # 4. Print by group
    printed = set()
    for group_name, keys in GROUPS.items():
        in_group = [k for k in keys if k in available_keys]
        if not in_group:
            continue
        print(f"\n  {group_name}")
        print(f"  {'-'*60}")
        for key in in_group:
            if key in live:
                val, unit = live[key]
                print(f"    {key:<35}  {val:>10} {unit}")
            else:
                print(f"    {key:<35}  {'(no live data)':>10}")
            printed.add(key)

    # 5. Print any ungrouped keys
    ungrouped = available_keys - printed
    if ungrouped:
        print(f"\n  📋 Other")
        print(f"  {'-'*60}")
        for key in sorted(ungrouped):
            if key in live:
                val, unit = live[key]
                print(f"    {key:<35}  {val:>10} {unit}")
            else:
                print(f"    {key:<35}  {'(no live data)':>10}")

    print(f"\n{'='*65}\n")


if __name__ == '__main__':
    main()
