#!/usr/bin/env python3
"""Monitor NPU AI Core utilization via npu-smi info and log to CSV.

Usage:
    npu_monitor.py [--interval SEC] [--devices 0,1,2,3] [--output FILE]

Parses the box-drawing table from `npu-smi info` — one call captures all devices.
Output CSV columns: timestamp, npu_id, ai_core_pct, power_w, temp_c
"""

import subprocess
import sys
import time
import csv
import signal
import argparse
from datetime import datetime


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_npu_info(output: str):
    """Parse the box-drawing table from ``npu-smi info``.

    Each NPU occupies two rows in the upper device table::

        | 0     910B2C              | OK  | 90.4  42  0 / 0             |
        | 0                         | ... | 0      0 / 0  3456 / 65536  |

    The *first* row of each pair carries power / temp; the *second* carries
    ai_core_pct.  After the device table there is a process table that we
    skip entirely.

    Returns
    -------
    list[dict]
        Dict keys: ``npu_id``, ``ai_core_pct``, ``power_w``, ``temp_c``.
    """
    devices: list[dict] = []
    in_process_section = False
    pending_npu: dict | None = None

    for raw_line in output.strip().splitlines():
        line = raw_line.strip()

        # --- detect start of process table -------------------------------
        if '| NPU' in line and 'Process id' in line:
            in_process_section = True
            continue

        if in_process_section:
            continue

        # --- skip non-data lines -----------------------------------------
        if '|' not in line:
            continue
        if '===' in line or '---' in line:
            continue
        if 'AICore(%)' in line or 'Hugepages-Usage' in line:
            continue
        if line.startswith('| npu-smi') or 'Version' in line:
            continue

        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4:
            continue

        col1 = parts[1]   # e.g. "0     910B2C"  or  "0"
        col3 = parts[3]   # e.g. "90.4  42  0 / 0"  or  "0  0 / 0  3456 / 65536"

        tokens1 = col1.split()
        if not tokens1:
            continue

        first_token = tokens1[0]

        # Skip rows whose first column is non-numeric (headers, "No running
        # processes…" lines, etc.)
        if not first_token.isdigit():
            continue

        tokens3 = col3.split()
        if not tokens3:
            continue

        # Heuristic: NPU row → col1 has *two or more* tokens (id + name);
        #            Chip row → col1 has *one* token (just chip id).
        if len(tokens1) >= 2:
            # ── NPU row ──────────────────────────────────────────────────
            try:
                npu_id = int(tokens1[0])
                power_w = float(tokens3[0])
                temp_c = int(tokens3[1])
            except (ValueError, IndexError):
                continue
            pending_npu = {
                'npu_id': npu_id,
                'power_w': power_w,
                'temp_c': temp_c,
                'ai_core_pct': 0,  # filled by the following Chip row
            }
        else:
            # ── Chip row ─────────────────────────────────────────────────
            if pending_npu is None:
                continue
            try:
                ai_core = int(tokens3[0])
            except ValueError:
                continue
            pending_npu['ai_core_pct'] = ai_core
            devices.append(pending_npu)
            pending_npu = None

    return devices


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def measure_npu_smi_latency() -> float:
    """Time a single ``npu-smi info`` call so we can warn about interval."""
    t0 = time.perf_counter()
    subprocess.run(['npu-smi', 'info'], capture_output=True, text=True)
    return time.perf_counter() - t0


def auto_detect_devices() -> list[int]:
    """Return sorted list of NPU ids visible via ``npu-smi info``."""
    result = subprocess.run(['npu-smi', 'info'], capture_output=True, text=True)
    if result.returncode != 0:
        print("[error] npu-smi info failed during device detection", file=sys.stderr)
        return []
    return [d['npu_id'] for d in parse_npu_info(result.stdout)]


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

def collect(interval: float, devices: list[int], output_file: str) -> None:
    overhead = measure_npu_smi_latency()
    actual_interval = max(interval, overhead)
    if interval < overhead:
        print(
            f"[warn] npu-smi info takes ~{overhead:.1f}s, "
            f"requested interval {interval}s is too small; "
            f"actual interval will be ~{actual_interval:.1f}s",
            file=sys.stderr,
        )

    all_devices = auto_detect_devices()
    target = devices if devices else all_devices
    if devices:
        unknown = set(devices) - set(all_devices)
        if unknown:
            print(f"[warn] requested devices not found: {sorted(unknown)}", file=sys.stderr)

    print(f"Starting NPU monitor")
    print(f"  interval:          {interval}s (requested), ~{actual_interval:.1f}s (actual)")
    print(f"  npu-smi overhead:  ~{overhead:.1f}s")
    print(f"  devices:           {target}")
    print(f"  output:            {output_file}")
    print(f"  Press Ctrl+C to stop.\n")

    # Write CSV header
    with open(output_file, 'w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['timestamp', 'npu_id', 'ai_core_pct', 'power_w', 'temp_c'])

    running = True

    def _sigint_handler(_sig, _frame):
        nonlocal running
        print("\n[signal] Ctrl+C received — stopping …")
        running = False

    signal.signal(signal.SIGINT, _sigint_handler)

    sample_count = 0
    try:
        while running:
            t0 = time.perf_counter()
            result = subprocess.run(['npu-smi', 'info'], capture_output=True, text=True)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if result.returncode != 0:
                print(f"[error] npu-smi info failed: {result.stderr}", file=sys.stderr)
                _sleep = max(0.1, interval)
                time.sleep(_sleep)
                continue

            parsed = parse_npu_info(result.stdout)
            if not parsed:
                print(f"[warn] [{timestamp}] no device data parsed — skipping sample", file=sys.stderr)
                _sleep = max(0.1, interval)
                time.sleep(_sleep)
                continue

            with open(output_file, 'a', newline='') as fh:
                writer = csv.writer(fh)
                for dev in parsed:
                    if devices and dev['npu_id'] not in devices:
                        continue
                    writer.writerow([
                        timestamp,
                        dev['npu_id'],
                        dev['ai_core_pct'],
                        dev['power_w'],
                        dev['temp_c'],
                    ])

            sample_count += 1
            ai_cores = [
                str(d['ai_core_pct'])
                for d in parsed
                if (not devices) or (d['npu_id'] in devices)
            ]
            print(f"[{timestamp}] sample={sample_count}  ai_core=[{','.join(ai_cores)}]")

            elapsed = time.perf_counter() - t0
            sleep_left = max(0.0, interval - elapsed)
            if sleep_left > 0:
                time.sleep(sleep_left)

    except KeyboardInterrupt:
        pass

    print(f"\nDone — {sample_count} samples written to {output_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Monitor NPU AI Core utilization → CSV',
    )
    parser.add_argument(
        '--interval', '-n', type=float, default=1.0,
        help='Sampling interval in seconds (default: 1.0)',
    )
    parser.add_argument(
        '--devices', '-d', type=str, default='',
        help='Comma-separated NPU ids to monitor (default: all detected)',
    )
    parser.add_argument(
        '--output', '-o', type=str, default='',
        help='Output CSV path (default: npu_usage_YYYYmmdd_HHMMSS.csv)',
    )
    args = parser.parse_args()

    device_list: list[int] = []
    if args.devices:
        device_list = [int(x.strip()) for x in args.devices.split(',') if x.strip()]

    output = args.output
    if not output:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output = f'npu_usage_{ts}.csv'

    collect(args.interval, device_list, output)


if __name__ == '__main__':
    main()
