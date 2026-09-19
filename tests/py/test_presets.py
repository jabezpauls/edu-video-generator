import json
import re

import pytest

from conftest import SKILL, load_script

PRESETS = SKILL / "presets"
SHIPPED = ["blank", "chalkboard", "paper", "blueprint"]


@pytest.fixture(scope="module")
def ap():
    return load_script("apply_preset")


def parsed(ap, name):
    return ap.parse_jsonc((PRESETS / name / "preset.jsonc").read_text())


def test_jsonc_parser_keeps_urls_and_drops_comments_and_trailing_commas(ap):
    src = '{"a": "https://x.y/z", // note\n "b": [1, 2,], /* block */ "c": "// not a comment",}'
    assert ap.parse_jsonc(src) == {"a": "https://x.y/z", "b": [1, 2], "c": "// not a comment"}


@pytest.mark.parametrize("name", SHIPPED)
def test_shipped_presets_resolve(ap, name):
    r = ap.resolve(parsed(ap, name), PRESETS / name)
    assert set(r["colors"]) == {"bg", "ink", "ink2", "accent", "highlight", "card"}
    assert all(re.match(r"^#[0-9a-f]{6}$", v) for v in r["colors"].values())


def test_blank_documents_every_field_the_resolver_knows(ap):
    blank = parsed(ap, "blank")
    resolved = ap.resolve(blank, PRESETS / "blank")
    assert set(blank) == set(resolved)
    assert set(blank["colors"]) == set(ap.DEFAULT_COLORS)
    for role in ("display", "body"):
        assert set(blank["fonts"][role]) >= {"file", "ttf", "family", "weight"}
    assert set(blank["voice"]) == {"elevenlabs", "openai", "piper", "style"}
    assert set(blank["captions"]) == {"style", "position", "active_word"}
    # every key is explained by a comment on its own line or beside it
    text = (PRESETS / "blank" / "preset.jsonc").read_text()
    for key in ("colors", "fonts", "voice", "music", "sfx", "captions", "cards", "safe_area", "notes"):
        assert re.search(rf'//.*\n\s*"{key}"|"{key}".*//', text), key


@pytest.mark.parametrize("name", ["chalkboard", "paper", "blueprint"])
def test_fonts_exist_and_ship_with_their_licence(name):
    data = json.loads(
        re.sub(r"^\s*//.*$", "", (PRESETS / name / "preset.jsonc").read_text(), flags=re.M))
    folder = PRESETS / name
    licences = list((folder / "fonts").glob("OFL-*.txt"))
    assert len(licences) >= 2
    for t in licences:
        assert "SIL Open Font License" in t.read_text()
    for role in ("display", "body"):
        for key in ("file", "ttf"):
            assert (folder / data["fonts"][role][key]).is_file()
    assert (folder / data["fonts"]["display"]["file"]).read_bytes()[:4] == b"wOF2"


def test_blank_applies_with_defaults(ap, tmp_path):
    r = ap.apply("blank", tmp_path)
    assert r["colors"] == ap.DEFAULT_COLORS
    theme = (tmp_path / "scenes" / "theme.py").read_text()
    assert "FONT_DISPLAY = ''" in theme
    assert not (tmp_path / "scenes" / "public").exists()
    assert "FACES: ReadonlyArray<{ family: string; weight: number; file: string }> = [\n];" in (
        tmp_path / "scenes" / "src" / "theme.ts").read_text()


def test_apply_writes_fonts_theme_and_manifest(ap, tmp_path):
    (tmp_path / "manifest.json").write_text('{"slug": "x", "preset": null}')
    ap.apply("blueprint", tmp_path)
    for f in ("display.woff2", "display.ttf", "body.woff2", "body.ttf"):
        assert (tmp_path / "assets" / "fonts" / f).is_file()
    assert (tmp_path / "scenes" / "public" / "fonts" / "body.woff2").is_file()
    ns = {}
    exec((tmp_path / "scenes" / "theme.py").read_text().replace("__file__", repr(str(tmp_path / "scenes" / "theme.py"))), ns)
    assert ns["BG"] == "#0b2545" and ns["FONT_DISPLAY"] == "Space Grotesk SemiBold"
    assert ns["FONT_FILES"] == [str(tmp_path / "assets/fonts/display.ttf"), str(tmp_path / "assets/fonts/body.ttf")]
    ts = (tmp_path / "scenes" / "src" / "theme.ts").read_text()
    assert '"--accent": COLORS.accent' in ts and '"#4cc9f0"' in ts
    assert json.loads((tmp_path / "manifest.json").read_text())["preset"] == "blueprint"
    assert json.loads((tmp_path / "preset.json").read_text())["fonts"]["display"]["woff2"] == "assets/fonts/display.woff2"


def test_apply_is_rerunnable_and_switches_preset(ap, tmp_path):
    ap.apply("chalkboard", tmp_path)
    ap.apply("paper", tmp_path)
    assert "#f6f0e4" in (tmp_path / "scenes" / "theme.py").read_text()


def test_project_presets_beat_skill_presets(ap, tmp_path):
    mine = tmp_path / "presets" / "paper"
    mine.mkdir(parents=True)
    (mine / "preset.jsonc").write_text('{"name": "Mine", "colors": {"bg": "#123456"}}')
    assert ap.apply("paper", tmp_path)["colors"]["bg"] == "#123456"


@pytest.mark.parametrize("raw, msg", [
    ({"colors": {"bg": "red"}}, "not a hex colour"),
    ({"colors": {"sky": "#fff"}}, "unknown token"),
    ({"music": {"mood": "angry"}}, "music.mood"),
    ({"captions": {"style": "neon"}}, "captions.style"),
    ({"safe_area": {"21x9": {"top": 0.1}}}, "unknown format"),
    ({"safe_area": {"all": {"top": 0.9}}}, "fraction"),
    ({"fonts": {"display": {"file": "nope.woff2", "family": "X"}}}, "does not exist"),
])
def test_bad_presets_are_rejected(ap, tmp_path, raw, msg):
    with pytest.raises(ap.PresetError, match=msg):
        ap.resolve(raw, tmp_path)


def test_font_file_needs_family(ap, tmp_path):
    (tmp_path / "f.woff2").write_bytes(b"x")
    with pytest.raises(ap.PresetError, match="family is required"):
        ap.resolve({"fonts": {"body": {"file": "f.woff2"}}}, tmp_path)


def test_unknown_preset_lists_the_choices(ap, tmp_path):
    with pytest.raises(ap.PresetError, match="chalkboard"):
        ap.apply("nope", tmp_path)


def motion_project(tmp_path):
    (tmp_path / "film").mkdir()
    (tmp_path / "film" / "index.html").write_text("<html></html>")
    return tmp_path


def test_motion_project_gets_the_resolved_preset_and_woff2_only(ap, tmp_path):
    p = motion_project(tmp_path)
    ap.apply("chalkboard", p)
    assert (p / "assets/fonts/display.woff2").is_file() and (p / "assets/fonts/body.woff2").is_file()
    assert not list((p / "assets/fonts").glob("*.ttf"))
    assert not (p / "scenes").exists(), "theme files are for Manim and Remotion"
    r = json.loads((p / "preset.json").read_text())
    assert r["colors"]["highlight"] == "#ff8fa3" and r["fonts"]["body"]["woff2"] == "assets/fonts/body.woff2"
