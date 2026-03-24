DAY_NUMBER = 9

from fitparse import FitFile
from pathlib import Path

BASE     = Path(__file__).parent
RAW_DIR  = BASE / "11_heart_rate_data" / "01_temp_raw_heart_rate"
OUT_PATH = BASE / "11_heart_rate_data" / f"day{DAY_NUMBER}.csv"

fit_files = list(RAW_DIR.glob("*.fit"))
if not fit_files:
    raise FileNotFoundError(f"No .fit file found in {RAW_DIR}")
FIT_PATH = fit_files[0]

print(f"Reading: {FIT_PATH}")
fit = FitFile(str(FIT_PATH))

rows = []
t0   = None

for msg in fit.get_messages("record"):
    fields = {f.name: f.value for f in msg if f.value is not None}
    if "heart_rate" not in fields or "timestamp" not in fields:
        continue
    ts = fields["timestamp"]
    if t0 is None:
        t0 = ts
    elapsed = round((ts - t0).total_seconds(), 1)
    hr      = int(fields["heart_rate"])
    rows.append((elapsed, hr))

if not rows:
    raise RuntimeError("No heart rate records found in the .fit file.")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("elapsed_seconds,heart_rate\n")
    for elapsed, hr in rows:
        f.write(f"{elapsed:.1f},{hr}\n")

print(f"Extracted {len(rows)} records")
print(f"Duration:  {rows[-1][0]:.1f} s  ({rows[-1][0]/3600:.2f} h)")
print(f"HR range:  {min(r[1] for r in rows)} - {max(r[1] for r in rows)} BPM")
print(f"Saved to:  {OUT_PATH}")
