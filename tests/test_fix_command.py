"""
Tests for `bpmn_tool.py fix` -- the mechanical repairs.

The rule this whole subcommand lives by: it repairs what is BOOKKEEPING (the
file disagreeing with itself) and never invents process content. It will not add
an end event, guess a condition, or name an unnamed task -- those are decisions
about the process, and they belong to whoever is modelling it.
"""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import lint_rules
from bpmn_build import run_build
from bpmn_tool import BPMNDI_NS, DI_NS, main as bpmn_tool_main, run_fix

TESTS_DIR = Path(__file__).resolve().parent
REFERENCES_DIR = TESTS_DIR.parent / "references"

SIMPLE_SPEC = {
    "id": "Process_Simples",
    "nodes": [
        {"id": "inicio", "type": "start", "name": "Começou"},
        {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
        {"id": "fim", "type": "end", "name": "Terminou"},
    ],
    "flows": [{"from": "inicio", "to": "fazer"}, {"from": "fazer", "to": "fim"}],
}


def diagram(tmp_path, spec=None, name="processo"):
    spec_path = tmp_path / f"{name}-spec.json"
    spec_path.write_text(json.dumps(spec or SIMPLE_SPEC, ensure_ascii=False), encoding="utf-8")
    return run_build(spec_path, tmp_path / f"{name}.bpmn", copy_editor=False).output


def rules_in(path):
    return {f.rule for f in lint_rules.run_rules(ET.parse(path))}


def edit(path, mutate):
    tree = ET.parse(path)
    mutate(tree.getroot(), tree.getroot()[0])
    tree.write(path, encoding="UTF-8", xml_declaration=True)
    return path


def run_cli(argv):
    with pytest.raises(SystemExit) as exit_info:
        bpmn_tool_main(argv)
    return exit_info.value.code


# ---------------------------------------------------------------------------
# What it repairs
# ---------------------------------------------------------------------------

def test_incoming_and_outgoing_declarations_are_rebuilt_from_the_flows(tmp_path):
    path = diagram(tmp_path)

    def break_refs(_root, process):
        task = [c for c in process if c.tag.endswith("}userTask")][0]
        [c for c in task if c.tag.endswith("}incoming")][0].text = "Flow_Inexistente"

    edit(path, break_refs)
    assert "flow-refs-mismatch" in rules_in(path)

    report = run_fix(path)

    assert "flow-refs-mismatch" not in rules_in(path)
    assert any("flow-refs-mismatch" in change for change in report.changes)


def test_a_missing_outgoing_declaration_is_restored(tmp_path):
    path = diagram(tmp_path)

    def drop_outgoing(_root, process):
        start = [c for c in process if c.tag.endswith("}startEvent")][0]
        start.remove([c for c in start if c.tag.endswith("}outgoing")][0])

    edit(path, drop_outgoing)
    run_fix(path)
    assert "flow-refs-mismatch" not in rules_in(path)


def test_an_exactly_duplicated_flow_is_removed_keeping_the_first(tmp_path):
    spec = json.loads(json.dumps(SIMPLE_SPEC))
    spec["flows"].append({"from": "fazer", "to": "fim"})
    path = diagram(tmp_path, spec)
    assert "duplicate-flow" in rules_in(path)

    run_fix(path)

    assert "duplicate-flow" not in rules_in(path)
    process = ET.parse(path).getroot()[0]
    flows = [c for c in process if c.tag.endswith("}sequenceFlow")]
    assert [f.get("id") for f in flows] == ["Flow_1", "Flow_2"]


def test_a_duplicated_id_is_renamed_and_the_change_is_reported(tmp_path):
    path = diagram(tmp_path)

    def duplicate_id(_root, process):
        end = [c for c in process if c.tag.endswith("}endEvent")][0]
        end.set("id", "Task_FazerAlgo")

    edit(path, duplicate_id)
    assert "duplicate-id" in rules_in(path)

    report = run_fix(path)

    assert "duplicate-id" not in rules_in(path)
    assert any("Task_FazerAlgo" in change for change in report.changes)


def test_a_missing_layout_section_is_recomputed(tmp_path):
    path = diagram(tmp_path)

    def drop_diagram(root, _process):
        root.remove(root.find(f"{{{BPMNDI_NS}}}BPMNDiagram"))

    edit(path, drop_diagram)
    assert "missing-diagram" in rules_in(path)

    run_fix(path)

    fired = rules_in(path)
    assert "missing-diagram" not in fired
    assert "missing-shape" not in fired
    assert "missing-edge" not in fired


def test_a_shape_lost_by_hand_editing_is_recomputed(tmp_path):
    path = diagram(tmp_path)

    def drop_shape(root, _process):
        plane = root.find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
        plane.remove(plane.findall(f"{{{BPMNDI_NS}}}BPMNShape")[0])

    edit(path, drop_shape)
    run_fix(path)
    assert "missing-shape" not in rules_in(path)


def test_a_degenerate_edge_is_recomputed(tmp_path):
    path = diagram(tmp_path)

    def strip_waypoints(root, _process):
        plane = root.find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
        edge = plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge")[0]
        for waypoint in edge.findall(f"{{{DI_NS}}}waypoint")[1:]:
            edge.remove(waypoint)

    edit(path, strip_waypoints)
    run_fix(path)
    assert "edge-waypoints" not in rules_in(path)


# ---------------------------------------------------------------------------
# What it must never do
# ---------------------------------------------------------------------------

def test_two_gateway_branches_to_the_same_task_are_not_a_duplicate(tmp_path):
    """
    Two branches can legitimately reach the same task under different criteria.
    Collapsing them would delete a decision rule of the process -- which is
    exactly what this command promises never to do.
    """
    spec = {
        "id": "Process_DoisCriterios",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Pedido recebido"},
            {"id": "avaliar", "type": "xor", "name": "Precisa de análise?"},
            {"id": "analisar", "type": "userTask", "name": "Analisar manualmente"},
            {"id": "seguir", "type": "serviceTask", "name": "Seguir automaticamente"},
            {"id": "fim", "type": "end", "name": "Pedido tratado"},
        ],
        "flows": [
            {"from": "inicio", "to": "avaliar"},
            {"from": "avaliar", "to": "analisar", "label": "Valor alto", "condition": "valor > 10000"},
            {"from": "avaliar", "to": "analisar", "label": "Cliente novo", "condition": "cliente.novo == true"},
            {"from": "avaliar", "to": "seguir", "label": "Rotina", "default": True},
            {"from": "analisar", "to": "fim"},
            {"from": "seguir", "to": "fim"},
        ],
    }
    path = diagram(tmp_path, spec, name="dois-criterios")
    before = ET.parse(path).getroot()[0]
    conditions_before = len([c for c in before.iter() if c.tag.endswith("}conditionExpression")])

    report = run_fix(path)

    after = ET.parse(path).getroot()[0]
    conditions_after = len([c for c in after.iter() if c.tag.endswith("}conditionExpression")])
    assert conditions_after == conditions_before == 2, "a decision rule was deleted"
    assert not any("duplicate-flow" in change for change in report.changes)
    assert "duplicate-flow" not in rules_in(path), "different criteria are not a duplicate"


def test_a_truly_identical_flow_is_still_removed(tmp_path):
    """Same pair, same label, same condition: the second one adds nothing."""
    spec = {
        "id": "Process_Repetido",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "avaliar", "type": "xor", "name": "Segue?"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
            {"id": "parar", "type": "userTask", "name": "Parar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        "flows": [
            {"from": "inicio", "to": "avaliar"},
            {"from": "avaliar", "to": "fazer", "label": "Sim", "condition": "segue == true"},
            {"from": "avaliar", "to": "fazer", "label": "Sim", "condition": "segue == true"},
            {"from": "avaliar", "to": "parar", "label": "Não", "default": True},
            {"from": "fazer", "to": "fim"},
            {"from": "parar", "to": "fim"},
        ],
    }
    path = diagram(tmp_path, spec, name="repetido")
    assert "duplicate-flow" in rules_in(path)

    run_fix(path)

    assert "duplicate-flow" not in rules_in(path)


def test_removing_a_duplicate_that_was_the_default_branch_keeps_the_gateway_valid(tmp_path):
    """
    Dropping the flow a gateway names as its default would leave the gateway
    pointing at a branch that no longer exists -- `fix` turning a clean file
    into a broken one.
    """
    path = diagram(tmp_path, {
        "id": "Process_DefaultDuplicado",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "avaliar", "type": "xor", "name": "Segue?"},
            {"id": "tratar", "type": "userTask", "name": "Tratar"},
            {"id": "parar", "type": "userTask", "name": "Parar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        "flows": [
            {"from": "inicio", "to": "avaliar"},
            {"from": "avaliar", "to": "parar", "label": "Não", "condition": "segue == false"},
            {"from": "avaliar", "to": "tratar"},
            {"from": "avaliar", "to": "tratar", "default": True},
            {"from": "tratar", "to": "fim"},
            {"from": "parar", "to": "fim"},
        ],
    }, name="default-duplicado")

    process = ET.parse(path).getroot()[0]
    gateway = [c for c in process if c.tag.endswith("}exclusiveGateway")][0]
    assert gateway.get("default") == "Flow_4", "fixture: the default is the duplicated flow"

    report = run_fix(path)

    fixed = ET.parse(path).getroot()[0]
    fixed_gateway = [c for c in fixed if c.tag.endswith("}exclusiveGateway")][0]
    surviving = [c.get("id") for c in fixed if c.tag.endswith("}sequenceFlow")]

    assert fixed_gateway.get("default") in surviving, "the default names a flow that is gone"
    assert "default-flow-invalid" not in rules_in(path)
    assert any("default" in change for change in report.changes), "the move must be reported"


def test_fix_never_invents_an_end_event(tmp_path):
    spec = {
        "id": "Process_SemFim",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
        ],
        "flows": [{"from": "inicio", "to": "fazer"}],
    }
    path = diagram(tmp_path, spec, name="sem-fim")

    run_fix(path)

    process = ET.parse(path).getroot()[0]
    assert not [c for c in process if c.tag.endswith("}endEvent")]
    assert "missing-end-event" in rules_in(path)


def test_fix_never_invents_a_gateway_condition(tmp_path):
    spec = {
        "id": "Process_SemCondicao",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "decidir", "type": "xor", "name": "Aprovado?"},
            {"id": "a", "type": "userTask", "name": "Seguir"},
            {"id": "b", "type": "userTask", "name": "Recusar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        "flows": [
            {"from": "inicio", "to": "decidir"},
            {"from": "decidir", "to": "a", "label": "Sim"},
            {"from": "decidir", "to": "b", "label": "Não"},
            {"from": "a", "to": "fim"},
            {"from": "b", "to": "fim"},
        ],
    }
    path = diagram(tmp_path, spec, name="sem-condicao")

    run_fix(path)

    assert "gateway-without-condition" in rules_in(path), "naming the criterion is a human decision"


def test_fix_never_names_an_unnamed_task(tmp_path):
    spec = json.loads(json.dumps(SIMPLE_SPEC))
    del spec["nodes"][1]["name"]
    path = diagram(tmp_path, spec, name="sem-nome")

    run_fix(path)

    assert "unnamed-element" in rules_in(path)


# ---------------------------------------------------------------------------
# Behaviour of the command itself
# ---------------------------------------------------------------------------

def test_dry_run_reports_the_changes_without_touching_the_file(tmp_path):
    path = diagram(tmp_path)

    def break_refs(_root, process):
        task = [c for c in process if c.tag.endswith("}userTask")][0]
        [c for c in task if c.tag.endswith("}incoming")][0].text = "Flow_Inexistente"

    edit(path, break_refs)
    before = path.read_bytes()

    report = run_fix(path, dry_run=True)

    assert report.changes
    assert path.read_bytes() == before
    assert "flow-refs-mismatch" in rules_in(path)


def test_fixing_a_clean_file_changes_nothing(tmp_path):
    path = diagram(tmp_path)
    before = path.read_bytes()
    report = run_fix(path)
    assert report.changes == []
    assert path.read_bytes() == before


def test_fix_is_idempotent(tmp_path):
    path = diagram(tmp_path)

    def break_refs(_root, process):
        task = [c for c in process if c.tag.endswith("}userTask")][0]
        [c for c in task if c.tag.endswith("}incoming")][0].text = "Flow_Inexistente"

    edit(path, break_refs)
    run_fix(path)
    after_first = path.read_bytes()

    assert run_fix(path).changes == []
    assert path.read_bytes() == after_first


def test_fix_can_write_to_a_different_file(tmp_path):
    path = diagram(tmp_path)

    def break_refs(_root, process):
        task = [c for c in process if c.tag.endswith("}userTask")][0]
        [c for c in task if c.tag.endswith("}incoming")][0].text = "Flow_Inexistente"

    edit(path, break_refs)
    out = tmp_path / "corrigido.bpmn"

    run_fix(path, output_path=out)

    assert "flow-refs-mismatch" in rules_in(path), "the input is left as it was"
    assert "flow-refs-mismatch" not in rules_in(out)


def test_cli_exits_zero_when_nothing_is_left_to_fix(tmp_path, capsys):
    path = diagram(tmp_path)

    def break_refs(_root, process):
        task = [c for c in process if c.tag.endswith("}userTask")][0]
        [c for c in task if c.tag.endswith("}incoming")][0].text = "Flow_Inexistente"

    edit(path, break_refs)
    assert run_cli(["fix", str(path)]) == 0
    assert "flow-refs-mismatch" in capsys.readouterr().out


def test_cli_exits_one_when_errors_remain_for_a_human(tmp_path, capsys):
    spec = {
        "id": "Process_SemFim",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
        ],
        "flows": [{"from": "inicio", "to": "fazer"}],
    }
    path = diagram(tmp_path, spec, name="sem-fim")

    assert run_cli(["fix", str(path)]) == 1
    assert "endEvent" in capsys.readouterr().err


def test_cli_rejects_a_file_that_is_not_well_formed(tmp_path, capsys):
    broken = tmp_path / "quebrado.bpmn"
    broken.write_text("<bpmn:definitions>", encoding="utf-8")
    assert run_cli(["fix", str(broken)]) == 1


def test_fixing_the_canonical_broken_example_leaves_only_human_decisions(tmp_path):
    source = tmp_path / "example-broken.bpmn"
    source.write_text((REFERENCES_DIR / "example-broken.bpmn").read_text(encoding="utf-8"),
                      encoding="utf-8")

    run_fix(source)

    remaining = rules_in(source)
    assert "flow-refs-mismatch" not in remaining, "bookkeeping is repaired"
    assert "dangling-flow-ref" in remaining, "a flow to a node that does not exist needs a human"
