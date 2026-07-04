import pytest

from conftest import load_script


@pytest.fixture(scope="module")
def sub():
    return load_script("align_subtitles")


@pytest.mark.parametrize(
    "t, expected",
    [
        (0, "00:00:00,000"),
        (1.5, "00:00:01,500"),
        (4.35, "00:00:04,350"),  # float noise must not turn this into 349 ms
        (59.9996, "00:01:00,000"),  # rounds up across the minute boundary
        (3661.25, "01:01:01,250"),
        (-0.2, "00:00:00,000"),
    ],
)
def test_fmt_srt(sub, t, expected):
    assert sub.fmt_srt(t) == expected


@pytest.mark.parametrize(
    "t, expected",
    [(0, "0:00:00.00"), (1.5, "0:00:01.50"), (59.999, "0:01:00.00"), (3661.25, "1:01:01.25")],
)
def test_fmt_ass(sub, t, expected):
    assert sub.fmt_ass(t) == expected


def test_group_lines_splits_every_seven_words(sub):
    words = [{"word": f"w{i}", "start": i, "end": i + 0.5} for i in range(15)]
    lines = sub.group_lines(words)
    assert [len(ln["text"].split()) for ln in lines] == [7, 7, 1]
    assert lines[0]["start"] == 0 and lines[0]["end"] == 6.5
    assert lines[2]["text"] == "w14"


def test_group_lines_empty(sub):
    assert sub.group_lines([]) == []
