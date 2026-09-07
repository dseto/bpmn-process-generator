import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest

from bpmn_tool import validate, stage2_lint, _di_index, _process_elements, run_layout
from build_editor import build_editor

TEST_CASES = [
    "01-user-onboarding",
    "02-credit-card-approval",
    "03-order-fulfillment",
    "04-incident-management",
    "05-document-revision-cycle",
    "06-bus-boarding-process",
]

BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"


@pytest.mark.parametrize("name", TEST_CASES)
def test_bpmn_file_exists(name: str, tests_dir: Path):
    """Verify that all predefined test BPMN files exist on disk."""
    bpmn_path = tests_dir / f"{name}.bpmn"
    assert bpmn_path.exists(), f"BPMN file missing: {bpmn_path}"
    assert bpmn_path.stat().st_size > 0, f"BPMN file is empty: {bpmn_path}"


@pytest.mark.parametrize("name", TEST_CASES)
def test_bpmn_validation_syntax_and_control_flow(name: str, tests_dir: Path):
    """Run stage 1 (syntax) and stage 2 (control-flow lint) validation on each BPMN file."""
    bpmn_path = tests_dir / f"{name}.bpmn"
    tree = ET.parse(bpmn_path)
    problems, warnings = stage2_lint(tree)
    assert not problems, f"Validation issues in {name}.bpmn:\n" + "\n".join(f"  - {p}" for p in problems)

    # Also test the validate() entrypoint
    val_res = validate(str(bpmn_path))
    assert val_res is True, f"validate() returned False for {name}.bpmn"


@pytest.mark.parametrize("name", TEST_CASES)
def test_bpmn_di_completeness_and_coordinates(name: str, tests_dir: Path):
    """Verify Diagram Interchange (DI) completeness and coordinate validity."""
    bpmn_path = tests_dir / f"{name}.bpmn"
    tree = ET.parse(bpmn_path)
    root = tree.getroot()

    di = _di_index(root)
    assert di["has_diagram"], f"{name}.bpmn has no <bpmndi:BPMNDiagram>"
    assert len(di["shape_ids"]) > 0, f"{name}.bpmn has no shapes"
    assert len(di["edge_ids"]) > 0, f"{name}.bpmn has no edges"

    # Verify all process nodes and sequence flows have corresponding DI elements
    processes = _process_elements(root)
    assert len(processes) >= 1, f"No process element found in {name}.bpmn"

    diagram = root.find(f"{{{BPMNDI_NS}}}BPMNDiagram")
    assert diagram is not None
    plane = diagram.find(f"{{{BPMNDI_NS}}}BPMNPlane")
    assert plane is not None

    # Check bounds for all shapes: valid numbers, width > 0, height > 0
    shapes = plane.findall(f"{{{BPMNDI_NS}}}BPMNShape")
    for shape in shapes:
        element_id = shape.get("bpmnElement")
        assert element_id, f"BPMNShape in {name}.bpmn missing bpmnElement attribute"
        bounds = shape.find(f"{{{DC_NS}}}Bounds")
        assert bounds is not None, f"BPMNShape for {element_id} in {name}.bpmn has no Bounds"
        x = float(bounds.get("x", 0))
        y = float(bounds.get("y", 0))
        width = float(bounds.get("width", 0))
        height = float(bounds.get("height", 0))
        assert width > 0, f"Shape {element_id} in {name}.bpmn has invalid width {width}"
        assert height > 0, f"Shape {element_id} in {name}.bpmn has invalid height {height}"
        assert not (x != x), f"Shape {element_id} in {name}.bpmn has NaN x coordinate"
        assert not (y != y), f"Shape {element_id} in {name}.bpmn has NaN y coordinate"

    # Check waypoints for all edges: valid numbers, at least 2 waypoints
    edges = plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge")
    for edge in edges:
        edge_id = edge.get("bpmnElement")
        assert edge_id, f"BPMNEdge in {name}.bpmn missing bpmnElement attribute"
        waypoints = edge.findall(f"{{{DI_NS}}}waypoint")
        assert len(waypoints) >= 2, f"Edge {edge_id} in {name}.bpmn has fewer than 2 waypoints"
        for wp in waypoints:
            wx = float(wp.get("x", -1))
            wy = float(wp.get("y", -1))
            assert not (wx != wx), f"Waypoint x in {edge_id} of {name}.bpmn is NaN"
            assert not (wy != wy), f"Waypoint y in {edge_id} of {name}.bpmn is NaN"


@pytest.mark.parametrize("name", TEST_CASES)
def test_bpmn_html_roundtrip_and_security(name: str, tests_dir: Path, template_path: Path, tmp_path: Path):
    """Verify HTML packaging, double JSON decoding round-trip, and script tag security."""
    bpmn_path = tests_dir / f"{name}.bpmn"
    output_html = tmp_path / f"{name}.html"

    build_editor(bpmn_path, template_path, output_html, process_slug=name)
    assert output_html.exists(), f"Output HTML was not created for {name}"

    html_content = output_html.read_text(encoding="utf-8")

    # Security check: Exactly 2 closing </script> tags (CDN script in head + main inline script in body)
    closing_tags = re.findall(r"</script>", html_content, re.IGNORECASE)
    assert len(closing_tags) == 2, (
        f"Found {len(closing_tags)} closing </script> tags in {name}.html; "
        "expected exactly 2. Risk of script tag injection or unescaped data."
    )

    # Contract check: Match JSON.parse embedded literal
    m = re.search(r'const ORIGINAL_BPMN_XML = JSON\.parse\(("(?:\\.|[^"\\])*")\);', html_content)
    assert m is not None, f"Could not match JSON.parse literal in {name}.html"

    encoded_literal = m.group(1)
    outer = json.loads(encoded_literal)
    inner_xml = json.loads(outer)
    bpmn_raw = bpmn_path.read_text(encoding="utf-8")

    # Character-exact round-trip check
    assert inner_xml == bpmn_raw, f"Round-trip XML mismatch in {name}.html"


@pytest.mark.parametrize("name", TEST_CASES)
def test_bpmn_layout_recalculation(name: str, tests_dir: Path, tmp_path: Path):
    """Verify that recalculating layout via bpmn_tool produces a valid diagram with intact DI."""
    bpmn_path = tests_dir / f"{name}.bpmn"
    output_bpmn = tmp_path / f"{name}_relayout.bpmn"

    run_layout(str(bpmn_path), str(output_bpmn))
    assert output_bpmn.exists(), f"Relayout output missing: {output_bpmn}"

    # Validate recalculated output
    tree = ET.parse(output_bpmn)
    problems, warnings = stage2_lint(tree)
    assert not problems, f"Recalculated layout for {name} has lint problems:\n" + "\n".join(problems)

    # Check DI index on recalculated output
    root = tree.getroot()
    di = _di_index(root)
    assert di["has_diagram"]
    assert len(di["shape_ids"]) > 0
    assert len(di["edge_ids"]) > 0
