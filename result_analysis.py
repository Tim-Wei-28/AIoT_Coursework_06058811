import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, wilcoxon
from pathlib import Path
import os

# CONFIGURATION
BASE      = Path(__file__).parent
HR_DIR    = BASE / "11_heart_rate_data"
NOISE_DIR = BASE / "12_noise_level_data"
OUT_DIR   = BASE / "20_results"
OUT_DIR.mkdir(exist_ok=True)

NIGHTS = [
    ("Night 1", "Normal",      "day2.csv"),
    ("Night 2", "Normal",      "day3.csv"),
    ("Night 3", "Added Noise", "day4.csv"),
    ("Night 4", "Normal",      "day5.csv"),
    ("Night 5", "Added Noise", "day6.csv"),
    ("Night 6", "Normal",      "day7.csv"),
    ("Night 7", "Added Noise", "day8.csv"),
    ("Night 8", "Added Noise", "day9.csv"),
]

NORMAL_IDX = [0, 1, 3, 5]   
NOISE_IDX  = [2, 4, 6, 7]   

C_BLUE  = "#0000D3"
C_PINK  = "#FF1A99"
C_AMBER = "#e67e00"
C_BG    = "#f8f9ff"

NOISE_THRESHOLD = 50
MIN_GAP_S       = 20
WINDOW_PRE      = 30
WINDOW_POST     = 60

LAG_MAX   = 120
KEY_LAGS  = [0, 5, 10, 15, 30, 60, 90, 120]

DPI = 150


# SECTION 1: DATA LOADING
def load_night(fname):
    """Load one night, merge HR and noise on seconds, interpolate gaps."""
    hr_path    = HR_DIR    / fname
    noise_path = NOISE_DIR / fname

    hr_df = pd.read_csv(hr_path, names=["seconds", "hr"], skiprows=1)
    hr_df["seconds"] = hr_df["seconds"].round().astype(int)

    noise_df = pd.read_csv(noise_path, sep=";", names=["seconds", "db"], skiprows=1)
    noise_df["seconds"] = noise_df["seconds"].astype(int)

    df = (pd.merge(hr_df, noise_df, on="seconds", how="outer")
            .sort_values("seconds").reset_index(drop=True))
    df["hr"] = df["hr"].interpolate(limit_direction="both")
    df["db"] = df["db"].interpolate(limit_direction="both")

    hr_arr = df["hr"].to_numpy(dtype=float)
    db_arr = df["db"].to_numpy(dtype=float)
    return hr_arr, db_arr


print("=" * 60)
print("  result_analysis.py  --  Sleep Quality Analysis")
print("=" * 60)
print()
print("Loading data...")

night_data = []
for label, ntype, fname in NIGHTS:
    hr_arr, db_arr = load_night(fname)
    night_data.append({
        "label": label,
        "type":  ntype,
        "hr":    hr_arr,
        "db":    db_arr,
    })
    print(f"  Loaded {label} ({ntype}): {len(hr_arr)} samples")

print()


# SECTION 2: PER-NIGHT STATISTICS
print("Computing per-night statistics...")

def compute_stats(hr, db):
    diffs = np.diff(hr)
    rmssd = float(np.sqrt(np.mean(diffs ** 2)))
    r_val, p_val = pearsonr(hr, db)
    stats = {
        "hr_mean":           float(np.mean(hr)),
        "hr_min":            float(np.min(hr)),
        "hr_max":            float(np.max(hr)),
        "hr_std":            float(np.std(hr)),
        "noise_mean":        float(np.mean(db)),
        "noise_min":         float(np.min(db)),
        "noise_max":         float(np.max(db)),
        "noise_std":         float(np.std(db)),
        "pct_below_35":      float(np.mean(db < 35) * 100),
        "rmssd":             rmssd,
        "pearson_r":         float(r_val),
        "pearson_p":         float(p_val),
        "sleep_duration_min": len(hr) / 60.0,
    }
    return stats

for nd in night_data:
    nd["stats"] = compute_stats(nd["hr"], nd["db"])

# Print stats table 
print()
print("=" * 110)
print("  PER-NIGHT STATISTICS TABLE")
print("=" * 110)
hdr = (f"{'Night':<10} {'Type':<12} {'HR Mean':>8} {'HR Min':>7} {'HR Max':>7} {'HR Std':>7} "
       f"{'N Mean':>7} {'N Min':>6} {'N Max':>6} {'N Std':>6} "
       f"{'<35%':>6} {'RMSSD':>7} {'r':>7} {'Dur(m)':>7}")
print(hdr)
print("-" * 110)
for nd in night_data:
    s = nd["stats"]
    print(f"{nd['label']:<10} {nd['type']:<12} "
          f"{s['hr_mean']:>8.2f} {s['hr_min']:>7.1f} {s['hr_max']:>7.1f} {s['hr_std']:>7.2f} "
          f"{s['noise_mean']:>7.2f} {s['noise_min']:>6.2f} {s['noise_max']:>6.2f} {s['noise_std']:>6.2f} "
          f"{s['pct_below_35']:>6.1f} {s['rmssd']:>7.3f} {s['pearson_r']:>7.4f} {s['sleep_duration_min']:>7.1f}")
print("=" * 110)
print()


# SECTION 3: LAGGED CROSS-CORRELATION
print("Computing xcorr...")

def fast_xcorr(hr, db, lag_max):
    """Pearson r between noise[t] and HR[t+lag] for each lag in -lag_max..+lag_max."""
    lags = np.arange(-lag_max, lag_max + 1)
    rs   = np.zeros(len(lags))
    hr_z  = (hr  - hr.mean())  / (hr.std()  + 1e-12)
    db_z  = (db  - db.mean())  / (db.std()  + 1e-12)
    n_tot = len(hr)
    for k, lag in enumerate(lags):
        if lag >= 0:
            if lag == 0:
                n = n_tot
                rs[k] = float(np.dot(db_z, hr_z)) / n
            else:
                n = n_tot - lag
                rs[k] = float(np.dot(db_z[:n], hr_z[lag:lag+n])) / n
        else:
            pos = -lag
            n   = n_tot - pos
            rs[k] = float(np.dot(db_z[pos:pos+n], hr_z[:n])) / n
    return lags, rs

xcorr_results = []
for nd in night_data:
    lags, rs = fast_xcorr(nd["hr"], nd["db"], LAG_MAX)
    nd["xcorr_lags"] = lags
    nd["xcorr_rs"]   = rs
    xcorr_results.append(rs)

xcorr_arr = np.array(xcorr_results)   
lags_ref  = night_data[0]["xcorr_lags"]

weights = np.array([np.sqrt(len(nd["hr"])) for nd in night_data])
w_normal = weights[NORMAL_IDX];  w_noise = weights[NOISE_IDX]
avg_normal = np.average(xcorr_arr[NORMAL_IDX], axis=0, weights=w_normal)
avg_noise  = np.average(xcorr_arr[NOISE_IDX],  axis=0, weights=w_noise)
grand_mean = np.average(xcorr_arr, axis=0, weights=weights)

def lag_idx(lag):
    return int(lag + LAG_MAX)

# Print per-night xcorr results 
print()
print("=" * 80)
print("  LAGGED CROSS-CORRELATION RESULTS  (noise[t] vs HR[t+lag])")
print("=" * 80)
for nd in night_data:
    rs = nd["xcorr_rs"]
    peak_pos_idx  = np.argmax(rs)
    peak_abs_idx  = np.argmax(np.abs(rs))
    print(f"  {nd['label']} ({nd['type']}):")
    print(f"    Peak positive  : lag = {lags_ref[peak_pos_idx]:>+4d}s,  r = {rs[peak_pos_idx]:>+.4f}")
    print(f"    Peak |r|       : lag = {lags_ref[peak_abs_idx]:>+4d}s,  r = {rs[peak_abs_idx]:>+.4f}")
    kv = "  ".join([f"r({l:+d}s)={rs[lag_idx(l)]:>+.4f}" for l in KEY_LAGS])
    print(f"    Key lags       : {kv}")
print()

# Print aggregated xcorr 
print("  AGGREGATED CROSS-CORRELATION:")
gm_peak_idx     = np.argmax(grand_mean)
gm_peak_abs_idx = np.argmax(np.abs(grand_mean))
print(f"    Grand mean peak positive : lag = {lags_ref[gm_peak_idx]:>+4d}s,  r = {grand_mean[gm_peak_idx]:>+.4f}")
print(f"    Grand mean peak |r|      : lag = {lags_ref[gm_peak_abs_idx]:>+4d}s,  r = {grand_mean[gm_peak_abs_idx]:>+.4f}")
kv = "  ".join([f"r({l:+d}s)={grand_mean[lag_idx(l)]:>+.4f}" for l in KEY_LAGS])
print(f"    Key lags                 : {kv}")

print()
print("  ASCII bar chart of grand mean xcorr (step=5s):")
print(f"  {'Lag':>6}  {'r':>7}  bar")
print("  " + "-" * 50)
BAR_SCALE = 40
for lag in range(-LAG_MAX, LAG_MAX + 1, 5):
    r_val  = grand_mean[lag_idx(lag)]
    bar_len = int(abs(r_val) * BAR_SCALE)
    bar_str = "#" * bar_len
    sign    = "+" if r_val >= 0 else "-"
    print(f"  {lag:>+6d}s  {r_val:>+7.4f}  {sign}{bar_str}")
print("=" * 80)
print()


# SECTION 4: PEAK-ALIGNED HR RESPONSE
print("Computing peak-aligned HR response...")

def detect_peaks(db_arr, threshold, min_gap_s):
    """Find local maxima above threshold, enforcing minimum gap between peaks."""
    db_list = list(db_arr)
    n, peaks, last_t, i = len(db_list), [], -min_gap_s, 0
    while i < n:
        if db_list[i] > threshold:
            run_start = i
            while i < n and db_list[i] > threshold:
                i += 1
            if run_start - last_t >= min_gap_s:
                chunk  = db_list[run_start:i]
                t_peak = run_start + chunk.index(max(chunk))
                peaks.append(t_peak)
                last_t = t_peak
        else:
            i += 1
    return peaks

wlen = WINDOW_PRE + WINDOW_POST

all_event_windows = []  
all_delta_hrs     = []

for nd in night_data:
    hr  = nd["hr"]
    db  = nd["db"]
    n   = len(hr)
    peaks = detect_peaks(db, NOISE_THRESHOLD, MIN_GAP_S)

    windows   = []
    delta_hrs = []
    for t in peaks:
        if t - WINDOW_PRE < 15 or t + WINDOW_POST + 15 >= n:
            continue
        baseline = float(np.mean(hr[t - 15: t - 3]))
        window   = hr[t - WINDOW_PRE: t + WINDOW_POST] - baseline
        if len(window) != wlen:
            continue
        windows.append(window)
        delta_hrs.append(float(hr[t + 5] - hr[t - 5]))

    nd["peak_windows"]  = windows
    nd["peak_deltas"]   = delta_hrs
    nd["n_valid_peaks"] = len(delta_hrs)

    all_event_windows.extend(windows)
    all_delta_hrs.extend(delta_hrs)

def peak_stats(deltas):
    if not deltas:
        return 0, 0.0, 0.0, 0.0
    arr = np.array(deltas)
    pct = float(np.mean(arr > 0) * 100)
    return len(deltas), float(np.mean(arr)), float(np.median(arr)), pct

# Print per-night peak response 
print()
print("=" * 80)
print("  PEAK-ALIGNED HR RESPONSE  (threshold={} dB, min_gap={}s)".format(
    NOISE_THRESHOLD, MIN_GAP_S))
print("=" * 80)
print(f"  {'Night':<10} {'Type':<12} {'N Peaks':>8} {'Mean dHR':>10} {'Med dHR':>9} {'Pct Inc%':>9}")
print("  " + "-" * 62)
for nd in night_data:
    np_, mean_d, med_d, pct_d = peak_stats(nd["peak_deltas"])
    print(f"  {nd['label']:<10} {nd['type']:<12} {np_:>8d} {mean_d:>10.3f} {med_d:>9.3f} {pct_d:>9.1f}")
print("  " + "-" * 62)
np_, mean_d, med_d, pct_d = peak_stats(all_delta_hrs)
print(f"  {'All Nights':<10} {'---':<12} {np_:>8d} {mean_d:>10.3f} {med_d:>9.3f} {pct_d:>9.1f}")
print("=" * 80)
print()

# Wilcoxon signed-rank test
print("=" * 80)
print("  WILCOXON SIGNED-RANK TEST: Is median delta-HR significantly != 0?")
print("=" * 80)
print()

def run_wilcoxon(deltas, label):
    if len(deltas) < 10:
        print(f"  {label}: insufficient events (n={len(deltas)}) — skipped")
        return
    stat, p = wilcoxon(deltas, alternative='two-sided')
    n       = len(deltas)
    median  = float(np.median(deltas))
    sig     = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
    print(f"  {label}")
    print(f"    n = {n}  |  median delta-HR = {median:+.3f} BPM  |  W = {stat:.1f}  |  p = {p:.4f}  {sig}")
    print()

print("  Per-night results:")
print()
for nd in night_data:
    run_wilcoxon(nd["peak_deltas"], f"{nd['label']} ({nd['type']})")

print("  Combined (all nights, all events):")
print()
run_wilcoxon(all_delta_hrs, "All Nights")

# SECTION 5: SAVE FIGURES
def fig_save(fig, name):
    path = OUT_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {path}")

def night_color(ntype):
    return C_BLUE if ntype == "Normal" else C_AMBER

# Build a styled matplotlib table 
def make_table_fig(col_headers, rows, col_widths=None, row_colors=None,
                   title="", figsize=(14, 5)):
    """Generic helper to create a styled matplotlib table figure."""
    n_rows = len(rows)
    n_cols = len(col_headers)

    fig, ax = plt.subplots(figsize=figsize, facecolor=C_BG)
    ax.set_facecolor(C_BG)
    ax.axis('off')

    if col_widths is None:
        col_widths = [1.0 / n_cols] * n_cols

    all_data   = [col_headers] + rows
    cell_colors = []

    header_colors = ["#0000A0"] * n_cols
    cell_colors.append(header_colors)

    for i in range(n_rows):
        if row_colors and i < len(row_colors):
            cell_colors.append(row_colors[i])
        else:
            shade = "#e8eaff" if i % 2 == 0 else "#f8f9ff"
            cell_colors.append([shade] * n_cols)

    tbl = ax.table(
        cellText=all_data,
        cellLoc='center',
        loc='center',
        cellColours=cell_colors,
        colWidths=col_widths,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.6)

    for j in range(n_cols):
        cell = tbl[0, j]
        cell.set_text_props(color='white', fontweight='bold')
        cell.set_edgecolor('#cccccc')

    for i in range(1, n_rows + 1):
        row_data = rows[i - 1]
        for j in range(n_cols):
            cell = tbl[i, j]
            cell.set_edgecolor('#cccccc')
            if j == 0:  
                cell.set_text_props(color=C_BLUE, fontweight='bold')
            if j == 1 and i > 0:
                txt = row_data[1] if len(row_data) > 1 else ""
                if txt == "Normal":
                    cell.set_text_props(color=C_BLUE)
                elif txt in ("Added Noise", "Noise"):
                    cell.set_text_props(color=C_AMBER)

    if title:
        ax.set_title(title, fontsize=11, fontweight='bold', color='#222222', pad=10)

    return fig


# (a) table_night_stats.png 
print("Saving table_night_stats.png...")

col_headers = ["Night", "Type", "HR Mean", "HR Min", "HR Max", "HR Std",
               "N Mean", "N Min", "N Max", "N Std",
               "< 35%", "RMSSD", "Pearson r", "Dur (min)"]

rows = []
for nd in night_data:
    s = nd["stats"]
    rows.append([
        nd["label"],
        nd["type"],
        f"{s['hr_mean']:.1f}",
        f"{s['hr_min']:.0f}",
        f"{s['hr_max']:.0f}",
        f"{s['hr_std']:.2f}",
        f"{s['noise_mean']:.1f}",
        f"{s['noise_min']:.1f}",
        f"{s['noise_max']:.1f}",
        f"{s['noise_std']:.2f}",
        f"{s['pct_below_35']:.1f}",
        f"{s['rmssd']:.3f}",
        f"{s['pearson_r']:.4f}",
        f"{s['sleep_duration_min']:.0f}",
    ])

col_w = [0.09, 0.10, 0.08, 0.07, 0.07, 0.07,
         0.08, 0.07, 0.07, 0.07, 0.06, 0.07, 0.08, 0.08]

fig = make_table_fig(col_headers, rows, col_widths=col_w,
                     title="Per-Night Sleep Statistics (8 Nights)",
                     figsize=(18, 5))
fig_save(fig, "table_night_stats.png")


# (b) chart_boxplot_hr.png 
print("Saving chart_boxplot_hr.png...")

fig, ax = plt.subplots(figsize=(12, 5), facecolor=C_BG)
ax.set_facecolor(C_BG)

hr_arrays = [nd["hr"] for nd in night_data]
bp = ax.boxplot(hr_arrays, patch_artist=True, widths=0.55, medianprops=dict(color='white', linewidth=2))

for i, (patch, nd) in enumerate(zip(bp['boxes'], night_data)):
    color = night_color(nd["type"])
    patch.set_facecolor(color)
    patch.set_alpha(0.75)
    patch.set_edgecolor('#333333')

for element in ['whiskers', 'caps', 'fliers']:
    for item in bp[element]:
        item.set_color('#555555')

ax.axhline(60, color='grey', linestyle='--', linewidth=1, alpha=0.7, label='60 BPM (typical resting HR)')
ax.set_xticks(range(1, 9))
ax.set_xticklabels([f"N{i+1}" for i in range(8)])
ax.set_xlabel("Night", fontsize=11)
ax.set_ylabel("Heart Rate (BPM)", fontsize=11)
ax.set_title("HR Distribution per Night", fontsize=12, fontweight='bold')
legend_handles = [
    mpatches.Patch(facecolor=C_BLUE,  edgecolor='#333', label='Normal Night'),
    mpatches.Patch(facecolor=C_AMBER, edgecolor='#333', label='Added Noise Night'),
    plt.Line2D([0], [0], color='grey', linestyle='--', label='60 BPM reference'),
]
ax.legend(handles=legend_handles, fontsize=9)
ax.grid(axis='y', alpha=0.3)
fig.tight_layout()
fig_save(fig, "chart_boxplot_hr.png")


# (c) chart_boxplot_noise.png 
print("Saving chart_boxplot_noise.png...")

fig, ax = plt.subplots(figsize=(12, 5), facecolor=C_BG)
ax.set_facecolor(C_BG)

db_arrays = [nd["db"] for nd in night_data]
bp = ax.boxplot(db_arrays, patch_artist=True, widths=0.55, medianprops=dict(color='white', linewidth=2))

for i, (patch, nd) in enumerate(zip(bp['boxes'], night_data)):
    color = night_color(nd["type"])
    patch.set_facecolor(color)
    patch.set_alpha(0.75)
    patch.set_edgecolor('#333333')

for element in ['whiskers', 'caps', 'fliers']:
    for item in bp[element]:
        item.set_color('#555555')

ax.axhline(40, color='grey',  linestyle='--', linewidth=1.2, alpha=0.8, label='40 dB (WHO guideline)')
ax.axhline(50, color='red',   linestyle='--', linewidth=1.2, alpha=0.8, label='50 dB (peak threshold)')
ax.set_xticks(range(1, 9))
ax.set_xticklabels([f"N{i+1}" for i in range(8)])
ax.set_xlabel("Night", fontsize=11)
ax.set_ylabel("Noise Level (dB)", fontsize=11)
ax.set_title("Noise Level Distribution per Night", fontsize=12, fontweight='bold')
legend_handles = [
    mpatches.Patch(facecolor=C_BLUE,  edgecolor='#333', label='Normal Night'),
    mpatches.Patch(facecolor=C_AMBER, edgecolor='#333', label='Added Noise Night'),
    plt.Line2D([0], [0], color='grey', linestyle='--', label='40 dB WHO guideline'),
    plt.Line2D([0], [0], color='red',  linestyle='--', label='50 dB peak threshold'),
]
ax.legend(handles=legend_handles, fontsize=9)
ax.grid(axis='y', alpha=0.3)
fig.tight_layout()
fig_save(fig, "chart_boxplot_noise.png")


# (d) chart_scatter_correlations.png 
print("Saving chart_scatter_correlations.png...")

noise_means = np.array([nd["stats"]["noise_mean"]  for nd in night_data])
hr_means    = np.array([nd["stats"]["hr_mean"]     for nd in night_data])
rmssds      = np.array([nd["stats"]["rmssd"]       for nd in night_data])
ntypes      = [nd["type"] for nd in night_data]

def scatter_regress(ax, x, y, ntypes_list, ylabel, title):
    for i, (xi, yi, nt) in enumerate(zip(x, y, ntypes_list)):
        c  = C_BLUE  if nt == "Normal" else C_AMBER
        mk = 'o'     if nt == "Normal" else '^'
        ax.scatter(xi, yi, color=c, marker=mk, s=80, zorder=3)
        label_str = f"N{i+1}"
        ax.annotate(label_str, (xi, yi), textcoords="offset points",
                    xytext=(6, 4), fontsize=8, color='#333333')
    m, b = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, m * xs + b, color='#555555', linestyle='--', linewidth=1.2, alpha=0.8)
    r_val, p_val = pearsonr(x, y)
    p_str = f"p={p_val:.3f}" if p_val >= 0.001 else "p<0.001"
    ax.text(0.05, 0.92, f"r={r_val:+.3f}, {p_str}",
            transform=ax.transAxes, fontsize=9, color='#222222',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.set_xlabel("Noise Mean (dB)", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_facecolor(C_BG)

fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor=C_BG)
scatter_regress(axes[0], noise_means, hr_means, ntypes, "HR Mean (BPM)", "Noise Mean vs HR Mean")
scatter_regress(axes[1], noise_means, rmssds,   ntypes, "RMSSD (delta BPM)", "Noise Mean vs RMSSD")

legend_handles = [
    mpatches.Patch(facecolor=C_BLUE,  edgecolor='#333', label='Normal'),
    mpatches.Patch(facecolor=C_AMBER, edgecolor='#333', label='Added Noise'),
]
fig.legend(handles=legend_handles, loc='lower center', ncol=2, fontsize=9,
           bbox_to_anchor=(0.5, -0.04))
fig.suptitle("Night-Level Correlations", fontsize=12, fontweight='bold')
fig.tight_layout(rect=[0, 0.04, 1, 1])
fig_save(fig, "chart_scatter_correlations.png")


# (e) chart_xcorr_curves.png 
print("Saving chart_xcorr_curves.png...")

fig, ax = plt.subplots(figsize=(13, 5), facecolor=C_BG)
ax.set_facecolor(C_BG)

for i, nd in enumerate(night_data):
    ax.plot(lags_ref, nd["xcorr_rs"], color='grey', alpha=0.35, linewidth=0.8)

ax.plot(lags_ref, avg_normal, color=C_BLUE,  linewidth=2,   label='Normal nights avg',     alpha=0.85)
ax.plot(lags_ref, avg_noise,  color=C_AMBER, linewidth=2,   label='Noise nights avg',      alpha=0.85)
ax.plot(lags_ref, grand_mean, color='black', linewidth=2.5, label='Grand mean',            alpha=1.0)

pk_idx = np.argmax(grand_mean)
pk_lag = lags_ref[pk_idx]
pk_r   = grand_mean[pk_idx]
ax.scatter([pk_lag], [pk_r], color='black', s=60, zorder=5)
ax.annotate(f"peak: lag={pk_lag:+d}s\nr={pk_r:+.4f}",
            (pk_lag, pk_r), textcoords="offset points",
            xytext=(10, -20), fontsize=8,
            arrowprops=dict(arrowstyle='->', color='#333333', lw=0.8))

ax.axvline(0, color='red',  linestyle='--', linewidth=1, alpha=0.7)
ax.axhline(0, color='grey', linestyle=':',  linewidth=1, alpha=0.7)
ax.set_xlabel("Lag (s)", fontsize=11)
ax.set_ylabel("Pearson r (noise[t] vs HR[t+lag])", fontsize=11)
ax.set_title("Lagged Cross-Correlation: Noise vs Heart Rate", fontsize=12, fontweight='bold')
ax.legend(fontsize=9)
ax.grid(alpha=0.25)
fig.tight_layout()
fig_save(fig, "chart_xcorr_curves.png")


# (f) chart_peak_aligned.png 
print("Saving chart_peak_aligned.png...")

t_axis = np.arange(-WINDOW_PRE, WINDOW_POST)

def weighted_avg_windows(windows_list):
    """Return weighted average across a list of (n_events, wlen) windows by event count."""
    if not windows_list:
        return None
    arr = np.array(windows_list)
    return arr.mean(axis=0)

windows_normal = []
windows_noise  = []
for i, nd in enumerate(night_data):
    if i in NORMAL_IDX:
        windows_normal.extend(nd["peak_windows"])
    else:
        windows_noise.extend(nd["peak_windows"])

fig, ax = plt.subplots(figsize=(13, 5), facecolor=C_BG)
ax.set_facecolor(C_BG)

for w in all_event_windows:
    ax.plot(t_axis, w, color='grey', alpha=0.25, linewidth=0.6)

if windows_normal:
    avg_n = weighted_avg_windows(windows_normal)
    ax.plot(t_axis, avg_n, color=C_BLUE,  linewidth=2, label=f'Normal avg (n={len(windows_normal)})')
if windows_noise:
    avg_ns = weighted_avg_windows(windows_noise)
    ax.plot(t_axis, avg_ns, color=C_AMBER, linewidth=2, label=f'Noise avg  (n={len(windows_noise)})')
if all_event_windows:
    grand_avg = weighted_avg_windows(all_event_windows)
    ax.plot(t_axis, grand_avg, color='black', linewidth=3, label=f'Grand mean (n={len(all_event_windows)})')

ax.axvline(0, color='red',  linestyle='--', linewidth=1.2, alpha=0.8)
ax.axhline(0, color='grey', linestyle=':',  linewidth=1.0, alpha=0.7)
ax.text(1, ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1] != 0 else 2,
        'noise peak (t=0)', color='red', fontsize=8, ha='left', va='top',
        transform=ax.get_xaxis_transform())

ax.set_ylim(-20, 20)
ax.set_xlabel("Time relative to noise peak (s)", fontsize=11)
ax.set_ylabel("Delta HR relative to pre-peak baseline (BPM)", fontsize=11)
ax.set_title("Peak-Aligned HR Response to Noise Events", fontsize=12, fontweight='bold')
ax.legend(fontsize=9)
ax.grid(alpha=0.25)
fig.tight_layout()
fig_save(fig, "chart_peak_aligned.png")


# (g) table_xcorr_summary.png 
print("Saving table_xcorr_summary.png...")

xcorr_col_headers = ["Night", "Type", "Peak Lag (s)", "Peak r",
                     "r at +5s", "r at +10s", "r at +15s", "r at +30s"]

def xcorr_row(label, ntype, rs):
    pk_idx = np.argmax(np.abs(rs))
    return [
        label,
        ntype,
        f"{lags_ref[pk_idx]:+d}",
        f"{rs[pk_idx]:+.4f}",
        f"{rs[lag_idx(5)]:+.4f}",
        f"{rs[lag_idx(10)]:+.4f}",
        f"{rs[lag_idx(15)]:+.4f}",
        f"{rs[lag_idx(30)]:+.4f}",
    ]

xcorr_rows = []
for nd in night_data:
    xcorr_rows.append(xcorr_row(nd["label"], nd["type"], nd["xcorr_rs"]))
pk_idx_gm = np.argmax(np.abs(grand_mean))
xcorr_rows.append([
    "All Nights", "---",
    f"{lags_ref[pk_idx_gm]:+d}",
    f"{grand_mean[pk_idx_gm]:+.4f}",
    f"{grand_mean[lag_idx(5)]:+.4f}",
    f"{grand_mean[lag_idx(10)]:+.4f}",
    f"{grand_mean[lag_idx(15)]:+.4f}",
    f"{grand_mean[lag_idx(30)]:+.4f}",
])

col_w_xcorr = [0.12, 0.13, 0.13, 0.12, 0.12, 0.12, 0.12, 0.12]
fig = make_table_fig(xcorr_col_headers, xcorr_rows, col_widths=col_w_xcorr,
                     title="Cross-Correlation Summary",
                     figsize=(14, 5))
fig_save(fig, "table_xcorr_summary.png")


# (h) table_peak_response.png 
print("Saving table_peak_response.png...")

peak_col_headers = ["Night", "Type", "N Peaks",
                    "Mean dHR (BPM)", "Median dHR (BPM)", "HR Increase Rate (%)"]

peak_rows = []
for nd in night_data:
    np_, mean_d, med_d, pct_d = peak_stats(nd["peak_deltas"])
    peak_rows.append([
        nd["label"], nd["type"],
        str(np_),
        f"{mean_d:.3f}",
        f"{med_d:.3f}",
        f"{pct_d:.1f}",
    ])
np_, mean_d, med_d, pct_d = peak_stats(all_delta_hrs)
peak_rows.append([
    "All Nights", "---",
    str(np_),
    f"{mean_d:.3f}",
    f"{med_d:.3f}",
    f"{pct_d:.1f}",
])

col_w_peak = [0.14, 0.15, 0.12, 0.19, 0.21, 0.19]
fig = make_table_fig(peak_col_headers, peak_rows, col_widths=col_w_peak,
                     title="Peak-Aligned HR Response Summary",
                     figsize=(12, 5))
fig_save(fig, "table_peak_response.png")


# SECTION 6: SUMMARY
print()
print("=" * 60)
print("  ALL FILES SAVED:")
print("=" * 60)
saved_files = [
    "table_night_stats.png",
    "chart_boxplot_hr.png",
    "chart_boxplot_noise.png",
    "chart_scatter_correlations.png",
    "chart_xcorr_curves.png",
    "chart_peak_aligned.png",
    "table_xcorr_summary.png",
    "table_peak_response.png",
]
for fname in saved_files:
    full = OUT_DIR / fname
    exists = "OK" if full.exists() else "MISSING"
    print(f"  [{exists}] {full}")
print("=" * 60)
print()
print("Done.")
