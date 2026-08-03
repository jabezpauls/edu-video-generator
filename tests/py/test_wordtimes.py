import pytest

from conftest import load_script


@pytest.fixture(scope="module")
def wt():
    return load_script("wordtimes")


def heard(*triples):
    return [{"word": w, "start": s, "end": e} for w, s, e in triples]


def test_norm_strips_punctuation_but_keeps_contractions(wt):
    assert wt.norm("Derivative,") == "derivative"
    assert wt.norm("Don’t") == "don't"
    assert wt.norm("well-known.") == "well-known"
    assert wt.norm("...") == ""


def test_tokenize_drops_bare_punctuation(wt):
    assert wt.tokenize("Rotate -- then, stop.") == ["Rotate", "then,", "stop."]


def test_ends_sentence(wt):
    assert wt.ends_sentence("stop.") and wt.ends_sentence('said?"') and wt.ends_sentence("so;")
    assert not wt.ends_sentence("then,") and not wt.ends_sentence("3.5")


def test_align_uses_heard_times_for_matching_words(wt):
    toks = wt.tokenize("Rotate the point")
    out = wt.align_to_text(toks, heard(("rotate", 1.0, 1.4), ("the", 1.4, 1.5), ("point", 1.5, 2.0)))
    assert [(w["word"], w["start"], w["end"]) for w in out] == [
        ("Rotate", 1.0, 1.4), ("the", 1.4, 1.5), ("point", 1.5, 2.0)]


def test_align_interpolates_words_the_recogniser_missed(wt):
    toks = wt.tokenize("e to the i pi")  # ASR heard "e" and "pi" only
    out = wt.align_to_text(toks, heard(("e", 0.0, 0.2), ("pi", 2.0, 2.4)))
    starts = [w["start"] for w in out]
    assert starts[0] == 0.0 and starts[-1] == 2.0
    assert starts == sorted(starts) and 0.2 <= starts[1] < starts[-1]
    assert len(out) == 5 and out[2]["word"] == "the"


def test_align_leading_and_trailing_gaps_stay_in_order(wt):
    out = wt.align_to_text(wt.tokenize("so rotate it now"),
                           heard(("rotate", 0.5, 0.9), ("it", 0.9, 1.0)))
    starts = [w["start"] for w in out]
    assert starts == sorted(starts)
    assert starts[0] >= 0 and out[-1]["start"] >= 1.0


def test_align_with_nothing_matching_uses_the_heard_span(wt):
    out = wt.align_to_text(wt.tokenize("alpha beta"), heard(("zzz", 3.0, 3.5), ("yyy", 3.5, 4.0)))
    assert out[0]["start"] == 3.0 and out[-1]["end"] <= 4.0


def test_align_without_heard_words_estimates(wt):
    out = wt.align_to_text(wt.tokenize("one two three"), [])
    assert len(out) == 3 and out[0]["start"] == 0 and out[2]["end"] > out[1]["end"]


def test_estimate_fills_the_given_duration(wt):
    out = wt.estimate_words(wt.tokenize("one two. three four"), 4.0)
    assert out[-1]["end"] <= 4.0 and out[-1]["end"] > 3.0
    assert wt.estimate_words([], 3.0) == []


def test_scene_words_prefers_provider_file(wt, tmp_path):
    import json
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "scene_01.words.json").write_text(
        json.dumps(heard(("hello", 0.1, 0.4), ("world", 0.5, 0.9))))
    words, source, dur = wt.scene_words(str(tmp_path), "01", "Hello world")
    assert source == "provider" and dur == 0.0
    assert [w["start"] for w in words] == [0.1, 0.5]


def test_scene_words_estimates_when_no_audio(wt, tmp_path):
    words, source, _ = wt.scene_words(str(tmp_path), "01", "Hello there world")
    assert source == "estimated" and len(words) == 3
