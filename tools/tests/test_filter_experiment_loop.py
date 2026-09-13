import numpy as np
import pytest
from tools.filter_experiment_loop import bounded_gain, compose, rate_limit_gain, safety_project

def test_composition_equation():
    np.testing.assert_allclose(compose(np.array([0., 1.]), np.array([1., 3.]), .5), [.5, 2.])

def test_gain_is_bounded_and_rate_limited():
    assert bounded_gain('learned', model_gain=2., alpha=0., alpha_max=.6) == .6
    assert rate_limit_gain(.6, .1, .05, 1.) == pytest.approx(.15)

def test_nan_input_is_rejected():
    with pytest.raises(ValueError): compose(np.array([np.nan]), np.array([0.]), .1)

def test_step_is_limited():
    np.testing.assert_allclose(safety_project(np.array([1.]), np.array([0.]), .5, .02), [.02])
