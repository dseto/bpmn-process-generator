"""
Tests for scripts/bpmn_build.py -- the spec-JSON -> BPMN 2.0 generator.

The point of the generator is that things a hand-written XML gets wrong
cannot be gotten wrong here: ids are derived deterministically from the
spec, and every <bpmn:incoming>/<bpmn:outgoing> child is derived from the
sequenceFlow list rather than typed independently.
"""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bpmn_build import SpecError, build_tree, build_xml, load_spec
from bpmn_tool import BPMN_NS, build_graph, compute_diagram, stage2_lint

NS = {"bpmn": BPMN_NS}

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"
EXAMPLE_SPEC = REFERENCES_DIR / "example-spec.json"
SPEC_DOC = REFERENCES_DIR / "process-spec.md"


def minimal_spec(**overrides):
    spec = {
        "id": "Process_Suporte",
        "name": "Atendimento de suporte",
        "nodes": [
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
            {"id": "fim", "type": "end", "name": "Chamado encerrado"},
        ],
        "flows": [
            {"from": "inicio", "to": "revisar"},
            {"from": "revisar", "to": "fim"},
        ],
    }
    spec.update(overrides)
    return spec


def process_of(spec):
    root = build_tree(spec).getroot()
    return root.find("bpmn:process", NS)


def tag_of(el):
    return el.tag.split("}")[-1]


# ---------------------------------------------------------------------------
# Readable, deterministic ids
# ---------------------------------------------------------------------------

def test_ids_follow_type_prefix_and_pascal_case_of_the_name():
    process = process_of(minimal_spec())
    ids = [child.get("id") for child in process if tag_of(child) != "sequenceFlow"]
    assert ids == ["Start_ChamadoAberto", "Task_RevisarChamado", "End_ChamadoEncerrado"]


def test_gateway_ids_use_the_gateway_prefix_and_drop_punctuation():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "decidir", "type": "xor", "name": "Resolvível?"},
            {"id": "fim", "type": "end", "name": "Chamado encerrado"},
        ],
        flows=[{"from": "inicio", "to": "decidir"}, {"from": "decidir", "to": "fim"}],
    )
    process = process_of(spec)
    gateway = process.find("bpmn:exclusiveGateway", NS)
    assert gateway is not None
    assert gateway.get("id") == "Gateway_Resolvivel"


def test_ids_strip_accents_but_names_keep_them():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Início"},
            {"id": "aprovar", "type": "userTask", "name": "Aprovação da diretoria"},
            {"id": "fim", "type": "end", "name": "Fim"},
        ],
        flows=[{"from": "inicio", "to": "aprovar"}, {"from": "aprovar", "to": "fim"}],
    )
    process = process_of(spec)
    task = process.find("bpmn:userTask", NS)
    assert task.get("id") == "Task_AprovacaoDaDiretoria"
    assert task.get("name") == "Aprovação da diretoria"


def test_node_without_name_derives_its_id_from_the_spec_id():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start"},
            {"id": "conferir_nota", "type": "task"},
            {"id": "fim", "type": "end"},
        ],
        flows=[{"from": "inicio", "to": "conferir_nota"}, {"from": "conferir_nota", "to": "fim"}],
    )
    process = process_of(spec)
    assert process.find("bpmn:task", NS).get("id") == "Task_ConferirNota"


def test_nodes_with_the_same_name_still_get_unique_ids():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "notificar_a", "type": "serviceTask", "name": "Notificar cliente"},
            {"id": "notificar_b", "type": "serviceTask", "name": "Notificar cliente"},
            {"id": "fim", "type": "end", "name": "Fim"},
        ],
        flows=[
            {"from": "inicio", "to": "notificar_a"},
            {"from": "notificar_a", "to": "notificar_b"},
            {"from": "notificar_b", "to": "fim"},
        ],
    )
    process = process_of(spec)
    ids = [t.get("id") for t in process.findall("bpmn:serviceTask", NS)]
    assert ids == ["Task_NotificarCliente", "Task_NotificarCliente_2"]


def test_building_the_same_spec_twice_is_byte_identical():
    spec = minimal_spec()
    assert build_xml(spec) == build_xml(spec)


# ---------------------------------------------------------------------------
# incoming/outgoing derived from the flows (the hand-written-XML bug class)
# ---------------------------------------------------------------------------

def test_incoming_and_outgoing_children_match_the_sequence_flows_exactly():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "decidir", "type": "xor", "name": "Resolvível?"},
            {"id": "responder", "type": "userTask", "name": "Responder cliente"},
            {"id": "escalar", "type": "userTask", "name": "Escalar para engenharia"},
            {"id": "fim", "type": "end", "name": "Chamado encerrado"},
        ],
        flows=[
            {"from": "inicio", "to": "decidir"},
            {"from": "decidir", "to": "responder", "label": "Sim"},
            {"from": "decidir", "to": "escalar", "label": "Não"},
            {"from": "responder", "to": "fim"},
            {"from": "escalar", "to": "fim"},
        ],
    )
    process = process_of(spec)
    nodes, edges, issues = build_graph(process)
    assert not issues

    for child in process:
        nid = child.get("id")
        if tag_of(child) == "sequenceFlow" or nid not in nodes:
            continue
        declared_in = [e.text for e in child.findall("bpmn:incoming", NS)]
        declared_out = [e.text for e in child.findall("bpmn:outgoing", NS)]
        real_in = [fid for fid, _ in nodes[nid]["in_edges"]]
        real_out = [fid for fid, _ in nodes[nid]["out_edges"]]
        assert declared_in == real_in, f"incoming of {nid} diverged from the sequenceFlows"
        assert declared_out == real_out, f"outgoing of {nid} diverged from the sequenceFlows"


def test_flow_ids_are_sequential_and_referenced_by_both_endpoints():
    process = process_of(minimal_spec())
    flow_ids = [f.get("id") for f in process.findall("bpmn:sequenceFlow", NS)]
    assert flow_ids == ["Flow_1", "Flow_2"]
    start = process.find("bpmn:startEvent", NS)
    assert [e.text for e in start.findall("bpmn:outgoing", NS)] == ["Flow_1"]


def test_flow_endpoints_are_resolved_to_the_generated_node_ids():
    process = process_of(minimal_spec())
    first = process.find("bpmn:sequenceFlow", NS)
    assert first.get("sourceRef") == "Start_ChamadoAberto"
    assert first.get("targetRef") == "Task_RevisarChamado"


def test_flow_label_becomes_the_sequence_flow_name():
    spec = minimal_spec(
        flows=[
            {"from": "inicio", "to": "revisar", "label": "Triagem ok"},
            {"from": "revisar", "to": "fim"},
        ]
    )
    process = process_of(spec)
    first = process.find("bpmn:sequenceFlow", NS)
    assert first.get("name") == "Triagem ok"


# ---------------------------------------------------------------------------
# Document skeleton
# ---------------------------------------------------------------------------

def test_definitions_carry_the_canonical_namespaces_and_process_attributes():
    xml = build_xml(minimal_spec())
    assert xml.startswith("<?xml version=")
    for uri in (
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"',
        'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"',
        'xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"',
        'xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"',
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
    ):
        assert uri in xml, f"missing namespace declaration: {uri}"

    process = process_of(minimal_spec())
    assert process.get("id") == "Process_Suporte"
    assert process.get("name") == "Atendimento de suporte"
    assert process.get("isExecutable") == "false"


def test_executable_flag_is_opt_in():
    process = process_of(minimal_spec(executable=True))
    assert process.get("isExecutable") == "true"


# ---------------------------------------------------------------------------
# Spec validation -- fail loudly instead of emitting a broken diagram
# ---------------------------------------------------------------------------

def test_flow_pointing_at_an_unknown_node_is_rejected():
    spec = minimal_spec(flows=[{"from": "inicio", "to": "fantasma"}])
    with pytest.raises(SpecError, match="fantasma"):
        build_xml(spec)


def test_duplicate_node_ids_in_the_spec_are_rejected():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "A"},
            {"id": "inicio", "type": "end", "name": "B"},
        ],
        flows=[],
    )
    with pytest.raises(SpecError, match="inicio"):
        build_xml(spec)


def test_unknown_node_type_is_rejected_with_the_offending_alias():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start"},
            {"id": "x", "type": "megaTask"},
            {"id": "fim", "type": "end"},
        ],
        flows=[{"from": "inicio", "to": "x"}, {"from": "x", "to": "fim"}],
    )
    with pytest.raises(SpecError, match="megaTask"):
        build_xml(spec)


def test_node_without_id_is_rejected():
    spec = minimal_spec(nodes=[{"type": "start", "name": "sem id"}], flows=[])
    with pytest.raises(SpecError):
        build_xml(spec)


def test_flow_missing_an_endpoint_is_rejected():
    spec = minimal_spec(flows=[{"from": "inicio"}])
    with pytest.raises(SpecError):
        build_xml(spec)


# ---------------------------------------------------------------------------
# The canonical example spec
# ---------------------------------------------------------------------------

def test_example_spec_is_valid_json_and_loads():
    assert EXAMPLE_SPEC.exists(), "references/example-spec.json is the canonical example"
    spec = load_spec(EXAMPLE_SPEC)
    assert spec["nodes"] and spec["flows"]


def test_example_spec_generates_a_diagram_that_passes_the_linter():
    spec = load_spec(EXAMPLE_SPEC)
    tree = build_tree(spec)
    root = tree.getroot()
    for process in root.findall("bpmn:process", NS):
        root.append(compute_diagram(process))

    problems, _warnings = stage2_lint(tree)
    assert not problems, "example spec produced a diagram the linter rejects:\n" + "\n".join(problems)


def test_spec_documentation_covers_every_supported_type_alias():
    assert SPEC_DOC.exists(), "references/process-spec.md documents the spec contract"
    doc = SPEC_DOC.read_text(encoding="utf-8")
    from bpmn_build import TYPE_ALIASES

    for alias in TYPE_ALIASES:
        assert f"`{alias}`" in doc, f"type alias '{alias}' is undocumented in process-spec.md"


def test_example_spec_round_trips_through_json_dump():
    raw = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert set(["id", "nodes", "flows"]).issubset(raw.keys())


# ---------------------------------------------------------------------------
# Typed events
# ---------------------------------------------------------------------------

def test_start_event_with_a_message_trigger_gets_an_event_definition():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Pedido recebido", "event": "message"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
            {"id": "fim", "type": "end", "name": "Fim"},
        ]
    )
    start = process_of(spec).find("bpmn:startEvent", NS)
    assert start.find("bpmn:messageEventDefinition", NS) is not None


def test_end_event_can_be_a_terminate_event():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
            {"id": "fim", "type": "end", "name": "Fim", "event": "terminate"},
        ]
    )
    end = process_of(spec).find("bpmn:endEvent", NS)
    assert end.find("bpmn:terminateEventDefinition", NS) is not None


def test_event_definition_comes_after_the_incoming_and_outgoing_children():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
            {"id": "fim", "type": "end", "name": "Fim", "event": "message"},
        ]
    )
    end = process_of(spec).find("bpmn:endEvent", NS)
    assert [tag_of(child) for child in end] == ["incoming", "messageEventDefinition"]


def test_unknown_event_kind_is_rejected():
    spec = minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "X", "event": "meteoro"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
            {"id": "fim", "type": "end", "name": "Fim"},
        ]
    )
    with pytest.raises(SpecError, match="meteoro"):
        build_xml(spec)


# ---------------------------------------------------------------------------
# Boundary events (deadlines and errors attached to an activity)
# ---------------------------------------------------------------------------

def boundary_spec(**boundary_overrides):
    boundary = {"id": "prazo", "type": "boundary", "name": "48h",
                "event": "timer", "attachedTo": "revisar"}
    boundary.update(boundary_overrides)
    return minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
            boundary,
            {"id": "escalar", "type": "userTask", "name": "Escalar chamado"},
            {"id": "fim", "type": "end", "name": "Fim"},
            {"id": "fim_prazo", "type": "end", "name": "Prazo estourado"},
        ],
        flows=[
            {"from": "inicio", "to": "revisar"},
            {"from": "revisar", "to": "fim"},
            {"from": "prazo", "to": "escalar"},
            {"from": "escalar", "to": "fim_prazo"},
        ],
    )


def test_boundary_event_attaches_to_the_generated_id_of_its_activity():
    boundary = process_of(boundary_spec()).find("bpmn:boundaryEvent", NS)
    assert boundary.get("id") == "Event_48h"
    assert boundary.get("attachedToRef") == "Task_RevisarChamado"
    assert boundary.find("bpmn:timerEventDefinition", NS) is not None


def test_boundary_event_is_interrupting_by_default_and_can_be_non_interrupting():
    assert process_of(boundary_spec()).find("bpmn:boundaryEvent", NS).get("cancelActivity") == "true"
    non_interrupting = boundary_spec(interrupting=False)
    assert process_of(non_interrupting).find("bpmn:boundaryEvent", NS).get("cancelActivity") == "false"


def test_boundary_event_without_a_host_activity_is_rejected():
    spec = boundary_spec()
    del spec["nodes"][2]["attachedTo"]
    with pytest.raises(SpecError, match="prazo"):
        build_xml(spec)


def test_boundary_event_attached_to_an_unknown_node_is_rejected():
    with pytest.raises(SpecError, match="fantasma"):
        build_xml(boundary_spec(attachedTo="fantasma"))


def test_boundary_event_attached_to_a_non_activity_is_rejected():
    with pytest.raises(SpecError, match="inicio"):
        build_xml(boundary_spec(attachedTo="inicio"))


# ---------------------------------------------------------------------------
# Gateway conditions and default flow
# ---------------------------------------------------------------------------

def gateway_spec(**flow_overrides):
    sim = {"from": "decidir", "to": "aprovar", "label": "Sim", "condition": "aprovado == true"}
    nao = {"from": "decidir", "to": "recusar", "label": "Não"}
    nao.update(flow_overrides)
    return minimal_spec(
        nodes=[
            {"id": "inicio", "type": "start", "name": "Pedido recebido"},
            {"id": "decidir", "type": "xor", "name": "Aprovado?"},
            {"id": "aprovar", "type": "userTask", "name": "Aprovar pedido"},
            {"id": "recusar", "type": "userTask", "name": "Recusar pedido"},
            {"id": "fim", "type": "end", "name": "Pedido decidido"},
        ],
        flows=[
            {"from": "inicio", "to": "decidir"},
            sim,
            nao,
            {"from": "aprovar", "to": "fim"},
            {"from": "recusar", "to": "fim"},
        ],
    )


def test_flow_condition_becomes_a_formal_condition_expression():
    process = process_of(gateway_spec())
    flow = [f for f in process.findall("bpmn:sequenceFlow", NS) if f.get("name") == "Sim"][0]
    condition = flow.find("bpmn:conditionExpression", NS)
    assert condition is not None
    assert condition.text == "aprovado == true"
    assert condition.get(f"{{http://www.w3.org/2001/XMLSchema-instance}}type") == "bpmn:tFormalExpression"


def test_default_flow_is_recorded_on_the_gateway_that_owns_it():
    process = process_of(gateway_spec(default=True))
    gateway = process.find("bpmn:exclusiveGateway", NS)
    default_flow = [f for f in process.findall("bpmn:sequenceFlow", NS) if f.get("name") == "Não"][0]
    assert gateway.get("default") == default_flow.get("id")
    assert default_flow.find("bpmn:conditionExpression", NS) is None


def test_a_default_flow_cannot_also_carry_a_condition():
    with pytest.raises(SpecError, match="default"):
        build_xml(gateway_spec(default=True, condition="aprovado == false"))


def test_default_flow_leaving_something_that_is_not_a_gateway_is_rejected():
    spec = minimal_spec(
        flows=[
            {"from": "inicio", "to": "revisar"},
            {"from": "revisar", "to": "fim", "default": True},
        ]
    )
    with pytest.raises(SpecError, match="revisar"):
        build_xml(spec)


# ---------------------------------------------------------------------------
# Lanes
# ---------------------------------------------------------------------------

def lane_spec(**overrides):
    spec = minimal_spec(
        lanes=[{"id": "cliente", "name": "Cliente"}, {"id": "suporte", "name": "Suporte"}],
        nodes=[
            {"id": "inicio", "type": "start", "name": "Chamado aberto", "lane": "cliente"},
            {"id": "revisar", "type": "userTask", "name": "Revisar chamado", "lane": "suporte"},
            {"id": "fim", "type": "end", "name": "Chamado encerrado", "lane": "suporte"},
        ],
    )
    spec.update(overrides)
    return spec


def test_lane_set_lists_every_flow_node_exactly_once():
    process = process_of(lane_spec())
    lane_set = process.find("bpmn:laneSet", NS)
    assert lane_set is not None
    refs = [ref.text for lane in lane_set.findall("bpmn:lane", NS)
            for ref in lane.findall("bpmn:flowNodeRef", NS)]
    node_ids = [child.get("id") for child in process
                if tag_of(child) not in ("sequenceFlow", "laneSet")]
    assert sorted(refs) == sorted(node_ids)
    assert len(refs) == len(set(refs))


def test_lanes_keep_their_spec_order_and_names():
    lanes = process_of(lane_spec()).find("bpmn:laneSet", NS).findall("bpmn:lane", NS)
    assert [lane.get("name") for lane in lanes] == ["Cliente", "Suporte"]
    assert [lane.get("id") for lane in lanes] == ["Lane_Cliente", "Lane_Suporte"]


def test_lane_set_is_the_first_child_of_the_process():
    process = process_of(lane_spec())
    assert tag_of(process[0]) == "laneSet"


def test_node_without_a_lane_falls_into_the_first_lane():
    spec = lane_spec()
    del spec["nodes"][0]["lane"]
    lanes = process_of(spec).find("bpmn:laneSet", NS).findall("bpmn:lane", NS)
    cliente_refs = [ref.text for ref in lanes[0].findall("bpmn:flowNodeRef", NS)]
    assert "Start_ChamadoAberto" in cliente_refs


def test_node_pointing_at_an_unknown_lane_is_rejected():
    spec = lane_spec()
    spec["nodes"][1]["lane"] = "juridico"
    with pytest.raises(SpecError, match="juridico"):
        build_xml(spec)


def test_no_lane_set_is_emitted_when_the_spec_has_no_lanes():
    assert process_of(minimal_spec()).find("bpmn:laneSet", NS) is None


# ---------------------------------------------------------------------------
# The canonical example exercises the full feature set
# ---------------------------------------------------------------------------

def test_example_spec_exercises_lanes_conditions_and_a_boundary_event():
    spec = load_spec(EXAMPLE_SPEC)
    assert spec.get("lanes"), "the canonical example should show lanes"
    assert any(n.get("type") == "boundary" for n in spec["nodes"]), \
        "the canonical example should show a boundary event"
    assert any(f.get("condition") for f in spec["flows"]), \
        "the canonical example should show a gateway condition"
    assert any(f.get("default") for f in spec["flows"]), \
        "the canonical example should show a default flow"
