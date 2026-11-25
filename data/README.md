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
| Kyoto 2006+               | Kyoto University honeypot data, `https://www.takakura.com/Kyoto_data/new_data201704/` | Song et al. 2011                             | `docs/data_cards/kyoto2006.md` (T2.3)  |

### Kyoto 2006+ archive (checked 2026-11-25)

The provider publishes yearly archives (`<YYYY>/<YYYY>.zip`) and monthly
archives (`<YYYY>/<YYYYMM>.zip`) from 2006-11 to 2015-12. Some months are
annotated with days that are missing; the data card lists them.

| Year                | Zipped size        | In the MVP window?  |
| ------------------- | ------------------ | ------------------- |
| 2006 (Nov–Dec only) | 90 MB              | No                  |
| 2007                | 633 MB             | **Yes**             |
| 2008                | 1,070 MB           | **Yes**             |
| 2009                | 2,155 MB           | **Yes**             |
| 2010–2015           | ≈ 15.7 GB in total | No (stretch option) |

The MVP downloads the 36 **monthly** archives of 2007–2009 (≈ 3.9 GB zipped), so
a failed transfer only repeats one month. Raw files are unzipped into
`raw/kyoto2006/YYYY/MM/`.

**Never use the original, uncorrected CIC-IDS2017 CSVs** (ADR-004). The Kyoto
detector-output columns and IP addresses are removed in ETL (ADR-005).
