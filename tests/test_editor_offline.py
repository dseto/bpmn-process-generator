"""
Tests for the editor's offline mode.

The editor is used under `file://`, often on a machine with no internet or on a
corporate network that blocks unpkg -- and then a CDN-only editor opens as a
blank page. So the generator embeds the bpmn-js assets whenever they are present
in `assets/vendor/`, and falls back to the CDN when they are not.

The real .js/.css/.woff files are not in the repository (they cannot be
downloaded from here), so these tests exercise the MECHANISM with stand-in files
and assert the fallback is intact meanwhile.
"""
import importlib
from pathlib import Path

import pytest

import generate_editor_html

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "assets" / "vendor"
EDITOR = ROOT / "editor.html"

REQUIRED_ASSETS = ("bpmn-modeler.production.min.js", "diagram-js.css", "bpmn.css")


def render_with_vendor(tmp_path, files):
    """Render the editor against a fake vendor directory."""
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    for name, content in files.items():
        (vendor / name).write_text(content, encoding="utf-8")
    return generate_editor_html.render_editor_html(vendor_dir=vendor)


# ---------------------------------------------------------------------------
# The mechanism
# ---------------------------------------------------------------------------

def test_the_generator_can_render_against_a_vendor_directory():
    assert hasattr(generate_editor_html, "render_editor_html")
    assert hasattr(generate_editor_html, "VENDOR_DIR")


def test_vendored_assets_are_inlined_instead_of_fetched(tmp_path):
    html = render_with_vendor(tmp_path, {
        "bpmn-modeler.production.min.js": "window.BpmnJS = function () {};",
        "diagram-js.css": ".djs-container { color: red; }",
        "bpmn.css": ".bpmn-icon-task { color: blue; }",
    })

    assert "window.BpmnJS = function () {};" in html
    assert ".djs-container { color: red; }" in html
    assert ".bpmn-icon-task { color: blue; }" in html
    assert "unpkg.com" not in html, "with local assets the editor must not reach the network"


def test_the_offline_editor_states_that_it_is_self_contained(tmp_path):
    html = render_with_vendor(tmp_path, {
        "bpmn-modeler.production.min.js": "// modeler",
        "diagram-js.css": "/* diagram */",
        "bpmn.css": "/* bpmn */",
    })
    assert 'name="bpmn-editor-assets" content="vendored"' in html


def test_the_bpmn_font_is_embedded_as_a_data_uri_when_present(tmp_path):
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "bpmn-modeler.production.min.js").write_text("// modeler", encoding="utf-8")
    (vendor / "diagram-js.css").write_text("/* diagram */", encoding="utf-8")
    (vendor / "bpmn.css").write_text(
        "@font-face { src: url('../font/bpmn.woff') format('woff'); }", encoding="utf-8")
    (vendor / "bpmn.woff").write_bytes(b"fake-woff-bytes")

    html = generate_editor_html.render_editor_html(vendor_dir=vendor)

    assert "data:font/woff;base64," in html
    assert "../font/bpmn.woff" not in html, "the font reference must be rewritten, not kept"


# ---------------------------------------------------------------------------
# The fallback, which is what ships today
# ---------------------------------------------------------------------------

def test_without_vendored_assets_the_editor_still_loads_from_the_cdn(tmp_path):
    empty = tmp_path / "empty-vendor"
    empty.mkdir()
    html = generate_editor_html.render_editor_html(vendor_dir=empty)

    assert "https://unpkg.com/bpmn-js@17.0.0/dist/bpmn-modeler.production.min.js" in html
    assert 'name="bpmn-editor-assets" content="cdn"' in html


def test_a_partial_vendor_directory_is_not_used_half_way(tmp_path):
    """All three assets or none -- half-vendored would load two of three and break."""
    html = render_with_vendor(tmp_path, {"bpmn-modeler.production.min.js": "// só o js"})
    assert "unpkg.com" in html
    assert 'name="bpmn-editor-assets" content="cdn"' in html


def test_the_committed_editor_declares_which_mode_it_was_built_in():
    html = EDITOR.read_text(encoding="utf-8")
    assert 'name="bpmn-editor-assets"' in html


def test_the_vendor_directory_is_documented_for_whoever_fills_it():
    readme = ROOT / "assets" / "vendor" / "README.md"
    assert readme.exists(), "assets/vendor/README.md tells a human which files to drop there"
    text = readme.read_text(encoding="utf-8")
    for asset in REQUIRED_ASSETS:
        assert asset in text, f"{asset} should be listed in assets/vendor/README.md"
    assert "generate_editor_html.py" in text, "it must say to regenerate the editor afterwards"


def test_the_shipped_editor_matches_the_assets_actually_vendored():
    """
    Asserts in both directions instead of skipping, so this test starts guarding
    offline mode the moment somebody drops the bpmn-js files into assets/vendor/
    (and, until then, guards that the editor is honestly marked as CDN-backed).
    """
    importlib.reload(generate_editor_html)
    html = EDITOR.read_text(encoding="utf-8")
    vendored = all((VENDOR / name).exists() for name in REQUIRED_ASSETS)

    assert html == generate_editor_html.html_content, (
        "editor.html is out of date -- run `python scripts/generate_editor_html.py`")

    if vendored:
        assert 'name="bpmn-editor-assets" content="vendored"' in html
        assert "unpkg.com" not in html, "with the assets vendored the editor must not need the network"
    else:
        assert 'name="bpmn-editor-assets" content="cdn"' in html
        assert "unpkg.com" in html, "without local assets the CDN fallback must still be wired"
