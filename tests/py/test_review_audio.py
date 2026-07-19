import pytest

from conftest import load_script
from synth import HAVE_FFMPEG, make_video

pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def review():
    return load_script("review")


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("a")
    speech = make_video(d / "speech.mp4", dur=6, tones=[(0, 2, 440, 0.3), (4.5, 6, 440, 0.3)])
    silent = make_video(d / "mute.mp4", dur=2)
    return str(speech), str(silent)


def test_dead_air_finds_the_gap(review, clips):
    runs = review.dead_air(clips[0])
    assert runs[0]["seconds"] == pytest.approx(2.5, abs=0.4)
    assert runs[0]["from_s"] == pytest.approx(2.0, abs=0.3)


def test_dead_air_on_all_silent_track_reaches_the_end(review, tmp_path):
    p = make_video(tmp_path / "quiet.mp4", dur=3, tones=[(0, 0, 440, 0)])
    runs = review.dead_air(str(p))
    assert runs and runs[0]["seconds"] >= 2.5


def test_loudness_reads_lufs_and_peak(review, clips):
    ld = review.loudness(clips[0])
    assert ld is not None
    assert -40 < ld["lufs"] < -5
    assert ld["true_peak_dbtp"] < 0


def test_loudness_none_without_audio(review, clips):
    assert review.loudness(clips[1]) is None


def test_safe_zone_metrics_find_content_in_the_zone(review, tmp_path):
    # 9:16 clip with a bar of "text" in the bottom 20 % from 1 s to 2 s
    p = tmp_path / "z.mp4"
    make_video(p, size="180x320", dur=3, fps=10,
               boxes=[dict(x=10, y=280, w=160, h=14, t0=1, t1=2)])
    a = review.analyze(str(p), zones=True)
    z = review.safe_zone_metrics(a["zone_ink"], a["fps"])
    assert z["bottom"]["seconds_with_content"] == pytest.approx(1.0, abs=0.3)
    assert z["top"]["seconds_with_content"] == 0
    assert z["bottom"]["longest_run_from_s"] == pytest.approx(1.0, abs=0.3)
