import os

import pytest
from PIL import Image

from conftest import load_script
from synth import HAVE_FFMPEG, make_video

pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def review():
    return load_script("review")


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    p = tmp_path_factory.mktemp("s") / "s.mp4"
    make_video(p, size="320x180", fps=10, dur=6,
               boxes=[dict(x=10, y=40, w=50, h=40, t0=1, dx=200, slide=0.5),
                      dict(x=10, y=110, w=50, h=40, t0=3, dx=200, slide=0.5)])
    return str(p)


def test_sampled_sheets_split_and_thin(review, clip, tmp_path):
    # 6 s at 2 fps = 12 frames; 4 per sheet -> 3 sheets
    paths, step = review.sampled_sheets(clip, str(tmp_path), "contact", 160, 90, 2, 4, 2, 8, 6.0)
    assert [os.path.basename(p) for p in paths] == ["contact.jpg", "contact_2.jpg", "contact_3.jpg"]
    assert step == 0.5
    # a long video is thinned so it never needs more than max_sheets
    paths, step = review.sampled_sheets(clip, str(tmp_path), "thin", 160, 90, 2, 2, 2, 2, 6.0)
    assert len(paths) <= 2 and step >= 1.5


def test_strips_centre_on_the_motion(review, clip, tmp_path):
    a = review.analyze(clip)
    paths, peaks = review.fast_action_strips(clip, str(tmp_path), a["energy"], a["fps"], a["duration"], 320, 180)
    assert len(paths) == 2 and all(os.path.getsize(p) > 0 for p in paths)
    assert any(abs(p - 1.0) < 1.2 for p in peaks[:2]) and any(abs(p - 3.0) < 1.2 for p in peaks[:2])


def test_shade_unsafe_tints_the_zones_only(review):
    im = Image.new("RGB", (100, 200), (0, 128, 0))
    out = review.shade_unsafe(im)
    assert out.getpixel((50, 100)) == (0, 128, 0)      # safe centre untouched
    assert out.getpixel((50, 5)) != (0, 128, 0)        # top zone
    assert out.getpixel((50, 195)) != (0, 128, 0)      # bottom zone
    assert out.getpixel((95, 100)) != (0, 128, 0)      # right zone
