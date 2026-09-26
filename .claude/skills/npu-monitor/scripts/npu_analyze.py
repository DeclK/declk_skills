#!/usr/bin/env python3
"""Analyse NPU AI Core utilisation CSV and produce a report + plot.

Usage:
    npu_analyze.py DATA.csv [--skip SEC] [--devices 0,1,2,3] [--threshold PCT] [--out-dir DIR]

Report columns (one row per device):
    Device   Low-Util Time %   Verdict

The verdict thresholds (ai_core_pct < THRESHOLD):
    > 30 %  →  BAD
    10–30 % →  MODERATE
    < 10 %  →  GOOD
"""

import argparse
import os
import sys
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use('Agg')                     # headless-safe
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERDICT_BAD_THRESHOLD      = 30.0   # >30 % low-util → BAD
VERDICT_MODERATE_THRESHOLD = 10.0   # 10-30 % → MODERATE; <10 % → GOOD

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def load_and_filter(csv_path: str, skip_sec: float, devices: list[int] | None
                    ) -> tuple[pd.DataFrame, float, float]:
    """Read CSV, optionally skip early samples, filter by device list.

    Returns (df, t_min, t_max) where *t_min* / *t_max* are seconds since the
    first *retained* timestamp.
    """
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    if devices:
        df = df[df['npu_id'].isin(devices)]

    if df.empty:
        print("[error] no data after device filter", file=sys.stderr)
        sys.exit(1)

    t0 = df['timestamp'].min()
    df['t_sec'] = (df['timestamp'] - t0).dt.total_seconds()

    if skip_sec > 0:
        df = df[df['t_sec'] >= skip_sec]

    if df.empty:
        print(f"[error] no data after --skip {skip_sec}s", file=sys.stderr)
        sys.exit(1)

    # Re-base time so plot starts at 0
    t_min = df['t_sec'].min()
    t_max = df['t_sec'].max()
    df['t_sec'] -= t_min

    return df, t_min, t_max


def downsample(df: pd.DataFrame, max_samples: int) -> pd.DataFrame:
    """Truncate each device to at most *max_samples* rows (keep the first N per device).

    A value of 0 or a device that already has ``<= max_samples`` rows is
    left untouched.
    """
    if max_samples <= 0:
        return df

    parts = []
    for npu_id, grp in df.groupby('npu_id', sort=False):
        grp = grp.sort_values('t_sec')               # ensure time order
        parts.append(grp.head(max_samples))

    return pd.concat(parts, ignore_index=True)


def compute_report(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Return per-device summary: low-util % and verdict string."""
    rows = []
    for npu_id, grp in df.groupby('npu_id'):
        total   = len(grp)
        low_cnt = (grp['ai_core_pct'] < threshold).sum()
        low_pct = low_cnt / total * 100.0

        if low_pct > VERDICT_BAD_THRESHOLD:
            verdict = 'BAD'
        elif low_pct >= VERDICT_MODERATE_THRESHOLD:
            verdict = 'MODERATE'
        else:
            verdict = 'GOOD'

        rows.append({
            'Device':           int(npu_id),
            'Low-Util Time %':  round(low_pct, 1),
            'Verdict':          verdict,
            '_total_samples':   total,
            '_low_samples':     low_cnt,
        })
    return pd.DataFrame(rows).sort_values('Device').reset_index(drop=True)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_devices(df: pd.DataFrame, threshold: float, devices: list[int],
                 out_png: str) -> None:
    """Stacked subplots (one per device), shared x-axis, tab20 colours."""
    n = len(devices)
    if n == 0:
        print("[error] no devices to plot", file=sys.stderr)
        return

    cmap = plt.get_cmap('tab20', n)

    fig, axes = plt.subplots(n, 1, figsize=(14, 2.2 * n), sharex=True)
    if n == 1:
        axes = [axes]

    for idx, npu_id in enumerate(devices):
        ax = axes[idx]
        grp = df[df['npu_id'] == npu_id]
        if grp.empty:
            ax.text(0.5, 0.5, f'NPU {npu_id}: no data', transform=ax.transAxes,
                    ha='center', va='center', fontsize=10, color='gray')
            ax.set_ylabel(f'NPU {npu_id}', fontsize=9)
            continue

        color = cmap(idx)
        ax.plot(grp['t_sec'], grp['ai_core_pct'], linewidth=0.6, color=color)

        # Threshold line
        ax.axhline(y=threshold, color='red', linestyle='--', linewidth=0.8, alpha=0.7)

        ax.set_ylabel(f'NPU {npu_id}', fontsize=9)
        ax.set_ylim(-5, 105)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(25))

        # Legend: low-util % for this device
        total   = len(grp)
        low_cnt = (grp['ai_core_pct'] < threshold).sum()
        low_pct = low_cnt / total * 100.0
        ax.legend(
            [f'AI Core (%)', f'Threshold ({threshold}%)'],
            loc='upper right', fontsize=7,
        )
        ax.text(
            0.99, 0.05,
            f'Low-util: {low_pct:.1f}% ({low_cnt}/{total})',
            transform=ax.transAxes, fontsize=7, ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7),
        )

    axes[-1].set_xlabel('Elapsed time (s)')
    fig.suptitle(
        f'NPU AI Core Utilisation  —  threshold = {threshold}%',
        fontsize=12, fontweight='bold',
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Plot saved → {out_png}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Analyse NPU AI Core utilisation CSV → report + plot',
    )
    parser.add_argument(
        'csv_file', type=str,
        help='Path to CSV produced by npu_monitor.py',
    )
    parser.add_argument(
        '--skip', type=float, default=0.0,
        help='Skip the first N seconds of data (cold-start)',
    )
    parser.add_argument(
        '--devices', '-d', type=str, default='',
        help='Comma-separated NPU ids to analyse (default: all in CSV)',
    )
    parser.add_argument(
        '--threshold', '-t', type=float, default=20.0,
        help='Low-utilisation threshold %% (default: 20)',
    )
    parser.add_argument(
        '--max-samples', type=int, default=0,
        help='Max samples PER DEVICE — truncate to first N rows (0 = no limit). '
             'E.g. --max-samples 1000 with 16 devices → 16000 total rows.',
    )
    parser.add_argument(
        '--out-dir', '-o', type=str, default='',
        help='Output directory for plot PNG (default: same dir as CSV)',
    )
    args = parser.parse_args()

    # ---- resolve devices ---------------------------------------------------
    device_list = None
    if args.devices:
        device_list = [int(x.strip()) for x in args.devices.split(',') if x.strip()]

    # ---- load & filter -----------------------------------------------------
    df, t_min, t_max = load_and_filter(args.csv_file, args.skip, device_list)

    # ---- downsample --------------------------------------------------------
    if args.max_samples > 0:
        df = downsample(df, args.max_samples)

    # ---- determine device order for plot -----------------------------------
    plot_devices_list = device_list if device_list else sorted(df['npu_id'].unique())

    # ---- report ------------------------------------------------------------
    report = compute_report(df, args.threshold)

    print()
    print(f"{'='*50}")
    print(f"  NPU AI Core Utilisation Report")
    print(f"{'='*50}")
    print(f"  Data file:     {args.csv_file}")
    print(f"  Time range:    {t_min:.0f}s – {t_max:.0f}s  ({t_max - t_min:.0f}s)")
    print(f"  Threshold:     {args.threshold}%")
    if args.skip > 0:
        print(f"  Skipped first: {args.skip}s")
    print(f"{'='*50}")
    print()
    print(report[['Device', 'Low-Util Time %', 'Verdict']].to_string(index=False))
    print()

    # ---- overall summary -----------------------------------------------------
    total_samples = df.shape[0]
    low_samples   = (df['ai_core_pct'] < args.threshold).sum()
    overall_pct   = low_samples / total_samples * 100.0
    print(f"  Overall:       {overall_pct:.1f}% low-util  ({low_samples}/{total_samples} samples)")
    print()

    # ---- plot --------------------------------------------------------------
    base = os.path.splitext(os.path.basename(args.csv_file))[0]
    out_dir = args.out_dir if args.out_dir else os.path.dirname(args.csv_file) or '.'
    out_png = os.path.join(out_dir, f'{base}_analysis.png')

    plot_devices(df, args.threshold, plot_devices_list, out_png)

    print(f"Done — {len(plot_devices_list)} device(s) analysed.")


if __name__ == '__main__':
    main()
