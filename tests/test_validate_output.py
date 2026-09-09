"""
Tests for `bpmn_tool.py validate --json / --strict`.

`--json` is what lets the assistant close the loop by itself: generate, read the
findings as data, repair what is mechanical, re-validate. `--strict` is the
quality gate -- modelling warnings stop counting as advice and start failing.
"""
import json
from pathlib import Path

import pytest

from bpmn_build import run_build
from bpmn_tool import main as bpmn_tool_main
from bpmn_tool import validate

TESTS_DIR = Path(__file__).resolve().parent
REFERENCES_DIR = TESTS_DIR.parent / "references"
CLEAN_DIAGRAM = TESTS_DIR / "01-user-onboarding.bpmn"
BROKEN_DIAGRAM = REFERENCES_DIR / "example-broken.bpmn"

# A gateway with one way in and one way out: style advice (useless-gateway),
# nothing that should ever fail a build.
INFO_SPEC = {
    "id": "Process_ComInfo",
    "nodes": [
        {"id": "inicio", "type": "start", "name": "Começou"},
        {"id": "passagem", "type": "xor", "name": "Passagem"},
        {"id": "fim", "type": "end", "name": "Terminou"},
    ],
    "flows": [
        {"from": "inicio", "to": "passagem"},
        {"from": "passagem", "to": "fim"},
    ],
}

WARNING_SPEC = {
    "id": "Process_ComAviso",
    "nodes": [
        {"id": "inicio", "type": "start", "name": "Começou"},
        {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
        {"id": "fim", "type": "end", "name": "Terminou"},
    ],
    "flows": [
        {"from": "inicio", "to": "fazer"},
        {"from": "fazer", "to": "fim"},
        {"from": "fazer", "to": "fim"},
    ],
}


def warning_diagram(tmp_path):
    """A diagram with warnings but no errors: a duplicated connection."""
    spec_path = tmp_path / "com-aviso-spec.json"
    spec_path.write_text(json.dumps(WARNING_SPEC, ensure_ascii=False), encoding="utf-8")
    result = run_build(spec_path, tmp_path / "com-aviso.bpmn", copy_editor=False)
    assert result.problems == []
    assert result.warnings
    return result.output


def run_cli(argv):
    with pytest.raises(SystemExit) as exit_info:
        bpmn_tool_main(argv)
    return exit_info.value.code


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def test_json_output_of_a_clean_diagram_is_ok_and_empty(capsys):
    assert run_cli(["validate", str(CLEAN_DIAGRAM), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["findings"] == []
    assert payload["counts"] == {"error": 0, "warn": 0, "info": 0}
    assert payload["file"].endswith("01-user-onboarding.bpmn")


def test_json_output_of_a_broken_diagram_lists_findings_with_rule_and_severity(capsys):
    assert run_cli(["validate", str(BROKEN_DIAGRAM), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["counts"]["error"] >= 1
    for finding in payload["findings"]:
        assert set(finding) == {"rule", "severity", "element", "message", "fixable"}
        assert finding["severity"] in ("error", "warn", "info")
    assert "flow-refs-mismatch" in {f["rule"] for f in payload["findings"]}


def test_json_output_marks_which_findings_can_be_repaired_automatically(capsys):
    run_cli(["validate", str(BROKEN_DIAGRAM), "--json"])
    payload = json.loads(capsys.readouterr().out)
    fixable = {f["rule"] for f in payload["findings"] if f["fixable"]}
    assert "flow-refs-mismatch" in fixable


def test_json_output_stays_json_when_the_file_is_not_well_formed(tmp_path, capsys):
    broken_xml = tmp_path / "quebrado.bpmn"
    broken_xml.write_text("<bpmn:definitions>", encoding="utf-8")

    assert run_cli(["validate", str(broken_xml), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["findings"][0]["rule"] == "malformed-xml"
    assert payload["findings"][0]["severity"] == "error"


def test_json_output_includes_info_level_findings(tmp_path, capsys):
    """A style finding must reach the report, not be filtered out on the way."""
    spec_path = tmp_path / "com-info-spec.json"
    spec_path.write_text(json.dumps(INFO_SPEC, ensure_ascii=False), encoding="utf-8")
    diagram = run_build(spec_path, tmp_path / "com-info.bpmn", copy_editor=False).output

    run_cli(["validate", str(diagram), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["counts"]["info"] >= 1
    assert "useless-gateway" in {f["rule"] for f in payload["findings"] if f["severity"] == "info"}


# ---------------------------------------------------------------------------
# --strict
# ---------------------------------------------------------------------------

def test_warnings_pass_by_default_and_fail_under_strict(tmp_path):
    diagram = warning_diagram(tmp_path)
    assert run_cli(["validate", str(diagram)]) == 0
    assert run_cli(["validate", str(diagram), "--strict"]) == 1


def test_strict_mode_still_passes_a_clean_diagram():
    assert run_cli(["validate", str(CLEAN_DIAGRAM), "--strict"]) == 0


def test_strict_and_json_can_be_combined(tmp_path, capsys):
    diagram = warning_diagram(tmp_path)
    assert run_cli(["validate", str(diagram), "--strict", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False, "under --strict a warning is a failure"
    assert payload["strict"] is True


def test_info_findings_alone_do_not_fail_even_under_strict(tmp_path, capsys):
    """Style advice is never a gate: only errors and warnings can fail a build."""
    spec_path = tmp_path / "so-info-spec.json"
    spec_path.write_text(json.dumps(INFO_SPEC, ensure_ascii=False), encoding="utf-8")
    diagram = run_build(spec_path, tmp_path / "so-info.bpmn", copy_editor=False).output

    exit_code = run_cli(["validate", str(diagram), "--strict", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["counts"]["info"] >= 1, "this fixture exists to carry info findings"
    assert payload["counts"]["error"] == 0 and payload["counts"]["warn"] == 0
    assert payload["ok"] is True
    assert exit_code == 0, "info findings must never fail a build, not even under --strict"


# ---------------------------------------------------------------------------
# The text output the humans (and verify_tests.py) already rely on
# ---------------------------------------------------------------------------

def test_text_output_of_a_broken_diagram_still_lists_the_problems(capsys):
    assert validate(str(BROKEN_DIAGRAM)) is False
    err = capsys.readouterr().err
    assert "Stage 2 (control-flow lint)" in err
    assert "Task_DoesNotExist" in err


def test_text_output_of_a_clean_diagram_still_says_it_passed(capsys):
    assert validate(str(CLEAN_DIAGRAM)) is True
    assert "All checks passed" in capsys.readouterr().out


def test_validate_keeps_its_single_argument_signature():
    assert validate(str(CLEAN_DIAGRAM)) is True


def test_strict_is_available_through_the_python_api(tmp_path):
    diagram = warning_diagram(tmp_path)
    assert validate(str(diagram)) is True
    assert validate(str(diagram), strict=True) is False
