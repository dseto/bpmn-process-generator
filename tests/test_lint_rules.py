"""
Tests for scripts/lint_rules.py -- the rule engine behind `bpmn_tool validate`.

Every check is a named rule with its own severity, so a finding can say WHICH
rule fired and how badly, and so a new check is a new function plus a test
instead of another branch inside one long function.
"""
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import lint_rules
from bpmn_build import build_tree
from bpmn_tool import stage2_lint

TESTS_DIR = Path(__file__).resolve().parent
REFERENCES_DIR = TESTS_DIR.parent / "references"

SHIPPED_DIAGRAMS = [
    "01-user-onboarding",
    "02-credit-card-approval",
    "03-order-fulfillment",
    "04-incident-management",
    "05-document-revision-cycle",
    "06-bus-boarding-process",
]


def tree_from_spec(spec, with_layout=True):
    """A spec built into a tree, laid out like bpmn_build does, ready to lint."""
    from bpmn_tool import BPMN_NS, compute_diagram

    tree = build_tree(spec)
    if with_layout:
        root = tree.getroot()
        for process in root.findall(f"{{{BPMN_NS}}}process"):
            root.append(compute_diagram(process))
    return tree


def linear_spec(**overrides):
    spec = {
        "id": "Process_Linear",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        "flows": [{"from": "inicio", "to": "fazer"}, {"from": "fazer", "to": "fim"}],
    }
    spec.update(overrides)
    return spec


def findings_for(spec, **kwargs):
    return lint_rules.run_rules(tree_from_spec(spec, **kwargs))


def rules_fired(findings):
    return {finding.rule for finding in findings}


# ---------------------------------------------------------------------------
# The engine itself
# ---------------------------------------------------------------------------

def test_a_clean_diagram_produces_no_findings():
    assert findings_for(linear_spec()) == []


def test_every_registered_rule_has_a_unique_id_and_a_known_severity():
    names = [rule.name for rule in lint_rules.RULES]
    assert names, "the engine should ship with rules registered"
    assert len(names) == len(set(names)), "two rules share an id"
    for rule in lint_rules.RULES:
        assert rule.severity in lint_rules.SEVERITIES, f"{rule.name} has severity {rule.severity!r}"


def test_registering_a_rule_with_an_unknown_severity_is_rejected():
    with pytest.raises(ValueError, match="catastrofico"):
        @lint_rules.register("regra-de-teste", "catastrofico")
        def _bad_rule(_document):
            return []


def test_a_finding_carries_rule_severity_element_and_message():
    spec = linear_spec(flows=[{"from": "inicio", "to": "fazer"}])  # 'fazer' is a dead end
    finding = [f for f in findings_for(spec) if f.rule == "dead-end"][0]
    assert finding.severity == "error"
    assert finding.element == "Task_FazerAlgo"
    assert "dead end" in finding.message
    assert finding.fixable is False


def test_a_finding_serialises_to_a_flat_dictionary():
    spec = linear_spec(flows=[{"from": "inicio", "to": "fazer"}])
    payload = [f for f in findings_for(spec) if f.rule == "dead-end"][0].to_dict()
    assert set(payload) == {"rule", "severity", "element", "message", "fixable"}
    assert payload["rule"] == "dead-end"


def test_findings_are_grouped_by_severity_for_callers():
    spec = linear_spec(flows=[{"from": "inicio", "to": "fazer"}])
    findings = findings_for(spec)
    assert lint_rules.errors(findings)
    assert lint_rules.warnings(findings) == [] or all(
        f.severity == "warn" for f in lint_rules.warnings(findings))


def test_process_id_is_part_of_the_message_so_multi_process_files_stay_readable():
    spec = linear_spec(flows=[{"from": "inicio", "to": "fazer"}])
    finding = [f for f in findings_for(spec) if f.rule == "dead-end"][0]
    assert "[Process_Linear]" in finding.message


# ---------------------------------------------------------------------------
# The checks that already existed keep firing, now as named rules
# ---------------------------------------------------------------------------

def test_duplicate_ids_are_reported_as_an_error():
    tree = tree_from_spec(linear_spec())
    process = tree.getroot()[0]
    process[1].set("id", process[0].get("id"))
    findings = lint_rules.run_rules(tree)
    assert "duplicate-id" in rules_fired(findings)


def test_a_file_without_a_layout_section_is_an_error():
    findings = findings_for(linear_spec(), with_layout=False)
    assert "missing-diagram" in rules_fired(findings)


def test_a_node_without_a_shape_is_an_error():
    from bpmn_tool import BPMNDI_NS

    tree = tree_from_spec(linear_spec())
    plane = tree.getroot().find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
    plane.remove(plane.findall(f"{{{BPMNDI_NS}}}BPMNShape")[0])
    assert "missing-shape" in rules_fired(lint_rules.run_rules(tree))


def test_a_flow_without_an_edge_is_an_error():
    from bpmn_tool import BPMNDI_NS

    tree = tree_from_spec(linear_spec())
    plane = tree.getroot().find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
    plane.remove(plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge")[0])
    assert "missing-edge" in rules_fired(lint_rules.run_rules(tree))


def test_an_edge_with_a_single_waypoint_is_an_error():
    from bpmn_tool import BPMNDI_NS, DI_NS

    tree = tree_from_spec(linear_spec())
    plane = tree.getroot().find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
    edge = plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge")[0]
    for waypoint in edge.findall(f"{{{DI_NS}}}waypoint")[1:]:
        edge.remove(waypoint)
    assert "edge-waypoints" in rules_fired(lint_rules.run_rules(tree))


def test_a_process_without_a_start_or_end_event_is_an_error():
    tree = tree_from_spec(linear_spec())
    process = tree.getroot()[0]
    for child in list(process):
        if child.tag.endswith("}startEvent") or child.tag.endswith("}endEvent"):
            process.remove(child)
    fired = rules_fired(lint_rules.run_rules(tree))
    assert {"missing-start-event", "missing-end-event"} <= fired


def test_a_flow_pointing_at_a_node_that_is_not_there_is_an_error():
    tree = tree_from_spec(linear_spec())
    process = tree.getroot()[0]
    flows = [c for c in process if c.tag.endswith("}sequenceFlow")]
    flows[0].set("targetRef", "Task_Fantasma")
    assert "dangling-flow-ref" in rules_fired(lint_rules.run_rules(tree))


def test_a_node_with_no_incoming_flow_is_an_error():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
            {"id": "orfao", "type": "userTask", "name": "Tarefa órfã"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[
            {"from": "inicio", "to": "fazer"},
            {"from": "fazer", "to": "fim"},
            {"from": "orfao", "to": "fim"},
        ],
    )
    fired = rules_fired(findings_for(spec))
    assert "unreachable-node" in fired
    assert "not-reachable-from-start" in fired


def test_a_parallel_split_with_no_join_downstream_is_a_warning():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "dividir", "type": "and", "name": "Dividir"},
            {"id": "a", "type": "userTask", "name": "Ramo A"},
            {"id": "b", "type": "userTask", "name": "Ramo B"},
            {"id": "fim_a", "type": "end", "name": "Fim A"},
            {"id": "fim_b", "type": "end", "name": "Fim B"},
        ],
        flows=[
            {"from": "inicio", "to": "dividir"},
            {"from": "dividir", "to": "a"},
            {"from": "dividir", "to": "b"},
            {"from": "a", "to": "fim_a"},
            {"from": "b", "to": "fim_b"},
        ],
    )
    finding = [f for f in findings_for(spec) if f.rule == "parallel-split-without-join"][0]
    assert finding.severity == "warn"


# ---------------------------------------------------------------------------
# The old entry point keeps behaving exactly the same
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", SHIPPED_DIAGRAMS)
def test_shipped_diagrams_still_pass_stage2_lint(name):
    problems, _warnings = stage2_lint(ET.parse(TESTS_DIR / f"{name}.bpmn"))
    assert problems == []


def test_stage2_lint_returns_error_messages_as_problems_and_warn_as_warnings():
    spec = linear_spec(flows=[{"from": "inicio", "to": "fazer"}])
    tree = tree_from_spec(spec)
    problems, warnings = stage2_lint(tree)
    findings = lint_rules.run_rules(tree)

    assert problems == [f.message for f in findings if f.severity == "error"]
    assert warnings == [f.message for f in findings if f.severity == "warn"]


def test_the_canonical_broken_example_is_still_rejected():
    problems, _warnings = stage2_lint(ET.parse(REFERENCES_DIR / "example-broken.bpmn"))
    assert problems, "references/example-broken.bpmn exists precisely to fail the linter"


def test_the_canonical_complete_example_is_still_accepted():
    problems, _warnings = stage2_lint(ET.parse(REFERENCES_DIR / "example-complete.bpmn"))
    assert problems == []


# ---------------------------------------------------------------------------
# New structural errors: what a hand-written diagram gets wrong silently
# ---------------------------------------------------------------------------

def test_declared_incoming_flows_that_disagree_with_the_real_ones_are_an_error():
    """
    The bug class this whole rule engine exists for: a hand-written file where
    <bpmn:incoming>/<bpmn:outgoing> no longer match the sequenceFlows. Nothing
    in the file complains, and tools disagree about what the process is.
    """
    tree = tree_from_spec(linear_spec())
    process = tree.getroot()[0]
    task = [c for c in process if c.tag.endswith("}userTask")][0]
    incoming = [c for c in task if c.tag.endswith("}incoming")][0]
    incoming.text = "Flow_Inexistente"

    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "flow-refs-mismatch"][0]
    assert finding.severity == "error"
    assert finding.element == "Task_FazerAlgo"
    assert finding.fixable is True, "rebuilding incoming/outgoing is mechanical"


def test_a_missing_outgoing_declaration_is_also_a_mismatch():
    tree = tree_from_spec(linear_spec())
    process = tree.getroot()[0]
    start = [c for c in process if c.tag.endswith("}startEvent")][0]
    start.remove([c for c in start if c.tag.endswith("}outgoing")][0])
    assert "flow-refs-mismatch" in rules_fired(lint_rules.run_rules(tree))


def test_a_clean_generated_file_never_has_a_refs_mismatch():
    assert "flow-refs-mismatch" not in rules_fired(findings_for(linear_spec()))


def test_a_start_event_with_an_incoming_flow_is_an_error():
    spec = linear_spec(flows=[
        {"from": "inicio", "to": "fazer"},
        {"from": "fazer", "to": "fim"},
        {"from": "fazer", "to": "inicio"},
    ])
    finding = [f for f in findings_for(spec) if f.rule == "start-has-incoming"][0]
    assert finding.element == "Start_Comecou"


def test_an_end_event_with_an_outgoing_flow_is_an_error():
    spec = linear_spec(flows=[
        {"from": "inicio", "to": "fazer"},
        {"from": "fazer", "to": "fim"},
        {"from": "fim", "to": "fazer"},
    ])
    assert "end-has-outgoing" in rules_fired(findings_for(spec))


def test_a_default_flow_that_does_not_leave_the_gateway_is_an_error():
    tree = tree_from_spec(gateway_spec())
    process = tree.getroot()[0]
    gateway = [c for c in process if c.tag.endswith("}exclusiveGateway")][0]
    gateway.set("default", "Flow_Inexistente")

    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "default-flow-invalid"][0]
    assert finding.element == gateway.get("id")


def test_a_valid_default_flow_raises_nothing():
    assert "default-flow-invalid" not in rules_fired(findings_for(gateway_spec()))


def gateway_spec():
    return {
        "id": "Process_Decisao",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "decidir", "type": "xor", "name": "Aprovado?"},
            {"id": "sim", "type": "userTask", "name": "Seguir"},
            {"id": "nao", "type": "userTask", "name": "Recusar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        "flows": [
            {"from": "inicio", "to": "decidir"},
            {"from": "decidir", "to": "sim", "label": "Sim", "condition": "ok == true"},
            {"from": "decidir", "to": "nao", "label": "Não", "default": True},
            {"from": "sim", "to": "fim"},
            {"from": "nao", "to": "fim"},
        ],
    }


def test_a_boundary_event_without_a_host_is_an_error():
    tree = tree_from_spec(boundary_spec())
    process = tree.getroot()[0]
    boundary = [c for c in process if c.tag.endswith("}boundaryEvent")][0]
    del boundary.attrib["attachedToRef"]
    assert "boundary-invalid" in rules_fired(lint_rules.run_rules(tree))


def test_a_boundary_event_attached_to_a_gateway_is_an_error():
    tree = tree_from_spec(boundary_spec())
    process = tree.getroot()[0]
    boundary = [c for c in process if c.tag.endswith("}boundaryEvent")][0]
    boundary.set("attachedToRef", "Start_Comecou")
    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "boundary-invalid"][0]
    assert "Start_Comecou" in finding.message


def boundary_spec():
    return {
        "id": "Process_ComPrazo",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
            {"id": "prazo", "type": "boundary", "name": "Prazo", "event": "timer", "attachedTo": "fazer"},
            {"id": "fim", "type": "end", "name": "Terminou"},
            {"id": "fim_prazo", "type": "end", "name": "Atrasou"},
        ],
        "flows": [
            {"from": "inicio", "to": "fazer"},
            {"from": "fazer", "to": "fim"},
            {"from": "prazo", "to": "fim_prazo"},
        ],
    }


def test_a_loop_that_can_never_reach_an_end_event_is_an_error():
    """
    Every node has an outgoing flow, so `dead-end` says nothing -- but the
    process can never finish. Only walking backwards from the end events finds it.
    """
    spec = {
        "id": "Process_Preso",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "a", "type": "userTask", "name": "Tarefa A"},
            {"id": "b", "type": "userTask", "name": "Tarefa B"},
            {"id": "fim", "type": "end", "name": "Terminou"},
            {"id": "solto", "type": "userTask", "name": "Caminho que termina"},
        ],
        "flows": [
            {"from": "inicio", "to": "a"},
            {"from": "a", "to": "b"},
            {"from": "b", "to": "a"},
            {"from": "inicio", "to": "solto"},
            {"from": "solto", "to": "fim"},
        ],
    }
    stuck = {f.element for f in findings_for(spec) if f.rule == "no-path-to-end"}
    assert {"Task_TarefaA", "Task_TarefaB"} <= stuck
    assert "Task_CaminhoQueTermina" not in stuck


def test_a_rework_loop_that_can_still_finish_is_not_reported():
    spec = {
        "id": "Process_Retrabalho",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "revisar", "type": "userTask", "name": "Revisar"},
            {"id": "ok", "type": "xor", "name": "Aprovado?"},
            {"id": "corrigir", "type": "userTask", "name": "Corrigir"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        "flows": [
            {"from": "inicio", "to": "revisar"},
            {"from": "revisar", "to": "ok"},
            {"from": "ok", "to": "fim", "label": "Sim", "condition": "ok == true"},
            {"from": "ok", "to": "corrigir", "label": "Não", "default": True},
            {"from": "corrigir", "to": "revisar"},
        ],
    }
    assert "no-path-to-end" not in rules_fired(findings_for(spec))


def test_a_node_listed_in_two_lanes_is_an_error():
    spec = {
        "id": "Process_ComRaias",
        "lanes": [{"id": "a", "name": "Setor A"}, {"id": "b", "name": "Setor B"}],
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou", "lane": "a"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo", "lane": "b"},
            {"id": "fim", "type": "end", "name": "Terminou", "lane": "b"},
        ],
        "flows": [{"from": "inicio", "to": "fazer"}, {"from": "fazer", "to": "fim"}],
    }
    tree = tree_from_spec(spec)
    process = tree.getroot()[0]
    lanes = [c for c in process[0] if c.tag.endswith("}lane")]
    duplicated = ET.SubElement(lanes[0], f"{{{lint_rules_bpmn_ns()}}}flowNodeRef")
    duplicated.text = "Task_FazerAlgo"

    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "lane-coverage-duplicate"][0]
    assert finding.element == "Task_FazerAlgo"


def lint_rules_bpmn_ns():
    from bpmn_tool import BPMN_NS

    return BPMN_NS


def test_lanes_that_cover_every_node_once_raise_nothing():
    spec = {
        "id": "Process_RaiasOk",
        "lanes": [{"id": "a", "name": "Setor A"}],
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou", "lane": "a"},
            {"id": "fim", "type": "end", "name": "Terminou", "lane": "a"},
        ],
        "flows": [{"from": "inicio", "to": "fim"}],
    }
    assert "lane-coverage-duplicate" not in rules_fired(findings_for(spec))


# ---------------------------------------------------------------------------
# Modelling-quality warnings: the diagram opens, but a reader will misread it
# ---------------------------------------------------------------------------

def severities_of(spec, rule):
    return {f.severity for f in findings_for(spec) if f.rule == rule}


def test_a_task_with_two_outgoing_flows_warns_about_an_implicit_split():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo"},
            {"id": "fim_a", "type": "end", "name": "Fim A"},
            {"id": "fim_b", "type": "end", "name": "Fim B"},
        ],
        flows=[
            {"from": "inicio", "to": "fazer"},
            {"from": "fazer", "to": "fim_a"},
            {"from": "fazer", "to": "fim_b"},
        ],
    )
    finding = [f for f in findings_for(spec) if f.rule == "implicit-split"][0]
    assert finding.severity == "warn"
    assert finding.element == "Task_FazerAlgo"


def test_a_task_receiving_two_flows_warns_about_an_implicit_merge():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "decidir", "type": "xor", "name": "Qual caminho?"},
            {"id": "a", "type": "userTask", "name": "Caminho A"},
            {"id": "b", "type": "userTask", "name": "Caminho B"},
            {"id": "juntar", "type": "userTask", "name": "Consolidar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[
            {"from": "inicio", "to": "decidir"},
            {"from": "decidir", "to": "a", "label": "A", "condition": "via == 'a'"},
            {"from": "decidir", "to": "b", "label": "B", "default": True},
            {"from": "a", "to": "juntar"},
            {"from": "b", "to": "juntar"},
            {"from": "juntar", "to": "fim"},
        ],
    )
    assert severities_of(spec, "implicit-merge") == {"warn"}


def test_a_gateway_split_without_conditions_is_a_warning():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "decidir", "type": "xor", "name": "Aprovado?"},
            {"id": "a", "type": "userTask", "name": "Seguir"},
            {"id": "b", "type": "userTask", "name": "Recusar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[
            {"from": "inicio", "to": "decidir"},
            {"from": "decidir", "to": "a", "label": "Sim"},
            {"from": "decidir", "to": "b", "label": "Não"},
            {"from": "a", "to": "fim"},
            {"from": "b", "to": "fim"},
        ],
    )
    finding = [f for f in findings_for(spec) if f.rule == "gateway-without-condition"][0]
    assert finding.severity == "warn"
    assert finding.element == "Gateway_Aprovado"


def test_a_gateway_split_with_a_condition_and_a_default_is_clean():
    assert "gateway-without-condition" not in rules_fired(findings_for(gateway_spec()))


def test_a_parallel_gateway_split_needs_no_conditions():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "dividir", "type": "and", "name": "Dividir"},
            {"id": "a", "type": "userTask", "name": "Ramo A"},
            {"id": "b", "type": "userTask", "name": "Ramo B"},
            {"id": "juntar", "type": "and", "name": "Juntar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[
            {"from": "inicio", "to": "dividir"},
            {"from": "dividir", "to": "a"},
            {"from": "dividir", "to": "b"},
            {"from": "a", "to": "juntar"},
            {"from": "b", "to": "juntar"},
            {"from": "juntar", "to": "fim"},
        ],
    )
    fired = rules_fired(findings_for(spec))
    assert "gateway-without-condition" not in fired
    assert "parallel-split-without-join" not in fired
    assert "parallel-join-without-split" not in fired


def test_a_parallel_join_with_no_split_upstream_is_a_warning():
    spec = linear_spec(
        nodes=[
            {"id": "inicio_a", "type": "start", "name": "Gatilho A"},
            {"id": "inicio_b", "type": "start", "name": "Gatilho B"},
            {"id": "juntar", "type": "and", "name": "Juntar"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[
            {"from": "inicio_a", "to": "juntar"},
            {"from": "inicio_b", "to": "juntar"},
            {"from": "juntar", "to": "fim"},
        ],
    )
    assert severities_of(spec, "parallel-join-without-split") == {"warn"}


def test_a_gateway_that_neither_splits_nor_merges_is_an_info():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "inutil", "type": "xor", "name": "Passagem"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[{"from": "inicio", "to": "inutil"}, {"from": "inutil", "to": "fim"}],
    )
    finding = [f for f in findings_for(spec) if f.rule == "useless-gateway"][0]
    assert finding.severity == "info"


def test_a_gateway_that_both_splits_and_merges_is_a_warning():
    spec = linear_spec(
        nodes=[
            {"id": "inicio_a", "type": "start", "name": "Gatilho A"},
            {"id": "inicio_b", "type": "start", "name": "Gatilho B"},
            {"id": "misto", "type": "xor", "name": "Misto?"},
            {"id": "fim_a", "type": "end", "name": "Fim A"},
            {"id": "fim_b", "type": "end", "name": "Fim B"},
        ],
        flows=[
            {"from": "inicio_a", "to": "misto"},
            {"from": "inicio_b", "to": "misto"},
            {"from": "misto", "to": "fim_a", "label": "A", "condition": "x == 1"},
            {"from": "misto", "to": "fim_b", "label": "B", "default": True},
        ],
    )
    assert severities_of(spec, "mixed-gateway") == {"warn"}


def test_an_unnamed_task_or_gateway_is_a_warning():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "sem_nome", "type": "userTask"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ],
        flows=[{"from": "inicio", "to": "sem_nome"}, {"from": "sem_nome", "to": "fim"}],
    )
    finding = [f for f in findings_for(spec) if f.rule == "unnamed-element"][0]
    assert finding.severity == "warn"
    assert finding.element == "Task_SemNome"


def test_two_flows_between_the_same_pair_of_nodes_is_a_warning():
    spec = linear_spec(flows=[
        {"from": "inicio", "to": "fazer"},
        {"from": "fazer", "to": "fim"},
        {"from": "fazer", "to": "fim"},
    ])
    assert severities_of(spec, "duplicate-flow") == {"warn"}


def test_a_flow_from_a_node_to_itself_is_a_warning():
    spec = linear_spec(flows=[
        {"from": "inicio", "to": "fazer"},
        {"from": "fazer", "to": "fazer"},
        {"from": "fazer", "to": "fim"},
    ])
    assert severities_of(spec, "self-loop") == {"warn"}


def test_a_node_missing_from_every_lane_is_a_warning():
    spec = {
        "id": "Process_RaiaIncompleta",
        "lanes": [{"id": "a", "name": "Setor A"}],
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou", "lane": "a"},
            {"id": "fazer", "type": "userTask", "name": "Fazer algo", "lane": "a"},
            {"id": "fim", "type": "end", "name": "Terminou", "lane": "a"},
        ],
        "flows": [{"from": "inicio", "to": "fazer"}, {"from": "fazer", "to": "fim"}],
    }
    tree = tree_from_spec(spec)
    lane = tree.getroot()[0][0][0]
    lane.remove([ref for ref in lane if ref.text == "Task_FazerAlgo"][0])

    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "lane-coverage-missing"][0]
    assert finding.severity == "warn"
    assert finding.element == "Task_FazerAlgo"


def test_overlapping_shapes_are_a_warning():
    tree = tree_from_spec(linear_spec())
    from bpmn_tool import BPMNDI_NS, DC_NS

    plane = tree.getroot().find(f"{{{BPMNDI_NS}}}BPMNDiagram/{{{BPMNDI_NS}}}BPMNPlane")
    shapes = plane.findall(f"{{{BPMNDI_NS}}}BPMNShape")
    first_bounds = shapes[0].find(f"{{{DC_NS}}}Bounds")
    second_bounds = shapes[1].find(f"{{{DC_NS}}}Bounds")
    for attr in ("x", "y"):
        second_bounds.set(attr, first_bounds.get(attr))

    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "di-overlap"][0]
    assert finding.severity == "warn"


def test_lane_bands_do_not_count_as_overlapping_shapes():
    """A lane band legitimately contains every node it owns -- not an overlap."""
    spec = {
        "id": "Process_ComRaia",
        "lanes": [{"id": "a", "name": "Setor A"}],
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Começou", "lane": "a"},
            {"id": "fim", "type": "end", "name": "Terminou", "lane": "a"},
        ],
        "flows": [{"from": "inicio", "to": "fim"}],
    }
    assert "di-overlap" not in rules_fired(findings_for(spec))


def test_an_id_off_the_naming_convention_is_an_info():
    tree = tree_from_spec(linear_spec())
    process = tree.getroot()[0]
    task = [c for c in process if c.tag.endswith("}userTask")][0]
    task.set("id", "abc123")
    for flow in [c for c in process if c.tag.endswith("}sequenceFlow")]:
        if flow.get("sourceRef") == "Task_FazerAlgo":
            flow.set("sourceRef", "abc123")
        if flow.get("targetRef") == "Task_FazerAlgo":
            flow.set("targetRef", "abc123")

    finding = [f for f in lint_rules.run_rules(tree) if f.rule == "id-convention"][0]
    assert finding.severity == "info"
    assert finding.element == "abc123"


def test_a_very_long_name_is_an_info():
    spec = linear_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Começou"},
            {"id": "fazer", "type": "userTask",
             "name": "Executar o procedimento completo de conferência documental "
                     "e cadastral de todos os fornecedores homologados"},
            {"id": "fim", "type": "end", "name": "Terminou"},
        ]
    )
    assert severities_of(spec, "name-too-long") == {"info"}


def test_warnings_and_infos_never_become_problems():
    spec = linear_spec(flows=[
        {"from": "inicio", "to": "fazer"},
        {"from": "fazer", "to": "fim"},
        {"from": "fazer", "to": "fim"},
    ])
    tree = tree_from_spec(spec)
    problems, warns = stage2_lint(tree)
    assert problems == []
    assert warns, "a duplicate flow should still be reported as a warning"


def test_the_broken_example_now_exercises_the_new_error_rules():
    findings = lint_rules.run_rules(ET.parse(REFERENCES_DIR / "example-broken.bpmn"))
    fired = rules_fired(findings)
    expected = {
        "dangling-flow-ref",
        "flow-refs-mismatch",
        "start-has-incoming",
        "end-has-outgoing",
        "default-flow-invalid",
        "boundary-invalid",
        "lane-coverage-duplicate",
    }
    assert expected <= fired, f"missing from the canonical broken example: {sorted(expected - fired)}"
    assert all(f.severity in lint_rules.SEVERITIES for f in findings)
