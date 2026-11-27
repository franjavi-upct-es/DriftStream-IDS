<!-- data/README.md -->

# Data

Raw data is **never** committed or redistributed. This folder holds only this
file and `CHECKSUMS.raw` (added after the first verified download, ROADMAP T2.1
/ T2.3). Everything else is regenerated with `make data`.

| Path                        | Written by                                  | Committed?                          |
| --------------------------- | ------------------------------------------- | ----------------------------------- |
| `raw/cicids2017_corrected/` | `driftstream data download --dataset cic`   | No                                  |
| `raw/kyoto2006/`            | `driftstream data download --dataset kyoto` | No                                  |
| `interim/`                  | ETL (temporary; safe to delete)             | No                                  |
| `processed/<dataset>/`      | ETL + validate                              | No (small JSON side files optional) |

## Datasets

| Dataset                   | Provider                                                                              | Cite                                         | Data card                              |
| ------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------- | -------------------------------------- |
| CIC-IDS2017 **corrected** | DistriNet / KU Leuven re-generation                                                   | Sharafaldin et al. 2018; Engelen et al. 2021 | `docs/data_cards/cicids2017.md` (T2.1) |
| Kyoto 2006+               | Kyoto University honeypot data, Kaggle mirror `harshwardhanbhangale/kyoto-2006` (v1)  | Song et al. 2011                             | `docs/data_cards/kyoto2006.md` (T2.3)  |

### Kyoto 2006+ archive (checked 2026-11-27)

The provider's server (`www.takakura.com`) refused connections on ports 80 and
443 on 2026-11-27, so the data comes from the Kaggle mirror
[`harshwardhanbhangale/kyoto-2006`](https://www.kaggle.com/datasets/harshwardhanbhangale/kyoto-2006)
(CC BY 4.0), pinned to **version 1**. It is one `archive.zip` of ≈ 14.5 GB
(109 GB unpacked) with the daily files
`<YYYY>/Kyoto2016/<YYYY>/<MM>/<YYYYMMDD>.txt`; no Kaggle account is needed. The
files have the documented `new_data201704` format (24 tab-separated columns,
sanitised IPv6 addresses, `HH:mm:ss` start times), checked on 2006-11-01.

| Year      | Day files | Unpacked size | In the MVP window?  |
| --------- | --------- | ------------- | ------------------- |
| 2006      | 61        | 0.7 GB        | No                  |
| 2007      | 357       | 4.6 GB        | **Yes**             |
| 2008      | 347       | 7.4 GB        | **Yes**             |
| 2009      | 354       | 14.7 GB       | **Yes**             |
| 2010      | —         | absent        | No                  |
| 2011–2015 | 1,793     | 82.0 GB       | No (stretch option) |

`driftstream data download --dataset kyoto` downloads the archive once (the
transfer resumes after an interruption) into
`raw/kyoto2006/_zips/kyoto-2006-kaggle-v1.zip`, records its SHA-256, and
extracts only the day files of the configured window (1,058 files, 26.7 GB for
2007–2009) under `raw/kyoto2006/`, keeping the archive's paths. Files already
extracted are not rewritten, so changing the window never downloads again. The
38 days of 2007–2009 without a file are listed in `etl_report.json`
(`missing_days`).

**Never use the original, uncorrected CIC-IDS2017 CSVs** (ADR-004). The Kyoto
detector-output columns and IP addresses are removed in ETL (ADR-005).
