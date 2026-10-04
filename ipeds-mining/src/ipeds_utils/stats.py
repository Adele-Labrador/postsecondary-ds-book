"""Small statistical helpers shared by the analysis notebooks.

Only methods that appear in more than one notebook, or whose correctness is easy to
get subtly wrong, live here. Each is covered by a test that checks it against a known
answer rather than against itself.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

MAD_TO_SD = 1.4826  # makes the MAD a consistent estimator of sigma under normality


def robust_z(values, *, min_mad: float = 0.0) -> pd.Series:
    """Median/MAD standardisation, resistant to the heavy tails typical of IPEDS.

    A single research university can move a mean-and-SD z-score for every other
    institution in its peer group; it cannot move a median. Returns NaN throughout if
    the MAD is at or below ``min_mad``, rather than dividing by zero.
    """
    x = pd.to_numeric(pd.Series(values), errors="coerce")
    median = x.median()
    mad = MAD_TO_SD * (x - median).abs().median()
    if not np.isfinite(mad) or mad <= min_mad:
        return pd.Series(np.nan, index=x.index)
    return (x - median) / mad


def cliffs_delta(x, y) -> float:
    """Cliff's delta: P(X > Y) - P(X < Y). A rank effect size in [-1, 1].

    Computed from the Mann-Whitney U statistic rather than the O(n*m) pairwise
    comparison, so it scales to full IPEDS sectors.
    """
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    y = np.asarray(pd.Series(y).dropna(), dtype=float)
    if len(x) == 0 or len(y) == 0:
        return float("nan")
    u = stats.mannwhitneyu(x, y, alternative="two-sided").statistic
    return float(2 * u / (len(x) * len(y)) - 1)


def bootstrap_ci(statistic, *samples, n_boot: int = 2000, level: float = 0.95, seed: int = 0):
    """Percentile bootstrap interval for ``statistic(*samples)``.

    Each sample is resampled independently, which is correct for comparing separate
    groups of institutions and wrong for paired or panel data.
    """
    rng = np.random.default_rng(seed)
    arrays = [np.asarray(pd.Series(s).dropna(), dtype=float) for s in samples]
    draws = np.empty(n_boot)
    for b in range(n_boot):
        draws[b] = statistic(*[a[rng.integers(0, len(a), len(a))] for a in arrays])
    alpha = (1 - level) / 2
    return float(np.quantile(draws, alpha)), float(np.quantile(draws, 1 - alpha))


def fit_beta_binomial(successes, trials) -> tuple[float, float]:
    """Maximum-likelihood Beta(a, b) prior for rates observed as successes out of trials.

    This is the empirical-Bayes step: the prior is estimated from the population of
    institutions itself. Optimisation runs on log(a), log(b) so both stay positive,
    starting from method-of-moments values.
    """
    k = np.asarray(successes, dtype=float)
    n = np.asarray(trials, dtype=float)
    keep = np.isfinite(k) & np.isfinite(n) & (n > 0) & (k >= 0) & (k <= n)
    k, n = k[keep].astype(int), n[keep].astype(int)
    if len(k) < 3:
        raise ValueError("need at least three institutions with a positive cohort")

    p = k / n
    mean, var = p.mean(), p.var()
    common = mean * (1 - mean) / var - 1 if var > 0 else 10.0
    start = np.log([max(mean * common, 0.5), max((1 - mean) * common, 0.5)])

    def nll(theta):
        a, b = np.exp(theta)
        return -stats.betabinom.logpmf(k, n, a, b).sum()

    result = optimize.minimize(
        nll, start, method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-6, "maxiter": 4000}
    )
    if not result.success:
        raise RuntimeError(f"beta-binomial fit did not converge: {result.message}")
    a, b = np.exp(result.x)
    return float(a), float(b)


def shrink(successes, trials, a: float, b: float, *, level: float = 0.9) -> pd.DataFrame:
    """Posterior mean and equal-tailed interval under a Beta(a, b) prior.

    The posterior for each institution is Beta(a + k, b + n - k). ``weight`` is the
    share of the posterior mean contributed by the institution's own data,
    n / (n + a + b): near 1 for large cohorts, near 0 for tiny ones.
    """
    k = pd.to_numeric(pd.Series(successes), errors="coerce")
    n = pd.to_numeric(pd.Series(trials), errors="coerce")
    post_a, post_b = a + k, b + (n - k)
    tail = (1 - level) / 2
    return pd.DataFrame(
        {
            "raw_rate": (k / n).where(n > 0),
            "post_mean": post_a / (post_a + post_b),
            "post_lo": stats.beta.ppf(tail, post_a, post_b),
            "post_hi": stats.beta.ppf(1 - tail, post_a, post_b),
            "weight": n / (n + a + b),
        },
        index=k.index,
    )


def within_transform(frame: pd.DataFrame, entity: str, cols: list[str]) -> pd.DataFrame:
    """Subtract entity means: the fixed-effects (within) transformation.

    Regressing within-transformed outcomes on within-transformed regressors gives the
    fixed-effects estimator without building one dummy column per institution, which
    for roughly 5,000 IPEDS institutions is a very large dense matrix. Standard errors
    from the transformed regression need clustering by entity.
    """
    out = frame.copy()
    means = frame.groupby(entity)[cols].transform("mean")
    out[cols] = frame[cols] - means
    return out
