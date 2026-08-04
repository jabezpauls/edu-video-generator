import importlib.util
import json
import math
import sys

import pytest

from conftest import REPO, SKILL

REF = json.loads((REPO / "tests" / "fixtures" / "spring_reference.json").read_text())


@pytest.fixture(scope="module")
def springs():
    path = SKILL / "templates" / "manim" / "springs.py"
    spec = importlib.util.spec_from_file_location("springs", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["springs"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", list(REF["presets"]))
def test_step_matches_reference(springs, name):
    r = REF["presets"][name]
    assert springs.PRESETS[name] == {"response": r["response"], "damping": r["damping"]}
    for tau, expected in zip(REF["taus"], r["step"]):
        assert springs.step(tau, name) == pytest.approx(expected, abs=1e-9), (name, tau)


@pytest.mark.parametrize("name", list(REF["presets"]))
def test_settle_matches_reference(springs, name):
    assert springs.settle(name, REF["eps"]) == pytest.approx(REF["presets"][name]["settle"], abs=1e-9)


@pytest.mark.parametrize("name", list(REF["presets"]))
def test_rate_function_is_the_normalised_reference_curve(springs, name):
    r = REF["presets"][name]
    rate = springs.spring(name)
    d = r["settle"]
    end = springs.step(d, name)
    for alpha in (0.05, 0.2, 0.37, 0.5, 0.81, 0.99):
        assert rate(alpha) == pytest.approx(springs.step(alpha * d, name) / end, abs=1e-12)


@pytest.mark.parametrize("name", list(REF["presets"]))
def test_rate_function_endpoints_are_exact(springs, name):
    rate = springs.spring(name)
    assert rate(0) == 0
    assert rate(-0.5) == 0
    assert rate(1) == 1.0
    assert rate(1.5) == 1.0


def test_overshoot_character(springs):
    def peak(name):
        rate = springs.spring(name)
        return max(rate(i / 2000) for i in range(2001))

    assert peak("heavy") <= 1 + 1e-9
    assert peak("snappy") - 1 < 0.02
    assert peak("playful") - 1 > 0.1


def test_custom_params_and_errors(springs):
    p = {"response": 0.3, "damping": 1.4}  # overdamped branch
    assert springs.step(5, p) == pytest.approx(1.0, abs=1e-6)
    assert math.isfinite(springs.settle(p))
    with pytest.raises(ValueError):
        springs.spring("bouncy")


def test_spring_at(springs):
    assert springs.spring_at(0.5, 1.0, 10, 20) == 10
    assert springs.spring_at(10, 0, 10, 20, "heavy") == pytest.approx(20, abs=1e-6)
