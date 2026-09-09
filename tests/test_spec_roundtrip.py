"""
Tests for `bpmn_tool.py extract` -- turning an existing .bpmn back into a spec.

This is what makes "change this process by describing the change" possible: the
assistant extracts the spec from the diagram on disk (hand edits in the editor
included), edits the spec, and rebuilds. So what matters here is that a
round-trip keeps the PROCESS intact -- nodes, their kinds and names, the flows
with their labels/conditions/default branch, and the lanes.
"""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bpmn_build import build_tree, build_xml, load_spec, run_build
from bpmn_tool import ExtractError, extract_spec, stage2_lint

TESTS_DIR = Path(__file__).resolve().parent
REFERENCES_DIR = TESTS_DIR.parent / "references"

FULL_SPEC = {
    "id": "Process_Reembolso",
    "name": "Reembolso de despesa",
    "executable": False,
    "lanes": [{"id": "colaborador", "name": "Colaborador"}, {"id": "financeiro", "name": "Financeiro"}],
    "nodes": [
        {"id": "despesa", "type": "start", "name": "Despesa realizada", "event": "message", "lane": "colaborador"},
        {"id": "lancar", "type": "userTask", "name": "Lançar despesa", "lane": "colaborador"},
        {"id": "conferir", "type": "userTask", "name": "Conferir comprovantes", "lane": "financeiro"},
        {"id": "prazo", "type": "boundary", "name": "Prazo de 5 dias", "event": "timer",
         "attachedTo": "conferir", "lane": "financeiro"},
        {"id": "aprovado", "type": "xor", "name": "Aprovado?", "lane": "financeiro"},
        {"id": "pagar", "type": "serviceTask", "name": "Pagar reembolso", "lane": "financeiro"},
        {"id": "corrigir", "type": "userTask", "name": "Corrigir lançamento", "lane": "colaborador"},
        {"id": "pago", "type": "end", "name": "Reembolso pago", "lane": "financeiro"},
        {"id": "atrasado", "type": "end", "name": "Conferência atrasada", "lane": "financeiro"},
    ],
    "flows": [
        {"from": "despesa", "to": "lancar"},
        {"from": "lancar", "to": "conferir"},
        {"from": "conferir", "to": "aprovado"},
        {"from": "aprovado", "to": "pagar", "label": "Sim", "condition": "comprovantesOk == true"},
        {"from": "aprovado", "to": "corrigir", "label": "Não", "default": True},
        {"from": "pagar", "to": "pago"},
        {"from": "corrigir", "to": "conferir"},
        {"from": "prazo", "to": "atrasado"},
    ],
}


def spec_shape(spec):
    """The process as content, ignoring the internal spec ids (which are keys, not data)."""
    name_of = {node["id"]: node.get("name") for node in spec["nodes"]}
    lane_name_of = {lane["id"]: lane.get("name") for lane in spec.get("lanes", [])}
    return {
        "name": spec.get("name"),
        "executable": bool(spec.get("executable")),
        "lanes": [lane.get("name") for lane in spec.get("lanes", [])],
        "nodes": [
            (
                node.get("type"),
                node.get("name"),
                node.get("event"),
                name_of.get(node.get("attachedTo")),
                lane_name_of.get(node.get("lane")),
            )
            for node in spec["nodes"]
        ],
        "flows": [
            (
                name_of.get(flow["from"]),
                name_of.get(flow["to"]),
                flow.get("label"),
                flow.get("condition"),
                bool(flow.get("default")),
            )
            for flow in spec["flows"]
        ],
    }


def extracted_from_spec(spec):
    return extract_spec(build_tree(spec))


# ---------------------------------------------------------------------------
# Round-trip: nothing about the process is lost
# ---------------------------------------------------------------------------

def test_round_trip_preserves_the_whole_process():
    assert spec_shape(extracted_from_spec(FULL_SPEC)) == spec_shape(FULL_SPEC)


def test_round_trip_is_stable_on_a_second_pass():
    once = extracted_from_spec(FULL_SPEC)
    twice = extracted_from_spec(once)
    assert spec_shape(twice) == spec_shape(once)


def test_rebuilding_an_extracted_spec_reproduces_the_same_element_ids():
    original = build_xml(FULL_SPEC)
    rebuilt = build_xml(extracted_from_spec(FULL_SPEC))
    assert rebuilt == original


def test_extracted_spec_keeps_typed_events_and_the_boundary_host():
    spec = extracted_from_spec(FULL_SPEC)
    by_name = {node.get("name"): node for node in spec["nodes"]}
    assert by_name["Despesa realizada"]["event"] == "message"
    boundary = by_name["Prazo de 5 dias"]
    assert boundary["type"] == "boundary"
    assert boundary["event"] == "timer"
    assert by_name[spec_name_of(spec, boundary["attachedTo"])]["name"] == "Conferir comprovantes"


def spec_name_of(spec, node_id):
    return next(node["name"] for node in spec["nodes"] if node["id"] == node_id)


def test_extracted_spec_keeps_conditions_and_the_default_branch():
    spec = extracted_from_spec(FULL_SPEC)
    conditioned = [f for f in spec["flows"] if f.get("condition")]
    defaults = [f for f in spec["flows"] if f.get("default")]
    assert [f["condition"] for f in conditioned] == ["comprovantesOk == true"]
    assert len(defaults) == 1
    assert defaults[0].get("label") == "Não"
    assert "condition" not in defaults[0]


def test_extracted_spec_keeps_non_interrupting_boundary_events():
    spec = json.loads(json.dumps(FULL_SPEC))
    spec["nodes"][3]["interrupting"] = False
    extracted = extracted_from_spec(spec)
    boundary = [n for n in extracted["nodes"] if n["type"] == "boundary"][0]
    assert boundary["interrupting"] is False


def test_extracted_spec_keeps_lane_membership():
    spec = extracted_from_spec(FULL_SPEC)
    lane_of = {node["name"]: node.get("lane") for node in spec["nodes"]}
    lane_names = {lane["id"]: lane["name"] for lane in spec["lanes"]}
    assert lane_names[lane_of["Lançar despesa"]] == "Colaborador"
    assert lane_names[lane_of["Pagar reembolso"]] == "Financeiro"


def test_a_process_without_lanes_extracts_without_a_lane_key():
    spec = {
        "id": "Process_Simples",
        "nodes": [
            {"id": "a", "type": "start", "name": "Começo"},
            {"id": "b", "type": "end", "name": "Fim"},
        ],
        "flows": [{"from": "a", "to": "b"}],
    }
    extracted = extracted_from_spec(spec)
    assert "lanes" not in extracted
    assert all("lane" not in node for node in extracted["nodes"])


def test_extracted_spec_is_json_serialisable():
    json.dumps(extracted_from_spec(FULL_SPEC), ensure_ascii=False)


def test_every_preferred_alias_the_extractor_emits_is_understood_by_the_builder():
    """
    The extractor writes short aliases ('xor'), the builder resolves them. The
    two tables live in different modules to avoid a circular import, so pin the
    contract between them here: every alias must map back to the tag it came from.
    """
    from bpmn_build import TYPE_ALIASES
    from bpmn_tool import PREFERRED_TYPE_ALIAS

    for tag, alias in PREFERRED_TYPE_ALIAS.items():
        assert alias in TYPE_ALIASES, f"extractor emits '{alias}', which the builder rejects"
        assert TYPE_ALIASES[alias] == tag, f"'{alias}' resolves to {TYPE_ALIASES[alias]}, not {tag}"


# ---------------------------------------------------------------------------
# Extracting real files from disk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "01-user-onboarding",
    "02-credit-card-approval",
    "03-order-fulfillment",
    "04-incident-management",
    "05-document-revision-cycle",
    "06-bus-boarding-process",
])
def test_every_shipped_diagram_can_be_extracted_and_rebuilt_cleanly(name, tmp_path):
    source = TESTS_DIR / f"{name}.bpmn"
    spec = extract_spec(source)

    spec_path = tmp_path / f"{name}-spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    result = run_build(spec_path, tmp_path / f"{name}.bpmn", copy_editor=False)
    assert result.problems == [], f"rebuilt {name} does not lint:\n" + "\n".join(result.problems)

    original_nodes = sum(1 for _ in ET.parse(source).getroot().iter()
                         if _.tag.endswith("}sequenceFlow"))
    rebuilt_nodes = sum(1 for _ in ET.parse(result.output).getroot().iter()
                        if _.tag.endswith("}sequenceFlow"))
    assert rebuilt_nodes == original_nodes, "a sequence flow was lost in the round-trip"


def test_extracting_the_canonical_example_matches_its_spec():
    built = REFERENCES_DIR / "example-complete.bpmn"
    spec = extract_spec(built)
    assert spec["nodes"] and spec["flows"]
    tree = build_tree(spec)
    assert tree.getroot().find("{http://www.omg.org/spec/BPMN/20100524/MODEL}process") is not None


def test_extracting_a_file_without_a_process_is_rejected(tmp_path):
    empty = tmp_path / "vazio.bpmn"
    empty.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_1" />',
        encoding="utf-8",
    )
    with pytest.raises(ExtractError):
        extract_spec(empty)


def test_extracting_an_expanded_subprocess_warns_that_its_content_is_lost(tmp_path, capsys):
    """
    The spec format does not carry the inside of a subprocess. Extracting one
    silently would hand back a spec that rebuilds a smaller process than the
    file on disk -- so it must say so.
    """
    source = tmp_path / "com-subprocesso.bpmn"
    source.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_1">'
        '  <bpmn:process id="Process_1">'
        '    <bpmn:startEvent id="Start_1" name="Começou" />'
        '    <bpmn:subProcess id="SubProcess_Cobranca" name="Cobrança">'
        '      <bpmn:startEvent id="Start_Interno" name="Início interno" />'
        '      <bpmn:endEvent id="End_Interno" name="Fim interno" />'
        '    </bpmn:subProcess>'
        '    <bpmn:endEvent id="End_1" name="Terminou" />'
        '    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="SubProcess_Cobranca" />'
        '    <bpmn:sequenceFlow id="Flow_2" sourceRef="SubProcess_Cobranca" targetRef="End_1" />'
        '  </bpmn:process>'
        '</bpmn:definitions>',
        encoding="utf-8",
    )

    spec = extract_spec(source)

    err = capsys.readouterr().err
    assert "SubProcess_Cobranca" in err
    assert "subprocess" in err.lower()
    assert any(node["id"] == "SubProcess_Cobranca" for node in spec["nodes"])


def test_extracting_a_file_with_several_pools_warns_that_only_one_is_taken(tmp_path, capsys):
    source = tmp_path / "dois-pools.bpmn"
    source.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_1">'
        '  <bpmn:process id="Process_Cliente">'
        '    <bpmn:startEvent id="Start_A" name="Pedido feito" />'
        '  </bpmn:process>'
        '  <bpmn:process id="Process_Fornecedor">'
        '    <bpmn:startEvent id="Start_B" name="Pedido recebido" />'
        '  </bpmn:process>'
        '</bpmn:definitions>',
        encoding="utf-8",
    )

    spec = extract_spec(source)

    err = capsys.readouterr().err
    assert "2 processes" in err
    assert spec["id"] == "Process_Cliente"


def test_a_single_process_file_extracts_without_warnings(capsys):
    extract_spec(TESTS_DIR / "01-user-onboarding.bpmn")
    assert capsys.readouterr().err == ""


def test_extracting_a_malformed_file_is_rejected(tmp_path):
    broken = tmp_path / "quebrado.bpmn"
    broken.write_text("<bpmn:definitions>", encoding="utf-8")
    with pytest.raises(ExtractError):
        extract_spec(broken)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_extract_subcommand_writes_a_spec_file(tmp_path, capsys):
    from bpmn_tool import main as bpmn_tool_main

    source = TESTS_DIR / "01-user-onboarding.bpmn"
    out = tmp_path / "onboarding-spec.json"

    with pytest.raises(SystemExit) as exit_info:
        bpmn_tool_main(["extract", str(source), "-o", str(out)])
    assert exit_info.value.code == 0

    spec = load_spec(out)
    assert spec["nodes"] and spec["flows"]
    assert str(out) in capsys.readouterr().out


def test_extract_subcommand_defaults_to_a_spec_json_next_to_the_diagram(tmp_path):
    from bpmn_tool import main as bpmn_tool_main

    source = tmp_path / "processo.bpmn"
    source.write_text((TESTS_DIR / "01-user-onboarding.bpmn").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        bpmn_tool_main(["extract", str(source)])
    assert exit_info.value.code == 0
    assert (tmp_path / "processo-spec.json").exists()


def test_extract_subcommand_fails_loudly_on_a_broken_file(tmp_path, capsys):
    from bpmn_tool import main as bpmn_tool_main

    broken = tmp_path / "quebrado.bpmn"
    broken.write_text("<bpmn:definitions>", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        bpmn_tool_main(["extract", str(broken)])
    assert exit_info.value.code == 1
