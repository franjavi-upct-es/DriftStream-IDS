# notebooks/01_eda_cicids2017.py
# %% [markdown]
# # 01 — EDA: CIC-IDS2017 (improved, CNS 2022 release)
# **Purpose:** describe the stream the simulator will replay (ROADMAP
# T2.7): arrival rate λ(t), attack share over time, family timeline and
# per-day feature shift. Findings go to `docs/lab_notebook.md`.
#
# **Inputs:** `data/processed/cicids2017/` (or `$DRIFTSTREAM_CIC_DIR`).
#
# **Outputs:** `results/figures/eda/cic_*.png` (exploratory; essay figures
# come from `analysis/figures.py`).

# %%
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from driftstream.analysis import eda
from driftstream.data.features import load_profile
from driftstream.data.loaders import load_frame

os.chdir("..")
DATA = Path(os.environ.get("DRIFTSTREAM_CIC_DIR", "data/processed/cicids2017"))
OUT = Path(os.environ.get("DRIFTSTREAM_EDA_OUT", "results/figures/eda"))
OUT.mkdir(parents=True, exist_ok=True)

df = load_frame(DATA)
profile = load_profile(DATA, "default")
print(f"{len(df):,} flows, attack share {df['y'].mean():.3f}")

# %% [markdown]
# ## Arrival rate and attack share (5-minute bins)
# λ(t) enters every prediction of `docs/theory.md`; the working-hours
# shape means λ must be taken locally around each onset.

# %%
rate = eda.arrival_rate(df, bin_seconds=300)
share = eda.attack_share(df, bin_seconds=300)
fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
ax[0].plot(rate.index, rate.to_numpy(), lw=0.8)
ax[0].set_ylabel("flows / s")
ax[1].plot(share.index, share.to_numpy(), lw=0.8, color="tab:red")
ax[1].set_ylabel("attack share")
fig.suptitle("CIC-IDS2017: arrival rate and attack share")
fig.tight_layout()
fig.savefig(OUT / "cic_rate_share.png", dpi=150)
print(rate.describe())

# %% [markdown]
# ## Family timeline and per-onset eligibility (OD-4)

# %%
timeline = eda.family_timeline(df)
onsets = json.loads((DATA / "drift_onsets.json").read_text())["families"]
timeline["eligible"] = [onsets[f]["eligible_per_onset"] for f in timeline.index]
timeline["in_warmup"] = [onsets[f]["in_warmup"] for f in timeline.index]
print(timeline.to_string())

fig, ax = plt.subplots(figsize=(9, 0.35 * len(timeline) + 1))
for i, (_, row) in enumerate(timeline.iterrows()):
    color = "tab:green" if row["eligible"] else "tab:gray"
    ax.plot([row["first"], row["last"]], [i, i], lw=4, color=color)
ax.set_yticks(range(len(timeline)), timeline.index)
ax.set_title("Attack families: green = eligible for per-onset analysis")
fig.tight_layout()
fig.savefig(OUT / "cic_family_timeline.png", dpi=150)

# %% [markdown]
# ## Per-day feature shift (KS statistic vs. Monday)

# %%
shift = eda.feature_shift(df, profile.numeric, period="day")
top = shift.max().sort_values(ascending=False).head(15).index
fig, ax = plt.subplots(figsize=(9, 4))
im = ax.imshow(shift[top].to_numpy().T, aspect="auto", cmap="viridis", vmin=0)
ax.set_xticks(range(len(shift)), shift.index, rotation=30)
ax.set_yticks(range(len(top)), top)
fig.colorbar(im, label="KS statistic vs. first day")
fig.tight_layout()
fig.savefig(OUT / "cic_feature_shift.png", dpi=150)
print(shift[top].round(3).to_string())
