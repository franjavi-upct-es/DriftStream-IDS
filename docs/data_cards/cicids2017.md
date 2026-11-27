<!-- docs/data_cards/cicids2017.md -->
# Data card — CIC-IDS2017 (improved, CNS 2022 release)

| Field | Value |
|---|---|
| Release used | `CICIDS2017_improved.zip` (≈ 328 MB), DistriNet/KU Leuven, uploaded 2023-04-27 |
| Source | `https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/` |
| Lineage | CIC-IDS2017 (Sharafaldin et al. 2018) → re-generated with a fixed CICFlowMeter and relabelled (Engelen et al. 2021, "WTMC 2021") → further corrected labelling logic and features (Liu et al., IEEE CNS 2022) |
| Cite | Sharafaldin et al. 2018; Engelen et al. 2021; Liu et al. 2022 |
| Licence / terms | Provider terms; data is **not** redistributed in this repository |
| Checked on | 2026-11-25 (source page and the authors' labelling code `GintsEngelen/CNS2022_Code`) |
| ETL | `src/driftstream/etl/cicids2017.py` (ROADMAP T2.2) |
| Status | Code ready and tested on a format-faithful fixture; **real download and ETL pending** (run on the project laptop) |

## Why this release (ADR-004)

The original CSVs have documented construction and labelling errors
(Engelen et al. 2021 report that more than 20 % of the traces had to be
reconstructed or relabelled). The WTMC 2021 page itself points to the
CNS 2022 release as the most recent version. The ETL also accepts the
WTMC 2021 files and the original spellings (`Bot`, `PortScan`,
`DoS SlowHttpTest`), but every experiment uses the CNS 2022 release.

## Raw format (verified)

- One CSV per weekday: `monday.csv` … `friday.csv` (the ETL searches the
  extracted archive recursively and requires exactly one file per day).
- First column `id`; identifiers `Flow ID`, `Src IP`, `Src Port`, `Dst IP`;
  `Dst Port`, `Protocol`; `Timestamp`; CICFlowMeter features (including the
  CNS 2022 additions: ICMP code/type, total TCP flow time, forward/backward
  RST counts); `Label`; `Attempted Category`.
- `Timestamp` is **UTC with microsecond precision** (the authors changed
  CICFlowMeter's output to UTC). The original release's AM/PM and timezone
  problems therefore do not apply, but the ETL still requires every row to
  fall on its file's UTC day (tolerance 0.1 %) and fails loudly otherwise.
- `Label` uses `"<attack> - Attempted"` for attack flows that carry no
  malicious payload; `Attempted Category` is −1 for every other flow. The
  dataset authors recommend relabelling Attempted flows as benign and never
  using them as a separate class.

## Labels per day (raw counts from the authors' labelling run)

Counts printed by the authors' notebook after labelling (before our
deduplication). Attempted rows are listed separately.

| Day (UTC) | Family | Flows | Attempted |
|---|---|---|---|
| Mon 2017-07-03 | BENIGN | 371,624 | — |
| Tue 2017-07-04 | BENIGN | 315,106 | — |
| | FTP-Patator | 3,972 | 12 |
| | SSH-Patator | 2,961 | 27 |
| Wed 2017-07-05 | BENIGN | 319,120 | — |
| | DoS Hulk | 158,468 | 581 |
| | DoS GoldenEye | 7,567 | 80 |
| | DoS Slowloris | 3,859 | 1,847 |
| | DoS Slowhttptest | 1,740 | 3,368 |
| | Heartbleed | 11 | 0 |
| Thu 2017-07-06 | BENIGN | 288,172 | — |
| | **Infiltration - Portscan** | **71,767** | — |
| | Web Attack - Brute Force | 73 | 1,292 |
| | Web Attack - XSS | 18 | 655 |
| | Web Attack - SQL Injection | 13 | 5 |
| | Infiltration | 36 | 45 |
| Fri 2017-07-07 | BENIGN | 288,544 | — |
| | Portscan | 159,066 | — |
| | DDoS | 95,144 | — |
| | Botnet | 736 | 4,067 |

Notes for the experiments:

- **`Infiltration - Portscan`** (the port scan run from the infiltrated
  host) is a large, separate family that the original release labelled
  benign. It is a real Thursday onset.
- Tuesday's FTP-/SSH-Patator are in the warm-up slice, so they are not
  onsets in the streaming phase.
- **Per-onset eligibility (OD-4, ≥ 1,000 flows):** on the full data, 7
  streaming-phase families qualify (DoS Hulk, DoS GoldenEye, DoS Slowloris,
  DoS Slowhttptest, Infiltration - Portscan, Portscan, DDoS). With the
  planned 25 % load-time subsample, DoS Slowloris (≈ 965) and DoS
  Slowhttptest (≈ 435) would fall below the threshold. See the
  pre-registration (OD-4).

## ETL choices

| Step | Choice | Where |
|---|---|---|
| Attempted rows | `attempted_policy = benign` (default); `attack` / `drop` for ablation A-ATT | `configs/dataset/cicids2017.yaml` |
| Identifiers | `id`, `Flow ID`, `Src IP`, `Src Port`, `Dst IP` and `Timestamp` dropped; `attempted_category` kept as metadata, never a feature | `etl/cicids2017.py` |
| Missing / infinite values | `Infinity` → NaN, then the median of the **warm-up slice** (Mon + Tue) | idem |
| Duplicates | Exact duplicates of features + label within the same second removed | idem |
| Order | Stable sort by `event_time`, dense `flow_id` | `etl/writer.py` |
| Layout | Parquet partitioned by UTC day, zstd | idem |
| Feature profiles | `default` = all numeric features; `strict` = minus `f_dst_port`, `f_protocol` | `data/features.py` |

## To fill after the first real run

| Item | Value |
|---|---|
| SHA-256 of `CICIDS2017_improved.zip` | in `data/CHECKSUMS.raw` |
| Rows read / written | `etl_report.json` |
| Duplicates removed, NaN imputed per feature | `etl_report.json` |
| Rows outside their UTC day | `etl_report.json` (expected 0) |
| Onsets and eligibility | `drift_onsets.json` |
| λ per hour, attack share per day | `stats.json`, notebook 01 |
