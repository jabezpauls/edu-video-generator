import importlib.util
import sys

import pytest

from conftest import SKILL


def load(name="formats"):
    spec = importlib.util.spec_from_file_location(name, SKILL / "templates" / "manim" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def formats():
    return load()


def test_frame_units_keep_one_pixel_density(formats):
    for fid, (w, h) in formats.SIZES.items():
        f = formats.get(fid)
        assert min(f.frame_width, f.frame_height) == pytest.approx(8.0)
        assert f.frame_width / f.frame_height == pytest.approx(w / h)
        # same pixels per unit as 16x9 at 1080p: 135 px per unit
        assert w / f.frame_width == pytest.approx(135.0, rel=1e-3)


def test_orientation_and_pick(formats):
    assert [formats.get(i).orientation for i in ("16x9", "1x1", "4x5", "9x16")] == [
        "wide", "square", "tall", "tall"]
    assert formats.get("4x5").pick("w", "s", "t") == "s"      # 4x5 shares the square layout
    assert formats.get("9x16").pick("w", "s", "t") == "t"
    assert formats.get("1x1").pick("w") == "w"
    assert formats.get("9x16").pick("w", "s") == "s"


def test_pixels_by_quality_are_even_and_aspect_true(formats):
    assert formats.get("16x9").pixels("high") == (1920, 1080)
    assert formats.get("16x9").pixels("med") == (1280, 720)
    assert formats.get("9x16").pixels("high") == (1080, 1920)
    assert formats.get("9x16").pixels("low") == (480, 854)
    assert formats.get("4x5").pixels("med") == (720, 900)
    for fid in formats.SIZES:
        for q in ("low", "med", "high"):
            assert all(p % 2 == 0 for p in formats.get(fid).pixels(q))


def test_safe_area_9x16_and_overrides(formats):
    f = formats.get("9x16")
    left, right, top, bottom = f.safe_bounds()
    hh = f.frame_height / 2
    assert top == pytest.approx(hh - 0.14 * f.frame_height)
    assert bottom == pytest.approx(-hh + 0.20 * f.frame_height)
    assert right == pytest.approx(f.frame_width / 2 - 0.12 * f.frame_width)
    assert f.safe_width < f.frame_width and f.safe_height < f.frame_height

    g = formats.get("9x16", {"9x16": {"bottom": 0.3}, "all": {"left": 0.1}})
    assert g.safe == (0.14, 0.3, 0.1, 0.12)
    assert formats.get("16x9", {"9x16": {"bottom": 0.3}}).safe == (0.05, 0.05, 0.05, 0.05)


def test_unknown_format(formats):
    with pytest.raises(ValueError):
        formats.get("21x9")


def test_current_reads_env(monkeypatch, formats):
    monkeypatch.setenv("EDU_FORMAT", "4x5")
    assert formats.current().id == "4x5"
    monkeypatch.delenv("EDU_FORMAT")
    assert formats.current().id == "16x9"


needs_manim = pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="needs manim")


@needs_manim
def test_layout_helpers_stay_in_the_safe_area(formats):
    from manim import Rectangle, Text  # noqa: F401

    for fid in formats.SIZES:
        f = formats.get(fid)
        left, right, top, bottom = f.safe_bounds()
        big = Rectangle(width=30, height=30)
        formats.fit(big, f=f)
        formats.place(big, "center", f=f)
        assert big.width <= f.safe_width + 1e-6 and big.height <= f.safe_height + 1e-6
        a, b = Rectangle(width=5, height=2), Rectangle(width=5, height=2)
        g = formats.split(a, b, f=f)
        assert g.get_left()[0] >= left - 1e-6 and g.get_right()[0] <= right + 1e-6
        assert g.get_top()[1] <= top + 1e-6 and g.get_bottom()[1] >= bottom - 1e-6
        if f.is_wide:
            assert abs(a.get_center()[1] - b.get_center()[1]) < 1e-6   # side by side
        else:
            assert abs(a.get_center()[0] - b.get_center()[0]) < 1e-6   # stacked
        t = formats.place(Rectangle(width=3, height=1), "title", f=f)
        assert t.get_top()[1] == pytest.approx(top)
        c = formats.place(Rectangle(width=3, height=1), "caption", f=f)
        assert c.get_bottom()[1] == pytest.approx(bottom)


@needs_manim
def test_apply_sets_manim_frame(formats):
    from manim import config

    before = (config.frame_width, config.frame_height, config.pixel_width, config.pixel_height)
    try:
        formats.get("9x16").apply("med")
        assert config.frame_width == pytest.approx(8.0)
        assert config.frame_height == pytest.approx(8 * 1920 / 1080)
        assert (config.pixel_width, config.pixel_height) == (720, 1280)
    finally:
        config.frame_width, config.frame_height, config.pixel_width, config.pixel_height = before
