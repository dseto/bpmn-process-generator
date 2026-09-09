"""
Contract tests for the skill's own documentation.

SKILL.md is the file the assistant actually follows, so it is executable
documentation in practice: if it still says "write the XML by hand", that is
what will happen. These tests pin the workflow it must teach and check that
every script, file and command it names really exists.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def skill():
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme():
    return README.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The workflow SKILL.md must teach
# ---------------------------------------------------------------------------

def test_skill_sends_the_assistant_through_the_spec_generator(skill):
    assert "scripts/bpmn_build.py" in skill
    assert "references/process-spec.md" in skill


def test_skill_no_longer_presents_hand_written_xml_as_the_main_path(skill):
    """
    Writing the XML directly is the source of the errors this skill now prevents;
    the XML reference stays as debugging material, not as step 2.
    """
    assert not re.search(r"###\s*Passo\s*2[^\n]*Gerar o XML BPMN", skill), \
        "step 2 must be 'generate from the spec', not 'write the XML'"


def test_skill_has_a_clarification_step_before_modelling(skill):
    assert re.search(r"Passo\s*0", skill), "the workflow needs a step 0 for clarification"
    lowered = skill.lower()
    for topic in ("ator", "gatilho", "exce", "retrabalho", "prazo"):
        assert topic in lowered, f"the clarification checklist should cover '{topic}'"


def test_skill_documents_the_validation_and_repair_loop(skill):
    assert "--json" in skill
    assert "--strict" in skill
    assert re.search(r"bpmn_tool\.py\s+fix", skill), "the fix subcommand must be documented"


def test_skill_documents_reverse_extraction_for_editing_an_existing_diagram(skill):
    assert re.search(r"bpmn_tool\.py\s+extract", skill)


def test_skill_states_the_naming_conventions(skill):
    lowered = skill.lower()
    assert "infinitivo" in lowered, "task naming convention (verb in the infinitive)"
    assert "gateway" in lowered


def test_skill_keeps_the_editor_delivery_rules(skill):
    """The rules that stop the assistant handing out a link into the skill folder."""
    assert "editor.html" in skill
    assert "?file=" in skill


# ---------------------------------------------------------------------------
# Everything the docs name must exist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("doc_name", ["SKILL.md", "README.md"])
def test_every_repo_path_mentioned_in_the_docs_exists(doc_name):
    text = (ROOT / doc_name).read_text(encoding="utf-8")
    mentioned = set(re.findall(r"`((?:scripts|references|assets|tests)/[A-Za-z0-9_.\-]+)`", text))
    assert mentioned, f"{doc_name} should reference the repository's files"
    missing = sorted(path for path in mentioned if not (ROOT / path).exists())
    assert not missing, f"{doc_name} references files that do not exist: {missing}"


@pytest.mark.parametrize("doc_name", ["SKILL.md", "README.md"])
def test_docs_do_not_advertise_removed_scripts(doc_name):
    text = (ROOT / doc_name).read_text(encoding="utf-8")
    for script in re.findall(r"python\s+(scripts/[A-Za-z0-9_.\-]+)", text):
        assert (ROOT / script).exists(), f"{doc_name} tells the user to run a missing {script}"


def test_readme_documents_the_new_commands(readme):
    assert "bpmn_build.py" in readme
    assert "--strict" in readme
    assert re.search(r"bpmn_tool\.py\s+fix", readme)
    assert re.search(r"bpmn_tool\.py\s+extract", readme)


def test_readme_and_skill_agree_on_the_repository_layout(readme, skill):
    for entry in ("scripts/bpmn_build.py", "scripts/lint_rules.py", "references/process-spec.md"):
        name = entry.split("/")[-1]
        assert name in readme, f"README's tree is missing {name}"
        assert name in skill, f"SKILL.md's tree is missing {name}"
