import json
import re
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

Make = Callable[..., TestClient]

SRC = Path(__file__).resolve().parents[2] / "src" / "app"
CSS = (SRC / "static" / "style.css").read_text(encoding="utf-8")
TEMPLATES = sorted((SRC / "templates").glob("*.html"))
URL_ATTRS = ("src", "href", "action", "hx-post", "hx-get", "hx-put", "hx-patch", "hx-delete")


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def parse(html: str) -> list[tuple[str, dict[str, str | None]]]:
    p = Tags()
    p.feed(html)
    return p.tags


def index(make_client: Make) -> str:
    return make_client().get("/").text


# I7
def test_index_loads_only_same_origin_resources(make_client: Make) -> None:
    for _, attrs in parse(index(make_client)):
        for key in URL_ATTRS:
            value = attrs.get(key)
            if value is None:
                continue
            assert value.startswith("#") or (
                value.startswith("/") and not value.startswith("//")
            ), (key, value)


def test_theme_switch_is_script_free_checkbox(make_client: Make) -> None:
    html = index(make_client)
    boxes = [a for t, a in parse(html) if t == "input" and a.get("id") == "theme"]
    assert len(boxes) == 1 and boxes[0].get("type") == "checkbox"
    assert 'for="theme"' in html
    assert ":root:has(#theme:checked)" in CSS


def test_only_script_is_bundled_htmx(make_client: Make) -> None:
    html = index(make_client)
    scripts = [a for t, a in parse(html) if t == "script"]
    assert len(scripts) == 1
    assert scripts[0].get("src") == "/static/htmx.min.js"
    assert re.search(r"<script[^>]*>\s*[^<\s]", html) is None


def test_stylesheet_has_required_rules() -> None:
    assert "@media (prefers-color-scheme: dark)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert ":focus-visible" in CSS


def test_stylesheet_has_no_forbidden_features() -> None:
    for word in ("gradient", "backdrop-filter", "blur", "@font-face", "@import", "url(", "http"):
        assert word not in CSS, word


def test_size_budget(make_client: Make) -> None:
    assert len(CSS.encode()) <= 12 * 1024
    assert len(index(make_client).encode()) <= 8 * 1024


def test_no_inline_style_or_emoji() -> None:
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8")
        assert "<style" not in text
        assert not re.search(r"\sstyle=", text)
        assert not re.search("[\U0001f300-\U0001faff☀-➿]", text), path


def test_templates_do_not_use_safe() -> None:
    for path in [*TEMPLATES, SRC / "ui.py"]:
        lines = path.read_text(encoding="utf-8").splitlines()
        text = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
        assert not re.search(r"\|\s*safe\b", text), path
        assert "Markup" not in text, path


def test_every_field_has_a_label(make_client: Make) -> None:
    tags = parse(index(make_client))
    labels = {a.get("for") for t, a in tags if t == "label"}
    ids = [a.get("id") for t, a in tags if t in ("input", "select")]
    assert ids
    for field_id in ids:
        assert field_id in labels


def test_page_has_lang_viewport_title(make_client: Make) -> None:
    html = index(make_client)
    tags = parse(html)
    assert any(t == "html" and a.get("lang") for t, a in tags)
    assert any(t == "meta" and a.get("name") == "viewport" for t, a in tags)
    assert re.search(r"<title>\s*\S", html)


def test_submit_button_is_disabled_by_htmx(make_client: Make) -> None:
    tags = parse(index(make_client))
    forms = [a for t, a in tags if t == "form"]
    assert forms[0].get("hx-disabled-elt") == "#submit"
    assert any(t == "button" and a.get("id") == "submit" for t, a in tags)
    busy = [a for _, a in tags if a.get("id") == "busy"][0]
    assert "hidden" not in busy
    assert "aria-hidden" not in busy


def test_htmx_indicator_styles_disabled(make_client: Make) -> None:
    tags = parse(index(make_client))
    metas = [a for t, a in tags if t == "meta" and a.get("name") == "htmx-config"]
    content = metas[0].get("content")
    assert content is not None
    config = json.loads(content)
    assert config["includeIndicatorStyles"] is False
    assert config["responseHandling"] == [{"code": ".*", "swap": True}]


def test_indicator_rules_live_in_stylesheet() -> None:
    assert ".htmx-indicator" in CSS
    assert ".htmx-request" in CSS


def channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))


def schemes() -> list[dict[str, str]]:
    dark_at = CSS.index("prefers-color-scheme: dark")
    return [tokens(CSS[:dark_at]), tokens(CSS[dark_at:])]


def test_palette_contrast_meets_aa() -> None:
    for t in schemes():
        for bg in ("paper", "panel"):
            for fg in ("ink", "muted", "accent", "error"):
                assert ratio(t[fg], t[bg]) >= 4.5, (fg, bg)
        assert ratio(t["on-accent"], t["accent"]) >= 4.5
        assert ratio(t["rule"], t["paper"]) >= 3


def test_form_fields_unchanged(make_client: Make) -> None:
    tags = parse(index(make_client))
    form = [a for t, a in tags if t == "form"][0]
    assert form.get("hx-post") == "/ui/decode"
    assert form.get("hx-target") == "#result"
    assert form.get("hx-encoding") == "multipart/form-data"
    assert form.get("enctype") == "multipart/form-data"
    names = {a.get("name") for t, a in tags if t in ("input", "select")}
    assert {"file", "language"} <= names
