"""The side-aware latent calibrator (config/improvements.yaml) and its locked default."""
import numpy as np
import pandas as pd
import pytest

from models.dist_models import LatentCalibrator


def _games(n=6000, seed=0):
    """Right-skewed totals: 7% of games get +24 points (overtime); mu is the mean residual."""
    rng = np.random.default_rng(seed)
    mu = rng.normal(0.8, 2.0, n)
    ot = rng.random(n) < 0.07
    outcome_minus_line = mu - 0.07 * 24 + rng.normal(0, 16, n) + 24 * ot
    line = np.full(n, 140.5)
    return pd.DataFrame({"date": pd.Timestamp("2020-01-01") + pd.to_timedelta(np.arange(n) // 20, "D"),
                         "line": line, "outcome": np.round(line + outcome_minus_line), "mu": mu, "sd": 17.0})


def test_base_calibrator_is_unchanged_and_ignores_side():
    h = _games()
    c = LatentCalibrator().fit(h)
    assert c.terms == "base" and len(c.beta) == 5
    s = np.array([0.1, -0.2])
    assert np.allclose(c.prob(s, 0.0 * s), c.prob(s, 0.0 * s, side=np.array([1, -1])))


def test_side_term_learns_that_skewed_totals_favour_the_under():
    h = _games()
    c = LatentCalibrator("side").fit(h)
    assert len(c.beta) == 6 and c.beta[5] < 0                      # Over (+1) wins less than Under (-1)
    p_over = c.prob(np.array([0.0]), np.array([0.0]), side=1)
    p_under = c.prob(np.array([0.0]), np.array([0.0]), side=-1)
    assert p_under[0] > p_over[0]


def test_side_calibrators_need_the_side_and_unknown_terms_fail():
    c = LatentCalibrator("side_buffer").fit(_games(2000))
    assert len(c.beta) == 8
    with pytest.raises(ValueError):
        c.prob(np.array([0.0]), np.array([0.0]))
    with pytest.raises(ValueError):
        LatentCalibrator("whatever")


def test_pickled_calibrators_without_terms_default_to_base():
    c = LatentCalibrator().fit(_games(1000))
    del c.terms                                                     # as unpickled from an older cache
    assert c.terms == "base" and np.isfinite(c.prob(np.array([0.2]), np.array([0.0]))).all()
