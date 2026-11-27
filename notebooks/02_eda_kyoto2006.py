# notebooks/02_eda_kyoto2006.py
# %% [markdown]
# # 02 — EDA: Kyoto 2006+ (new_data201704, 2007-2009 sample)
# **Purpose:** describe the long-horizon stream (ROADMAP T2.7): daily
# arrival rate, monthly attack share (prior drift), known vs. unknown
# attacks over time, and monthly feature shift (virtual drift).
#
# **Inputs:** `data/processed/kyoto2006/` (or `$DRIFTSTREAM_KYOTO_DIR`).
#
# **Outputs:** `results/figures/eda/kyoto_*.png` (exploratory).

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
DATA = Path(os.environ.get("DRIFTSTREAM_KYOTO_DIR", "data/processed/kyoto2006"))
OUT = Path(os.environ.get("DRIFTSTREAM_EDA_OUT", "results/figures/eda"))
OUT.mkdir(parents=True, exist_ok=True)

df = load_frame(DATA)
profile = load_profile(DATA, "default")
report = json.loads((DATA / "etl_report.json").read_text())
print(
    f"{len(df):,} sessions (sampling fraction "
    f"{report['sampling_fraction']:.4f}), {len(report['missing_days'])} "
    f"missing days, timestamps assumed in {report['source_tz']}"
)

# %% [markdown]
# ## Daily rate and monthly attack share
# Kyoto's attack share varies over months: prior drift, part of why its
# onsets are unknown and E2 relies on regret.

# %%
rate = eda.arrival_rate(df, bin_seconds=86_400)
share = eda.attack_share(df, bin_seconds=30 * 86_400)
fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
ax[0].plot(rate.index, rate.to_numpy(), lw=0.8)
ax[0].set_ylabel("sessions / s (sample)")
ax[1].step(share.index, share.to_numpy(), where="post", color="tab:red")
ax[1].set_ylabel("attack share")
fig.suptitle("Kyoto 2006+: arrival rate and attack share")
fig.tight_layout()
fig.savefig(OUT / "kyoto_rate_share.png", dpi=150)

# %% [markdown]
# ## Known vs. unknown attacks per month

# %%
months = eda.period_keys(df, "month")
mix = df.groupby([months, df["family"]]).size().unstack(fill_value=0)
mix = mix.div(mix.sum(axis=1), axis=0)
ax = mix.plot.area(figsize=(9, 3.5), linewidth=0)
ax.set_ylabel("share of sessions")
ax.figure.tight_layout()
ax.figure.savefig(OUT / "kyoto_family_mix.png", dpi=150)
print(mix.round(3).to_string())

# %% [markdown]
# ## Monthly feature shift (KS statistic vs. the first month)

# %%
shift = eda.feature_shift(df, profile.numeric, period="month")
fig, ax = plt.subplots(figsize=(9, 4))
im = ax.imshow(shift.to_numpy().T, aspect="auto", cmap="viridis", vmin=0)
ax.set_xticks(range(len(shift)), shift.index, rotation=90)
ax.set_yticks(range(shift.shape[1]), shift.columns)
fig.colorbar(im, label="KS statistic vs. first month")
fig.tight_layout()
fig.savefig(OUT / "kyoto_feature_shift.png", dpi=150)
print(shift.max().sort_values(ascending=False).round(3).to_string())
