DAY_NUMBER = 9

from pathlib import Path

BASE    = Path(__file__).parent
RAW_DIR = BASE / "12_noise_level_data" / "01_temp_raw_noise"
OUT_PATH = BASE / "12_noise_level_data" / f"day{DAY_NUMBER}.csv"

csv_files = sorted(RAW_DIR.glob("*.csv"))
if not csv_files:
    raise FileNotFoundError(f"No .csv files found in {RAW_DIR}")

print(f"Found {len(csv_files)} file(s): {[f.name for f in csv_files]}")

db_values = []

for path in csv_files:
    rows = path.read_text(encoding="utf-8").strip().splitlines()
    for line in rows[1:]:           
        parts = line.split(";")
        if len(parts) < 2:
            continue
        db = float(parts[1])
        if float(parts[0]) == 0:    
            continue
        db_values.append(db)

if not db_values:
    raise RuntimeError("No valid noise records found.")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("seconds;db\n")
    for i, db in enumerate(db_values, start=0):
        f.write(f"{i};{db:.2f}\n")

print(f"Merged {len(db_values)} rows from {len(csv_files)} file(s)")
print(f"Duration:  {len(db_values)} s  ({len(db_values)/3600:.2f} h)")
print(f"dB range:  {min(db_values):.2f} - {max(db_values):.2f} dB")
print(f"Saved to:  {OUT_PATH}")
