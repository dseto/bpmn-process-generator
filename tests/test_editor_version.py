"""
Tests for the versioning of the editor copy a project receives.

Two things must both be true, and they pull in opposite directions:
  - a project that got the editor once should still benefit when the skill
    improves it (otherwise every project freezes on the version it first saw);
  - a copy the user edited by hand must never be silently overwritten.

So: an untouched copy is refreshed, an edited copy is preserved and reported,
and `--force` is the explicit way to discard local edits.
"""
import re
from pathlib import Path

import pytest

import generate_editor_html
from bpmn_tool import (EDITOR_VERSION_META, copy_editor_if_needed, editor_version_of,
                        main as bpmn_tool_main, was_edited_locally)

ROOT = Path(__file__).resolve().parent.parent
EDITOR = ROOT / "editor.html"


@pytest.fixture
def project(tmp_path):
    """A project directory with a diagram, ready to receive the editor."""
    diagram = tmp_path / "processo.bpmn"
    diagram.write_text((ROOT / "tests" / "01-user-onboarding.bpmn").read_text(encoding="utf-8"),
                        encoding="utf-8")
    return tmp_path, diagram


# ---------------------------------------------------------------------------
# The version stamp
# ---------------------------------------------------------------------------

def test_the_generator_declares_an_editor_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", generate_editor_html.EDITOR_VERSION)


def test_the_committed_editor_carries_the_version_meta_tag():
    html = EDITOR.read_text(encoding="utf-8")
    assert EDITOR_VERSION_META in html
    assert editor_version_of(html) == generate_editor_html.EDITOR_VERSION


def test_a_file_without_the_meta_tag_reads_as_no_version():
    assert editor_version_of("<html><head></head></html>") is None


def test_the_copy_delivered_to_a_project_keeps_the_version(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    assert editor_version_of(copied.read_text(encoding="utf-8")) == generate_editor_html.EDITOR_VERSION


# ---------------------------------------------------------------------------
# Refreshing an untouched copy
# ---------------------------------------------------------------------------

def test_an_untouched_copy_is_refreshed_when_the_skill_moves_on(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)

    aged = copied.read_text(encoding="utf-8").replace(
        f'content="{generate_editor_html.EDITOR_VERSION}"', 'content="0.0.1"')
    copied.write_text(aged, encoding="utf-8")
    assert editor_version_of(copied.read_text(encoding="utf-8")) == "0.0.1"

    copy_editor_if_needed(directory, diagram)

    assert editor_version_of(copied.read_text(encoding="utf-8")) == generate_editor_html.EDITOR_VERSION


def test_refreshing_still_points_the_editor_at_the_project_diagram(project):
    directory, diagram = project
    copy_editor_if_needed(directory, diagram)
    copy_editor_if_needed(directory, diagram)
    html = (directory / "editor.html").read_text(encoding="utf-8")
    assert 'let DEFAULT_DIAGRAM_NAME = "processo.bpmn";' in html


# ---------------------------------------------------------------------------
# Preserving a copy the user edited
# ---------------------------------------------------------------------------

def test_a_freshly_copied_editor_does_not_look_edited(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    assert was_edited_locally(copied.read_text(encoding="utf-8")) is False


def test_a_single_hand_edit_is_detected(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    copied.write_text(copied.read_text(encoding="utf-8") + "\n<!-- ajuste local -->", encoding="utf-8")
    assert was_edited_locally(copied.read_text(encoding="utf-8")) is True


def test_an_edited_copy_is_never_overwritten_silently(project, capsys):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    edited = copied.read_text(encoding="utf-8") + "\n<!-- ajuste local -->"
    copied.write_text(edited, encoding="utf-8")

    copy_editor_if_needed(directory, diagram)

    assert copied.read_text(encoding="utf-8") == edited
    out = capsys.readouterr().out
    assert "--force" in out, "the user must be told how to overwrite on purpose"


def test_force_overwrites_an_edited_copy(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    copied.write_text(copied.read_text(encoding="utf-8") + "\n<!-- ajuste local -->", encoding="utf-8")

    copy_editor_if_needed(directory, diagram, force=True)

    assert was_edited_locally(copied.read_text(encoding="utf-8")) is False


def test_an_edited_copy_is_preserved_even_when_it_is_outdated(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    aged = copied.read_text(encoding="utf-8").replace(
        f'content="{generate_editor_html.EDITOR_VERSION}"', 'content="0.0.1"')
    copied.write_text(aged + "\n<!-- ajuste local -->", encoding="utf-8")

    copy_editor_if_needed(directory, diagram)

    assert "<!-- ajuste local -->" in copied.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_copy_editor_subcommand_accepts_force(project):
    directory, diagram = project
    copied = copy_editor_if_needed(directory, diagram)
    copied.write_text(copied.read_text(encoding="utf-8") + "\n<!-- ajuste local -->", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        bpmn_tool_main(["copy-editor", str(directory), str(diagram), "--force"])

    assert exit_info.value.code == 0
    assert was_edited_locally(copied.read_text(encoding="utf-8")) is False
