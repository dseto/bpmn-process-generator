from pathlib import Path
from xml.etree import ElementTree as ET
import pytest

from bpmn_tool import (
    build_graph,
    compute_diagram,
    stage2_lint,
    validate,
    run_layout,
    BPMN_NS,
)

MINIMAL_VALID_PROCESS_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="{BPMN_NS}"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
                  id="Defs_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_Simple" isExecutable="false">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Do something">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_2</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_Simple">
      <bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1">
        <omgdc:Bounds x="100" y="100" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_1_di" bpmnElement="Task_1">
        <omgdc:Bounds x="200" y="80" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="End_1_di" bpmnElement="End_1">
        <omgdc:Bounds x="360" y="100" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
        <omgdi:waypoint x="136" y="118" />
        <omgdi:waypoint x="200" y="118" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2">
        <omgdi:waypoint x="300" y="118" />
        <omgdi:waypoint x="360" y="118" />
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""


def test_example_complete_reference(references_dir: Path):
    """Verify that the canonical complete reference BPMN passes all lint checks."""
    example_path = references_dir / "example-complete.bpmn"
    assert example_path.exists()
    assert validate(str(example_path)) is True


def test_example_broken_reference(references_dir: Path):
    """Verify that the broken reference BPMN fails validation with expected lint errors."""
    broken_path = references_dir / "example-broken.bpmn"
    assert broken_path.exists()
    tree = ET.parse(broken_path)
    problems, warnings = stage2_lint(tree)
    assert len(problems) > 0, "Expected broken reference to fail stage 2 lint"

    problem_text = " ".join(problems)
    assert "Task_DoesNotExist" in problem_text
    assert "unreachable" in problem_text


def test_build_graph():
    """Verify build_graph correctly identifies nodes, tags, and incoming/outgoing edges."""
    tree = ET.fromstring(MINIMAL_VALID_PROCESS_XML)
    process = tree.find(f"{{{BPMN_NS}}}process")
    assert process is not None
    nodes, edges, issues = build_graph(process)
    assert not issues
    assert "Start_1" in nodes
    assert "Task_1" in nodes
    assert "End_1" in nodes
    assert nodes["Start_1"]["tag"] == "startEvent"
    assert nodes["Task_1"]["tag"] == "task"
    assert nodes["End_1"]["tag"] == "endEvent"
    assert len(edges) == 2


def test_lint_catches_duplicate_ids():
    """Verify stage2_lint flags duplicate element IDs."""
    xml_with_dups = MINIMAL_VALID_PROCESS_XML.replace('id="End_1"', 'id="Task_1"')
    tree = ET.ElementTree(ET.fromstring(xml_with_dups))
    problems, _ = stage2_lint(tree)
    assert any("duplicate element id 'Task_1'" in p for p in problems)


def test_lint_catches_missing_start_event():
    """Verify stage2_lint flags a process without startEvent."""
    xml = MINIMAL_VALID_PROCESS_XML.replace("<bpmn:startEvent", "<bpmn:task")
    xml = xml.replace("</bpmn:startEvent>", "</bpmn:task>")
    tree = ET.ElementTree(ET.fromstring(xml))
    problems, _ = stage2_lint(tree)
    assert any("no startEvent found" in p for p in problems)


def test_lint_catches_missing_end_event():
    """Verify stage2_lint flags a process without endEvent."""
    xml = MINIMAL_VALID_PROCESS_XML.replace("<bpmn:endEvent", "<bpmn:task")
    xml = xml.replace("</bpmn:endEvent>", "</bpmn:task>")
    tree = ET.ElementTree(ET.fromstring(xml))
    problems, _ = stage2_lint(tree)
    assert any("no endEvent found" in p for p in problems)


def test_lint_catches_dead_ends():
    """Verify stage2_lint flags nodes without outgoing flows that are not endEvents."""
    xml = MINIMAL_VALID_PROCESS_XML.replace(
        '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1" />', ""
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    problems, _ = stage2_lint(tree)
    assert any("dead end" in p for p in problems)


def test_lint_catches_unreachable_node():
    """Verify stage2_lint flags nodes without incoming flows that are not startEvents."""
    xml = MINIMAL_VALID_PROCESS_XML.replace(
        '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1" />', ""
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    problems, _ = stage2_lint(tree)
    assert any("unreachable" in p for p in problems)


def test_compute_diagram_generates_shapes_and_edges():
    """Verify compute_diagram generates valid BPMNDiagram elements with non-empty bounds."""
    tree = ET.fromstring(MINIMAL_VALID_PROCESS_XML)
    process = tree.find(f"{{{BPMN_NS}}}process")
    diagram = compute_diagram(process)
    assert diagram is not None

    plane = diagram.find("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNPlane")
    assert plane is not None
    shapes = plane.findall("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape")
    edges = plane.findall("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNEdge")
    assert len(shapes) == 3
    assert len(edges) == 2


def test_run_layout_cli_wrapper(tmp_path: Path):
    """Verify run_layout writes a well-formed file with fresh BPMNDiagram."""
    input_file = tmp_path / "simple.bpmn"
    input_file.write_text(MINIMAL_VALID_PROCESS_XML, encoding="utf-8")
    output_file = tmp_path / "simple_out.bpmn"

    run_layout(str(input_file), str(output_file))
    assert output_file.exists()
    assert validate(str(output_file)) is True
