# Sleep & Noise Dashboard — MSc IoT Project
CID: 06058811
---

## Opening the Dashboard
Download this folder and double-click **`dashboard.html`** to open it in your browser. No server, no installation required. The file is fully self-contained (all data, charts, and scripts are embedded). 

---

## Folder Structure

```
30_Dashboard/
│
├── dashboard.html              Self-contained interactive dashboard (open in browser)
├── result_analysis.py          Runs all statistical analyses, prints to terminal,
│                               saves charts and tables to 20_results/
├── extract_heart_rate.py       Converts a .fit file into a day<x>.csv HR file
├── merge_noise_data.py         Merges raw noise .csv files into a single day<x>.csv
├── imperial_logo.png           Logo embedded in the dashboard
├── wiring.txt                  ESP32 GPIO pin mapping for microphone and SD Card to MCU
│
├── 11_heart_rate_data/         Heart rate CSVs (one per night)
│   ├── day2.csv … day9.csv     columns: elapsed_seconds, heart_rate
│   └── 01_temp_raw_heart_rate/ Temporary folder used for extract_heart_rate.py
│
├── 12_noise_level_data/        Noise level CSVs (one per night)
│   ├── day2.csv … day9.csv     columns: seconds, db
│   └── 01_temp_raw_noise/      Temporary folder used for extract_noise_data.py
│
├── 20_results/                 Output folder for result_analysis.py
│   ├── table_night_stats.png   Summary statistics table across all 8 nights
│   ├── chart_boxplot_hr.png    HR distribution boxplots per night
│   ├── chart_boxplot_noise.png Noise distribution boxplots per night
│   ├── chart_scatter_correlations.png  Night-level Pearson correlations with regression
│   ├── chart_xcorr_curves.png  Lagged cross-correlation curves
│   ├── chart_peak_aligned.png  Peak-aligned HR response to noise events
│   ├── table_xcorr_summary.png Cross-correlation summary table
│   └── table_peak_response.png Peak response statistics table
│
└── 30_arduino_setup/           Arduino/ESP32 firmware
    ├── 01_main_data_collection/ Main sketch for recording noise to SD card
    ├── 11_microphone_calibration/  Calibration script for microphone INMP441
    └── 12_SD_card_initialisation/
```

## Dependencies

```
pip install pandas numpy scipy fitparse
```
All dashboard functionality runs in the browser with no additional installation.
