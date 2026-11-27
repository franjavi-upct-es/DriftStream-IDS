<!-- docs/data_cards/kyoto2006.md -->
# Data card — Kyoto 2006+ (new_data201704)

| Field | Value |
|---|---|
| Release used | new_data201704: sessions extracted with Bro 2.4, sanitised IP addresses, new IDS detection results |
| Source | `https://www.takakura.com/Kyoto_data/new_data201704/` (documentation: `BenchmarkData-Description-New.pdf`) |
| Coverage | 2006-11 → 2015-12, as yearly (`<YYYY>/<YYYY>.zip`) and monthly (`<YYYY>/<YYYYMM>.zip`) archives |
| MVP window | 2007-01 → 2009-12: 36 monthly archives, ≈ 3.9 GB zipped (2007: 633 MB, 2008: 1,070 MB, 2009: 2,155 MB) |
| Cite | Song et al. 2011 |
| Licence / terms | Provider terms; data is **not** redistributed in this repository |
| Checked on | 2026-11-25 |
| ETL | `src/driftstream/etl/spark_kyoto_etl.py` (ROADMAP T2.4, PySpark) |
| Status | Code ready and tested on a format-faithful fixture with a local Spark session; **real download and ETL pending** |

## Raw format (verified from the documentation)

24 columns, in this order (the documentation states the order is exactly
that of the data):

| # | Column | Use in the project |
|---|---|---|
| 1–13 | Duration, Service, Source bytes, Destination bytes, Count, Same srv rate, Serror rate, Srv serror rate, Dst host count, Dst host srv count, Dst host same src port rate, Dst host serror rate, Dst host srv serror rate | Features (`Service` categorical, the rest numeric) |
| 14 | Flag | Categorical feature |
| 15–17 | IDS detection, Malware detection, Ashula detection | **Removed: outputs of other detectors (label leakage, ADR-005)** |
| 18 | Label | `1` normal, `-1` known attack, `-2` unknown attack |
| 19–21 | Source IP Address, Source Port Number, Destination IP Address | **Removed: identifiers** |
| 22 | Destination Port Number | Numeric feature (removed by the `strict` profile) |
| 23 | Start Time | With the file date, gives `event_time` |
| 24 | Protocol | Categorical feature |

IP addresses are sanitised to IPv6 unique local addresses, and the mapping
is consistent **within one month only**. That is another reason never to
use them as features.

## Facts the documentation does not state: verify on the first month

| Item | Assumption in the ETL | How to verify (T2.3) |
|---|---|---|
| Delimiter | Tab | Open one `YYYYMMDD.txt`; 24 fields per line |
| File naming | `YYYYMMDD.txt` somewhere inside the monthly zip | `find data/raw/kyoto2006 -name '*.txt' \| head` |
| `Start Time` format | `HH:mm:ss`, optional fractional seconds | First lines of a day file |
| `Start Time` timezone | `Asia/Tokyo` (`source_tz`; the honeypots are in Japan) | Within one day file, `Start Time` should span 00:00–23:59 **local**: if it does, the file date and the time share one timezone. Then compare the hourly profile of sessions with the expected Japanese diurnal pattern (notebook 02) |

Rows with an unparsable time or a label outside {1, −1, −2} are dropped
and counted in `etl_report.json`.

## ETL choices

| Step | Choice |
|---|---|
| Engine | PySpark (local mode) for the scan; the sample is collected and written by the same writer as CIC-IDS2017 |
| Labels | `y = 0` for `1`; `y = 1` for `-1`/`-2`; `family` ∈ {BENIGN, KNOWN, UNKNOWN} |
| Sampling | Deterministic: `xxhash64(seed, file date, all raw fields)` → uniform; keep if below `target_sessions / valid rows` (default 1.5 M, `sample_seed = 0`) |
| Missing values | Numeric: warm-up median (first 30 days); categorical: `<missing>` |
| Time | `event_time` = file date + `Start Time` in `source_tz`, converted to UTC epoch seconds |
| Layout | Parquet partitioned by **UTC** month. A few early-morning JST sessions of the 1st of a month therefore land in the previous UTC month |
| Feature profiles | `default` = 13 numeric + `Service`, `Flag`, `Protocol`; `strict` = minus `f_destination_port_number` |

## To fill after the first real run

| Item | Value |
|---|---|
| SHA-256 of the 36 monthly archives | `data/CHECKSUMS.raw` |
| Unzipped size (first month, then total) | — |
| Days missing in the window | `etl_report.json` → `missing_days` |
| Rows read, invalid label/time, sampling fraction | `etl_report.json` |
| Attack share per month, KNOWN/UNKNOWN mix | `stats.json`, notebook 02 |
| `Start Time` timezone confirmed? | — |
