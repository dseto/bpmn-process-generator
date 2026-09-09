"""
Tests for the `bpmn_build.py` command line: one command that turns a spec into
a diagram ready to open -- generate, lay out, validate, and drop the editor next
to the file.
"""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bpmn_build import main, run_build
from bpmn_tool import BPMNDI_NS, stage2_lint

NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}

GOOD_SPEC = {
    "id": "Process_Compras",
    "name": "Compra de material",
    "lanes": [{"id": "requisitante", "name": "Requisitante"}, {"id": "compras", "name": "Compras"}],
    "nodes": [
        {"id": "necessidade", "type": "start", "name": "Necessidade identificada", "lane": "requisitante"},
        {"id": "solicitar", "type": "userTask", "name": "Solicitar compra", "lane": "requisitante"},
        {"id": "avaliar", "type": "xor", "name": "Dentro do orçamento?", "lane": "compras"},
        {"id": "comprar", "type": "serviceTask", "name": "Emitir pedido", "lane": "compras"},
        {"id": "recusar", "type": "userTask", "name": "Devolver ao requisitante", "lane": "compras"},
        {"id": "comprado", "type": "end", "name": "Pedido emitido", "lane": "compras"},
        {"id": "recusado", "type": "end", "name": "Solicitação devolvida", "lane": "compras"},
    ],
    "flows": [
        {"from": "necessidade", "to": "solicitar"},
        {"from": "solicitar", "to": "avaliar"},
        {"from": "avaliar", "to": "comprar", "label": "Sim", "condition": "valor <= orcamento"},
        {"from": "avaliar", "to": "recusar", "label": "Não", "default": True},
        {"from": "comprar", "to": "comprado"},
        {"from": "recusar", "to": "recusado"},
    ],
}

# Valid as a spec, but a process the linter rejects: the task is a dead end and
# there is no end event.
LINT_BREAKING_SPEC = {
    "id": "Process_Incompleto",
    "nodes": [
        {"id": "inicio", "type": "start", "name": "Começou"},
        {"id": "fazer", "type": "task", "name": "Fazer algo"},
    ],
    "flows": [{"from": "inicio", "to": "fazer"}],
}


def write_spec(directory: Path, spec: dict, name: str = "processo-spec.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The happy path: a diagram ready to open
# ---------------------------------------------------------------------------

def test_build_writes_a_laid_out_diagram_that_passes_the_linter(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "compras.bpmn"

    result = run_build(spec_path, out, copy_editor=False)

    assert result.output == out
    assert result.problems == []
    assert out.exists()

    tree = ET.parse(out)
    problems, _warnings = stage2_lint(tree)
    assert not problems


def test_generated_file_carries_the_layout_section(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "compras.bpmn"
    run_build(spec_path, out, copy_editor=False)

    root = ET.parse(out).getroot()
    plane = root.find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
    assert plane is not None
    shapes = plane.findall(f"{{{BPMNDI_NS}}}BPMNShape")
    edges = plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge")
    assert len(shapes) >= len(GOOD_SPEC["nodes"])  # nodes plus the two lane bands
    assert len(edges) == len(GOOD_SPEC["flows"])


def test_generated_file_declares_the_five_canonical_namespaces(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "compras.bpmn"
    run_build(spec_path, out, copy_editor=False)

    xml = out.read_text(encoding="utf-8")
    assert xml.startswith("<?xml version=")
    for prefix in ("bpmn", "bpmndi", "omgdc", "omgdi", "xsi"):
        assert f"xmlns:{prefix}=" in xml


def test_building_the_same_spec_twice_produces_the_same_file(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    first = tmp_path / "a.bpmn"
    second = tmp_path / "b.bpmn"
    run_build(spec_path, first, copy_editor=False)
    run_build(spec_path, second, copy_editor=False)
    assert first.read_bytes() == second.read_bytes()


def test_output_path_defaults_to_the_spec_name_with_a_bpmn_extension(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC, name="compra-material-spec.json")
    result = run_build(spec_path, None, copy_editor=False)
    assert result.output == tmp_path / "compra-material-spec.bpmn"
    assert result.output.exists()


def test_missing_output_directory_is_created(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "novo" / "projeto" / "compras.bpmn"
    run_build(spec_path, out, copy_editor=False)
    assert out.exists()


# ---------------------------------------------------------------------------
# The editor lands next to the diagram
# ---------------------------------------------------------------------------

def test_editor_is_copied_next_to_the_generated_diagram(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "projeto" / "compras.bpmn"

    run_build(spec_path, out)

    editor = out.parent / "editor.html"
    assert editor.exists(), "the requesting project should get its own editor.html"
    assert editor.stat().st_size > 0


def test_copied_editor_opens_the_generated_diagram_by_default(tmp_path):
    """
    The editor handed to a project must open THAT project's diagram, never a
    skill example -- that is what `copy_editor_if_needed` configures while
    copying. (Preserving a locally edited editor is T-14's job, not this one.)
    """
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "projeto" / "compras.bpmn"

    run_build(spec_path, out)

    editor_html = (out.parent / "editor.html").read_text(encoding="utf-8")
    assert 'let DEFAULT_DIAGRAM_NAME = "compras.bpmn";' in editor_html
    assert "bus-boarding-process" not in editor_html, "skill examples must not ship to a project"


def test_copying_the_editor_can_be_turned_off(tmp_path):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "projeto" / "compras.bpmn"
    run_build(spec_path, out, copy_editor=False)
    assert not (out.parent / "editor.html").exists()


# ---------------------------------------------------------------------------
# Exit codes -- the assistant reads these to decide whether to repair
# ---------------------------------------------------------------------------

def test_cli_exits_zero_and_reports_the_paths_on_success(tmp_path, capsys):
    spec_path = write_spec(tmp_path, GOOD_SPEC)
    out = tmp_path / "compras.bpmn"

    exit_code = main([str(spec_path), "-o", str(out), "--no-copy-editor"])

    assert exit_code == 0
    assert str(out) in capsys.readouterr().out


def test_cli_rejects_a_malformed_spec_without_writing_a_diagram(tmp_path, capsys):
    spec_path = write_spec(tmp_path, {"id": "P", "nodes": [{"id": "a", "type": "megaTask"}], "flows": []})
    out = tmp_path / "quebrado.bpmn"

    exit_code = main([str(spec_path), "-o", str(out), "--no-copy-editor"])

    assert exit_code == 1
    assert "megaTask" in capsys.readouterr().err
    assert not out.exists()


def test_cli_fails_when_the_generated_diagram_does_not_pass_the_linter(tmp_path, capsys):
    spec_path = write_spec(tmp_path, LINT_BREAKING_SPEC)
    out = tmp_path / "incompleto.bpmn"

    exit_code = main([str(spec_path), "-o", str(out), "--no-copy-editor"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "endEvent" in err
    # The file is still written: the point is to let a human open and fix it.
    assert out.exists()


def test_cli_reports_a_missing_spec_file(tmp_path, capsys):
    exit_code = main([str(tmp_path / "nao-existe.json"), "--no-copy-editor"])
    assert exit_code == 1
    assert "nao-existe.json" in capsys.readouterr().err


def test_run_build_reports_lint_problems_instead_of_raising(tmp_path):
    spec_path = write_spec(tmp_path, LINT_BREAKING_SPEC)
    result = run_build(spec_path, tmp_path / "incompleto.bpmn", copy_editor=False)
    assert result.problems
    assert any("endEvent" in problem for problem in result.problems)


def test_canonical_example_spec_builds_end_to_end(tmp_path):
    example = Path(__file__).resolve().parent.parent / "references" / "example-spec.json"
    result = run_build(example, tmp_path / "exemplo.bpmn", copy_editor=False)
    assert result.problems == []
