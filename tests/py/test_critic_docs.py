import re

from conftest import SKILL

CRITERIA = ["Hook", "Correctness", "Clarity & cognitive load", "Readability at phone size",
            "Motion quality", "Narration sync", "Pacing", "Polish"]


def test_critique_prompt_lists_all_eight_criteria_and_the_log_format():
    text = (SKILL / "references" / "critique.md").read_text()
    for c in CRITERIA:
        assert f"| **{c}" in text, c
        assert f"| {c}" in text.split("## Output")[1], c
    assert "**Verdict:** SHIP | ANOTHER ROUND" in text


def test_review_log_template_matches_the_critique_rows():
    tpl = (SKILL / "templates" / "review_log.md").read_text()
    rows = re.findall(r"^\| ([^|]+?) \| *\| *\|$", tpl, re.M)
    assert [r.split(" (")[0] for r in rows] == CRITERIA


def test_review_script_seeds_the_log_once(tmp_path):
    from conftest import load_script
    review = load_script("review")
    dest = review.ensure_review_log(str(tmp_path))
    assert dest and (tmp_path / "docs" / "review_log.md").read_text().startswith("# Review log")
    assert review.ensure_review_log(str(tmp_path)) is None
