"""
Tests for the editor's own features.

`editor.html` is a BUILD OUTPUT of scripts/generate_editor_html.py -- never edit
it by hand. The first test here pins exactly that: the committed file must match
what the generator renders, so a hand edit (which the next regeneration would
silently throw away) fails the suite instead.

The feature tests are static checks on the rendered HTML: they prove the panel,
its fields and its bpmn-js wiring are present. Whether it FEELS right is a
manual check in the browser -- see the contract's manual verification step.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EDITOR = ROOT / "editor.html"


@pytest.fixture(scope="module")
def editor_html():
    return EDITOR.read_text(encoding="utf-8")


def test_the_committed_editor_matches_what_the_generator_renders(editor_html):
    from generate_editor_html import html_content

    assert editor_html == html_content, (
        "editor.html is out of date with scripts/generate_editor_html.py. "
        "It is a build output: change the generator and run "
        "`python scripts/generate_editor_html.py`, never edit editor.html by hand."
    )


# ---------------------------------------------------------------------------
# Properties panel
# ---------------------------------------------------------------------------

def test_the_editor_has_a_properties_panel(editor_html):
    assert 'id="properties-panel"' in editor_html
    assert 'id="btn-props-toggle"' in editor_html


def test_the_panel_edits_name_and_documentation(editor_html):
    assert 'id="prop-name"' in editor_html
    assert 'id="prop-documentation"' in editor_html
    assert "updateLabel" in editor_html, "renaming goes through modeling.updateLabel"
    assert "bpmn:Documentation" in editor_html, "documentation is a moddle element"


def test_the_panel_shows_the_element_id_without_letting_it_be_edited(editor_html):
    match = re.search(r'<input[^>]*id="prop-id"[^>]*>', editor_html)
    assert match, "the panel should show the element id"
    assert "readonly" in match.group(0), "ids are generated, not typed"


def test_the_panel_can_convert_an_element_to_another_type(editor_html):
    assert 'id="prop-type"' in editor_html
    assert "bpmnReplace" in editor_html, "type conversion goes through bpmnReplace"
    for option in ("bpmn:UserTask", "bpmn:ServiceTask", "bpmn:ExclusiveGateway", "bpmn:ParallelGateway"):
        assert option in editor_html, f"{option} should be offered as a conversion target"


def test_the_panel_edits_the_condition_and_the_default_of_a_flow(editor_html):
    assert 'id="prop-condition"' in editor_html
    assert 'id="prop-default"' in editor_html
    assert "bpmn:FormalExpression" in editor_html, "a condition is a formal expression"
    assert "conditionExpression" in editor_html


def test_the_panel_reacts_to_the_current_selection(editor_html):
    assert "updatePropertiesPanel" in editor_html
    assert re.search(r"selection\.changed", editor_html), "the panel follows selection.changed"


def test_the_panel_says_when_nothing_is_selected(editor_html):
    assert 'id="prop-empty"' in editor_html


def test_editing_a_property_marks_the_file_as_unsaved(editor_html):
    """Otherwise a rename looks saved and is lost on close."""
    assert "commandStack.changed" in editor_html


# ---------------------------------------------------------------------------
# The panel must not break what already worked
# ---------------------------------------------------------------------------

def test_the_canvas_still_fills_the_workspace(editor_html):
    assert 'id="canvas"' in editor_html
    assert 'id="workspace"' in editor_html, "canvas and panel share a flex workspace"


def test_existing_toolbar_features_are_still_there(editor_html):
    for control in ("btn-save", "btn-open", "btn-undo", "btn-redo", "btn-route-90",
                     "btn-export-svg", "btn-export-png", "btn-font-bold", "btn-search"):
        assert f'id="{control}"' in editor_html, f"{control} disappeared from the toolbar"


def test_the_editor_still_embeds_its_presets(editor_html):
    assert "/*PRESETS_START*/" in editor_html
    assert "/*PRESETS_END*/" in editor_html
    assert "DEFAULT_DIAGRAM_NAME" in editor_html


# ---------------------------------------------------------------------------
# Validation panel
# ---------------------------------------------------------------------------

def test_the_editor_can_validate_the_open_diagram(editor_html):
    assert 'id="btn-validate"' in editor_html
    assert 'id="validation-results"' in editor_html
    assert "runDiagramValidation" in editor_html


@pytest.mark.parametrize("rule", [
    "dead-end",
    "unreachable-node",
    "no-path-to-end",
    "gateway-without-condition",
    "unnamed-element",
    "lane-coverage-missing",
])
def test_the_editor_checks_the_same_rules_the_linter_does(editor_html, rule):
    """
    Same rule ids as scripts/lint_rules.py, so what the editor shows and what
    `bpmn_tool validate` reports are the same vocabulary, not two dialects.
    """
    assert f"'{rule}'" in editor_html


def test_every_rule_the_editor_checks_exists_in_the_python_linter(editor_html):
    import lint_rules

    editor_rules = set(re.findall(r"rule:\s*'([a-z0-9-]+)'", editor_html))
    assert editor_rules, "the editor should carry rule ids"
    known = {rule.name for rule in lint_rules.RULES}
    assert editor_rules <= known, f"editor invents rules the linter does not have: {editor_rules - known}"


def test_a_validation_finding_selects_the_element_it_is_about(editor_html):
    assert "selectValidationFinding" in editor_html
    assert "elementRegistry" in editor_html


def test_validation_reports_a_clean_diagram_too(editor_html):
    assert "Nenhum problema encontrado" in editor_html


# ---------------------------------------------------------------------------
# Arrangement tools and PDF export
# ---------------------------------------------------------------------------

def test_the_editor_can_align_and_distribute_the_selection(editor_html):
    assert 'id="btn-align-left"' in editor_html
    assert 'id="btn-align-middle"' in editor_html
    assert 'id="btn-distribute-h"' in editor_html
    assert "alignElements" in editor_html, "alignment uses the native bpmn-js module"
    assert "distributeElements" in editor_html


def test_alignment_needs_at_least_two_elements(editor_html):
    assert "Selecione pelo menos 2 elementos" in editor_html


def test_the_editor_can_print_the_diagram_as_pdf(editor_html):
    assert 'id="btn-export-pdf"' in editor_html
    assert "exportPDF" in editor_html
    assert "@page" in editor_html, "printing needs a page stylesheet"
