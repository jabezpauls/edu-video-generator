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


def test_group_lines_breaks_at_sentence_ends(sub):
    words = [{"word": w, "start": i, "end": i + 0.5}
             for i, w in enumerate("One two three. Four five".split())]
    assert [ln["text"] for ln in sub.group_lines(words)] == ["One two three.", "Four five"]


def test_main_uses_grid_clock(sub, tmp_path, monkeypatch):
    import json
    words = [{"i": 0, "word": "Hello", "start": 2.0, "end": 2.4},
             {"i": 1, "word": "world.", "start": 2.5, "end": 3.0}]
    (tmp_path / "storyboard.json").write_text(json.dumps({"scenes": [{"id": "01"}]}))
    (tmp_path / "grid.json").write_text(json.dumps({"scenes": [{"id": "01", "words": words}]}))
    monkeypatch.setattr("sys.argv", ["align_subtitles.py", str(tmp_path)])
    assert sub.main() == 0
    srt = (tmp_path / "output" / "subtitles.srt").read_text()
    assert "00:00:02,000 --> 00:00:03,000" in srt and "Hello world." in srt


def test_tall_style_is_phone_sized_and_clear_of_the_platform_zones(sub, tmp_path):
    out = tmp_path / "t.ass"
    words = [{"word": f"w{i}", "start": i, "end": i + 0.5} for i in range(9)]
    sub.write_ass(out, sub.group_lines(words, sub.STYLES["tall"]["words"]), "tall")
    text = out.read_text()
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    style = [ln for ln in text.splitlines() if ln.startswith("Style:")][0].split(",")
    size, ml, mr, mv = int(style[2]), int(style[-4]), int(style[-3]), int(style[-2])
    assert size >= 60
    assert mr >= 0.12 * 1080 and mv >= 0.20 * 1920, "right UI strip and bottom 20 % stay clear"
    assert text.count("Dialogue:") == 3   # 4 words per line
