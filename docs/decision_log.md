<!-- docs/decision_log.md -->
# Decision log — DriftStream-IDS

Small decisions that do not deserve an ADR. One line each, newest first.
Significant decisions go to `docs/adr/`.

| Date | Area | Decision | Reason |
|---|---|---|---|
| 2026-11-25 | Plan | Deadline 2027-02-01; target submission 2027-01-29 with a 3-day buffer; baseline plan kept, compressed plan as fallback | Confirmed deadline (Q1) is only 3 days before the old baseline end |
| 2026-11-25 | Essay | PDF only, built with Pandoc + LaTeX engine + BibTeX (`refs.bib`), IEEE CSL by default; no DOCX template | Course format confirmed (Q2) |
| 2026-11-25 | Essay | The essay cites the public repository `https://github.com/franjavi-upct-es/DriftStream-IDS` | Allowed and preferred (Q3); repository must be public by M7 |
| 2026-11-25 | Data | Kyoto MVP window stays 2007–2009, downloaded as 36 monthly archives (≈ 3.9 GB zipped); 2010–2015 is a stretch option | Archive covers 2006-11 → 2015-12 (Q6); 2010 alone is 5.2 GB zipped |
| 2026-11-25 | Compute | Sweeps run with `hydra.launcher.n_jobs=16` on the 20-core laptop, leaving headroom for the OS and Docker; GPU not used | Hardware confirmed (Q5); River and HGB are CPU-only |
| 2026-11-25 | Config | Hydra experiment files start with `# @package _global_` and carry the path comment on line 2 | Hydra parses the package directive only as the first line of a file; `tests/unit/test_repo_conventions.py` accepts exactly this exception |
| 2026-11-25 | Config | Root defaults list ends with `experiment: null`, after `_self_` | `experiment=<name>` then selects a group, and the experiment file overrides root values such as `experiment` and `seed` |
| 2026-11-25 | Config | No project copy of `configs/hydra/launcher/joblib.yaml`; the plugin's own `joblib` config is used | A same-named YAML triggers Hydra's deprecated schema matching; tune with `hydra.launcher.n_jobs=<n>` |
| 2026-11-25 | Tooling | mypy `warn_unused_configs = false` until the third-party overrides are used | The overrides for River, scikit-learn, PySpark, etc. are pre-declared |
| 2026-11-25 | CLI | Planned commands exit with code 3 and name their ROADMAP task | A missing feature is never mistaken for a silent success |
| 2026-11-25 | Conventions | Every file starts with a comment holding its relative path; enforced by a unit test | Project rule; JSON and lock files are exempt (no comment syntax / generated) |
