"""
Fase 3B of the BPMN editor: integration with the skill (F3.5 to F3.7).

  F3.5  import / export the process spec JSON, with the SAME errors as `SpecError`;
  F3.6  "Organizar automaticamente": the layout of `bpmn_tool layout`, ported to JS
        and applied as ONE undoable command;
  F3.7  review comments in a side file (`<name>.review.json`) that never touch the .bpmn.

The skill's logic lives in Python (`bpmn_build.py`, `bpmn_tool.py`) and the editor runs
only in the browser, so the heart of this module is PARITY: the JS port must give the
same answer as the Python original on the repository's own diagrams.

A note on determinism. `bpmn_tool._topo_order` walks a `set` of node ids, whose order
changes with PYTHONHASHSEED, so stock Python lays a branching diagram out differently
from one run to the next. The editor needs ONE answer: it takes the successors in the
order they appear. To compare like with like, the Python side runs here with an
insertion-ordered `set` (`deterministic_layout`), without touching `bpmn_tool.py`.

Like the other browser tests these need bpmn-js (CDN or assets/vendor) and FAIL,
instead of skipping, when it cannot be loaded.
"""
import contextlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import bpmn_build
import bpmn_tool
import generate_editor_html
from test_editor_ui_phase2 import (
    BPMN_TOOL,
    EDITOR_URL,
    NO_PICKERS,
    ROOT,
    browser,
    element_id,
    load_xml,
    open_editor,
    page,
    saved_xml,
    select,
    stack_index,
)

NS = {"bpmn": bpmn_tool.BPMN_NS, "bpmndi": bpmn_tool.BPMNDI_NS,
      "dc": bpmn_tool.DC_NS, "di": bpmn_tool.DI_NS}

TEMPLATE_FILES = sorted((ROOT / "assets" / "templates").glob("*.bpmn"))
TEST_FILES = [ROOT / "tests" / name for name in (
    "01-user-onboarding.bpmn", "02-credit-card-approval.bpmn", "03-order-fulfillment.bpmn",
    "04-incident-management.bpmn", "05-document-revision-cycle.bpmn",
    "06-bus-boarding-process.bpmn", "movimentacao-frota.bpmn")]
REFERENCE_FILES = [ROOT / "references" / "example-complete.bpmn"]
DIAGRAM_FILES = TEMPLATE_FILES + TEST_FILES + REFERENCE_FILES
EXAMPLE_SPEC = ROOT / "references" / "example-spec.json"


def ids_of(paths):
    return [path.name for path in paths]


@pytest.fixture(scope="module")
def shared_page(browser):
    """One editor session for the whole module: opening the editor (bpmn-js) dominates a test's cost."""
    context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 800})
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    open_editor(page)
    yield page
    context.close()


@pytest.fixture
def editor(shared_page):
    """The shared session, back to a neutral state (nothing selected, no dialogs, clean slate)."""
    page = shared_page
    page.keyboard.press("Escape")
    page.evaluate(
        "() => { propertiesPanel.classList.remove('hidden'); btnPropsToggle.setAttribute('aria-pressed', 'true');"
        " document.querySelectorAll('.dialog-backdrop').forEach(d => { d.hidden = true; });"
        " ['spec-problem', 'spec-export-warning', 'review-problem'].forEach(hideNotice);"
        " setFileState(currentFileName, null, false);"
        " modeler.get('selection').select([]); }")
    # No comments left over from the previous test (nor drafts of them), and no pending warning.
    with answering(page, accept=True):  # a review file over unsaved comments asks first
        page.evaluate(
            "() => { try { localStorage.clear(); } catch (e) {}"
            " loadReviewText('{\"version\": 1, \"comments\": []}', 'limpar.review.json', null); }")
    yield page
    assert not page.errors, page.errors


@contextlib.contextmanager
def answering(page, accept):
    """Answer every confirm() of the block with OK (accept=True) or Cancel; the questions are collected."""
    questions = []

    def handler(dialog):
        questions.append(dialog.message)
        dialog.accept() if accept else dialog.dismiss()

    page.on("dialog", handler)
    try:
        yield questions
    finally:
        page.remove_listener("dialog", handler)


# ---------------------------------------------------------------------------
# Python side of the parity
# ---------------------------------------------------------------------------

class InsertionOrderedSet(dict):
    """A `set` that iterates in insertion order (see the module docstring)."""

    def __init__(self, items=()):
        super().__init__(dict.fromkeys(items))

    def add(self, item):
        self[item] = None


@pytest.fixture
def deterministic_layout(monkeypatch):
    monkeypatch.setattr(bpmn_tool, "set", InsertionOrderedSet, raising=False)


def read_di(diagram):
    """{shapes: {id: [x, y, w, h]}, edges: {id: [[x, y], ...]}} from a BPMNDiagram element."""
    shapes, edges = {}, {}
    for shape in diagram.iter(f"{{{bpmn_tool.BPMNDI_NS}}}BPMNShape"):
        b = shape.find("dc:Bounds", NS)
        shapes[shape.get("bpmnElement")] = [int(float(b.get(k))) for k in ("x", "y", "width", "height")]
    for edge in diagram.iter(f"{{{bpmn_tool.BPMNDI_NS}}}BPMNEdge"):
        edges[edge.get("bpmnElement")] = [
            [int(float(p.get("x"))), int(float(p.get("y")))] for p in edge.findall("di:waypoint", NS)]
    return {"shapes": shapes, "edges": edges}


def expected_layout(path):
    """What `bpmn_tool layout` computes for the file's graph (every process, merged)."""
    root = ET.parse(path).getroot()
    merged = {"shapes": {}, "edges": {}}
    for process in root.findall("bpmn:process", bpmn_tool.NS):
        part = read_di(bpmn_tool.compute_diagram(process))
        merged["shapes"].update(part["shapes"])
        merged["edges"].update(part["edges"])
    return merged


def read_di_from_xml(xml):
    return read_di(ET.fromstring(xml))


# ---------------------------------------------------------------------------
# The editor side
# ---------------------------------------------------------------------------

SNAPSHOT_JS = """
() => {
  const shapes = {}, edges = {};
  modeler.get('elementRegistry').forEach(el => {
    if (el.labelTarget || !el.businessObject || el.type === 'bpmn:Process') return;
    if (el.waypoints) edges[el.id] = el.waypoints.map(p => [p.x, p.y]);
    else shapes[el.id] = [el.x, el.y, el.width, el.height];
  });
  return {shapes, edges};
}
"""


def snapshot(page):
    return page.evaluate(SNAPSHOT_JS)


def open_diagram(page, path):
    load_xml(page, Path(path).read_text(encoding="utf-8"), Path(path).name)


def lay_out(page):
    result = page.evaluate("runAutoLayout()")
    assert result["status"] == "ok", result
    return result


def process_xml(xml):
    """The semantic part of a document: the <bpmn:process> element(s), as text."""
    root = ET.fromstring(xml)
    return "".join(ET.tostring(p, encoding="unicode") for p in root.findall("bpmn:process", NS))


def validate_with_tool(tmp_path, xml, name="check.bpmn"):
    target = tmp_path / name
    target.write_text(xml, encoding="utf-8")
    result = subprocess.run([sys.executable, str(BPMN_TOOL), "validate", str(target)],
                            capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


# ===========================================================================
# F3.6 - Organizar automaticamente
# ===========================================================================

@pytest.mark.parametrize("path", DIAGRAM_FILES, ids=ids_of(DIAGRAM_FILES))
def test_the_auto_layout_gives_the_same_bounds_and_waypoints_as_bpmn_tool(editor, deterministic_layout, path):
    """Parity (F3.6): the same shape bounds and edge waypoints as `compute_diagram` for the same graph."""
    open_diagram(editor, path)
    lay_out(editor)
    actual = snapshot(editor)
    expected = expected_layout(path)

    assert expected["shapes"], "the reference must lay out something"
    for element_id, box in expected["shapes"].items():
        assert actual["shapes"].get(element_id) == box, f"{path.name}: bounds of {element_id}"
    for flow_id, points in expected["edges"].items():
        assert actual["edges"].get(flow_id) == points, f"{path.name}: waypoints of {flow_id}"


@pytest.mark.parametrize("name", ["04-incident-management.bpmn", "05-document-revision-cycle.bpmn"])
def test_the_saved_xml_carries_the_laid_out_di(editor, deterministic_layout, name):
    """The DI that is SAVED (not just what is on screen) is the one `bpmn_tool` computes."""
    path = ROOT / "tests" / name
    open_diagram(editor, path)
    lay_out(editor)
    saved = read_di_from_xml(saved_xml(editor))
    expected = expected_layout(path)
    for element_id, box in expected["shapes"].items():
        assert saved["shapes"].get(element_id) == box, element_id
    for flow_id, points in expected["edges"].items():
        assert saved["edges"].get(flow_id) == points, flow_id


def test_the_layout_covers_lanes_and_diagrams_without_lanes(editor):
    open_diagram(editor, ROOT / "tests" / "06-bus-boarding-process.bpmn")
    assert editor.evaluate("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').length") >= 2
    lay_out(editor)
    lanes = editor.evaluate("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').map(e => [e.x, e.y, e.height])")
    assert [lane[0] for lane in lanes] == [0] * len(lanes)
    assert [lane[2] for lane in lanes] == [360] * len(lanes), "every band is three row-units tall"
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    assert editor.evaluate("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').length") == 0
    lay_out(editor)


def scrambled_xml(path):
    """The file with every shape and waypoint pushed off its grid, so a layout must move things."""
    root = ET.parse(path).getroot()
    for bounds in root.iter(f"{{{bpmn_tool.DC_NS}}}Bounds"):
        bounds.set("x", str(int(float(bounds.get("x"))) + 37))
        bounds.set("y", str(int(float(bounds.get("y"))) + 23))
    for point in root.iter(f"{{{bpmn_tool.DI_NS}}}waypoint"):
        point.set("x", str(int(float(point.get("x"))) + 37))
        point.set("y", str(int(float(point.get("y"))) + 23))
    return ET.tostring(root, encoding="unicode")


def test_the_layout_is_one_undo_step_and_one_undo_restores_everything(editor):
    path = ROOT / "tests" / "04-incident-management.bpmn"
    load_xml(editor, scrambled_xml(path), path.name)
    before_xml = saved_xml(editor)
    before = snapshot(editor)
    assert stack_index(editor) == 0

    lay_out(editor)
    after = snapshot(editor)
    assert after != before, "the file was not laid out already, something must move"
    assert stack_index(editor) == 1, "the whole layout is a single history entry"
    assert editor.evaluate("modeler.get('commandStack').canUndo()")

    editor.keyboard.press("Control+z")
    assert snapshot(editor) == before, "one Ctrl+Z puts every shape and every waypoint back"
    assert saved_xml(editor) == before_xml, "and the saved XML is byte-identical to the original"
    assert not editor.evaluate("modeler.get('commandStack').canUndo()")

    editor.keyboard.press("Control+y")
    assert snapshot(editor) == after, "redo applies the layout again"


def test_the_layout_marks_the_diagram_as_changed(editor):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    assert editor.evaluate("isDirty") is False
    lay_out(editor)
    assert editor.evaluate("isDirty") is True


def test_the_layout_does_not_change_the_graph_names_colors_fonts_or_documentation(editor):
    open_diagram(editor, ROOT / "tests" / "04-incident-management.bpmn")
    task = editor.evaluate(
        "modeler.get('elementRegistry').filter(e => e.type === 'bpmn:UserTask' && !e.labelTarget)[0].id")
    editor.evaluate(
        "id => { const el = modeler.get('elementRegistry').get(id);"
        " modeler.get('modeling').setColor([el], {fill: '#e0f2fe', stroke: '#0284c7'});"
        " applyFontChange([el], f => ({size: 18, isBold: true, isItalic: f.isItalic}));"
        " modeler.get('modeling').updateProperties(el, {name: 'Nome com acentuação ç'});"
        " modeler.get('modeling').updateModdleProperties(el, el.businessObject, "
        "{documentation: [modeler.get('moddle').create('bpmn:Documentation', {text: 'Regra importante'})]}); }", task)
    before = saved_xml(editor)
    lay_out(editor)
    after = saved_xml(editor)

    assert process_xml(after) == process_xml(before), "the process (graph, names, documentation) is untouched"
    for needle in ('name="Nome com acentuação ç"', "Regra importante", 'fill="#e0f2fe"', "<omgdc:Font"):
        assert needle in after, needle
    assert re.search(r'bpmndi:BPMNLabelStyle', after), "the font style survives (G1)"
    assert re.search(r'<bpmndi:BPMNLabel labelStyle="LabelStyle_[^"]+"', after)
    root = ET.fromstring(after)
    style = root.find(".//bpmndi:BPMNLabelStyle/dc:Font", NS)
    assert style.get("size") == "18" and style.get("isBold") == "true"
    # the styled element still points at its style
    shape = [s for s in root.iter(f"{{{bpmn_tool.BPMNDI_NS}}}BPMNShape") if s.get("bpmnElement") == task][0]
    assert shape.find("bpmndi:BPMNLabel", NS).get("labelStyle")


def test_an_empty_diagram_is_left_alone_without_error(editor):
    empty = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" id="D" targetNamespace="http://bpmn.io/schema/bpmn">'
        '<bpmn:process id="Process_Vazio" isExecutable="false"/>'
        '<bpmndi:BPMNDiagram id="BD"><bpmndi:BPMNPlane id="BP" bpmnElement="Process_Vazio"/></bpmndi:BPMNDiagram>'
        '</bpmn:definitions>')
    editor.evaluate("([x, n]) => loadDiagram(x, n, null)", [empty, "vazio.bpmn"])
    editor.wait_for_function("currentFileName === 'vazio.bpmn'")
    result = editor.evaluate("runAutoLayout()")
    assert result["status"] == "empty"
    assert stack_index(editor) == 0
    assert editor.evaluate("isDirty") is False


COLLABORATION = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
    'id="D" targetNamespace="http://bpmn.io/schema/bpmn">'
    '<bpmn:collaboration id="Collab_1"><bpmn:participant id="Part_A" name="A" processRef="Process_A"/>'
    '<bpmn:participant id="Part_B" name="B" processRef="Process_B"/></bpmn:collaboration>'
    '<bpmn:process id="Process_A" isExecutable="false"><bpmn:startEvent id="Start_A" name="Inicio A"/></bpmn:process>'
    '<bpmn:process id="Process_B" isExecutable="false"><bpmn:startEvent id="Start_B" name="Inicio B"/></bpmn:process>'
    '<bpmndi:BPMNDiagram id="BD"><bpmndi:BPMNPlane id="BP" bpmnElement="Collab_1">'
    '<bpmndi:BPMNShape id="Part_A_di" bpmnElement="Part_A" isHorizontal="true"><dc:Bounds x="100" y="50" width="400" height="150"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNShape id="Part_B_di" bpmnElement="Part_B" isHorizontal="true"><dc:Bounds x="100" y="250" width="400" height="150"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNShape id="Start_A_di" bpmnElement="Start_A"><dc:Bounds x="200" y="100" width="36" height="36"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNShape id="Start_B_di" bpmnElement="Start_B"><dc:Bounds x="200" y="300" width="36" height="36"/></bpmndi:BPMNShape>'
    '</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>')


def test_a_diagram_with_pools_is_refused_politely_and_left_untouched(editor):
    editor.evaluate("([x, n]) => loadDiagram(x, n, null)", [COLLABORATION, "pools.bpmn"])
    editor.wait_for_function("currentFileName === 'pools.bpmn'")
    before = snapshot(editor)
    result = editor.evaluate("runAutoLayout()")
    assert result["status"] == "unsupported"
    assert snapshot(editor) == before
    assert stack_index(editor) == 0
    assert "pools" in editor.inner_text("#toast")


EXPANDED = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
    'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="D" targetNamespace="http://bpmn.io/schema/bpmn">'
    '<bpmn:process id="Process_S" isExecutable="false">'
    '<bpmn:startEvent id="Start_1" name="Inicio"><bpmn:outgoing>Flow_1</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:subProcess id="SubProcess_1" name="Bloco"><bpmn:incoming>Flow_1</bpmn:incoming>'
    '<bpmn:outgoing>Flow_2</bpmn:outgoing>'
    '<bpmn:task id="Task_Inner" name="Dentro"/></bpmn:subProcess>'
    '<bpmn:endEvent id="End_1" name="Fim"><bpmn:incoming>Flow_2</bpmn:incoming></bpmn:endEvent>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="SubProcess_1"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="SubProcess_1" targetRef="End_1"/>'
    '</bpmn:process>'
    '<bpmndi:BPMNDiagram id="BD"><bpmndi:BPMNPlane id="BP" bpmnElement="Process_S">'
    '<bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1"><dc:Bounds x="500" y="500" width="36" height="36"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNShape id="SubProcess_1_di" bpmnElement="SubProcess_1" isExpanded="true">'
    '<dc:Bounds x="100" y="40" width="300" height="200"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNShape id="Task_Inner_di" bpmnElement="Task_Inner"><dc:Bounds x="150" y="100" width="100" height="80"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNShape id="End_1_di" bpmnElement="End_1"><dc:Bounds x="700" y="700" width="36" height="36"/></bpmndi:BPMNShape>'
    '<bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1"><di:waypoint x="536" y="518"/><di:waypoint x="100" y="140"/></bpmndi:BPMNEdge>'
    '<bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2"><di:waypoint x="400" y="140"/><di:waypoint x="700" y="718"/></bpmndi:BPMNEdge>'
    '</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>')


def test_an_expanded_subprocess_keeps_its_size_and_carries_its_content(editor):
    editor.evaluate("([x, n]) => loadDiagram(x, n, null)", [EXPANDED, "sub.bpmn"])
    editor.wait_for_function("currentFileName === 'sub.bpmn'")
    before = snapshot(editor)["shapes"]
    lay_out(editor)
    after = snapshot(editor)["shapes"]
    sub_before, sub_after = before["SubProcess_1"], after["SubProcess_1"]
    assert sub_after[2:] == sub_before[2:] == [300, 200], "the container keeps its size"
    assert sub_after[:2] != sub_before[:2], "and it was moved"
    inner_offset = [after["Task_Inner"][i] - sub_after[i] for i in (0, 1)]
    assert inner_offset == [before["Task_Inner"][i] - sub_before[i] for i in (0, 1)], "the content moved with it"
    # the flows reach the container's real border, not a default-size box
    edges = snapshot(editor)["edges"]
    assert edges["Flow_2"][0][0] == sub_after[0] + 300


def test_external_labels_follow_their_elements(editor):
    open_diagram(editor, ROOT / "tests" / "02-credit-card-approval.bpmn")
    lay_out(editor)
    problems = editor.evaluate(
        "() => modeler.get('elementRegistry').filter(l => l.labelTarget && !l.labelTarget.waypoints).map(l => {"
        " const t = l.labelTarget; const cx = l.x + l.width / 2;"
        " return {id: t.id, below: l.y >= t.y + t.height - 1, centered: Math.abs(cx - (t.x + t.width / 2)) <= 1}; })"
        ".filter(r => !r.below || !r.centered)")
    assert problems == [], problems


def test_the_menu_offers_an_accessible_organize_action_that_runs_the_layout(editor):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    editor.click("#menu-edit-trigger")
    button = editor.locator("#btn-auto-layout")
    assert button.is_visible()
    assert editor.get_attribute("#btn-auto-layout", "role") == "menuitem"
    assert "Organizar" in editor.get_attribute("#btn-auto-layout", "aria-label")
    button.click()
    assert stack_index(editor) == 1
    assert not editor.is_visible("#menu-edit-list"), "choosing the item closes the menu"
    assert "organizado" in editor.inner_text("#toast")


def test_the_diagram_stays_valid_after_the_layout(editor, tmp_path):
    """
    The 3A validator reports no new ERROR, and `bpmn_tool validate` still passes on the saved file.

    Warnings are not compared: the CLI's own engine overlaps two tasks of the bus diagram
    (`bpmn_tool layout` warns `di-overlap` there too), and the editor reproduces it faithfully.
    """
    errors = "refreshValidation().filter(f => f.severity === 'error').map(f => f.rule + ':' + f.id)"
    for name in ("04-incident-management.bpmn", "06-bus-boarding-process.bpmn", "03-order-fulfillment.bpmn"):
        open_diagram(editor, ROOT / "tests" / name)
        before = editor.evaluate(errors)
        lay_out(editor)
        after = editor.evaluate(errors)
        assert set(after) <= set(before), f"{name}: new errors {set(after) - set(before)}"
        code, output = validate_with_tool(tmp_path, saved_xml(editor), name)
        assert code == 0, output


# ===========================================================================
# F3.5 - spec JSON: export (extract_spec) and import (bpmn_build + SpecError)
# ===========================================================================

def spec_of(path):
    """What `bpmn_tool extract` produces for a .bpmn on disk."""
    return bpmn_tool.extract_spec(path)


def spec_text(spec):
    """The exact text `bpmn_tool.run_extract` writes."""
    return json.dumps(spec, ensure_ascii=False, indent=2) + "\n"


def canonical(xml):
    """The document as canonical XML, so formatting and attribute order do not count."""
    return ET.canonicalize(xml, strip_text=True)


def semantic_xml(spec):
    """`bpmn_build.build_xml`: the document without the layout."""
    return bpmn_build.build_xml(spec)


def laid_out_xml(spec):
    """`bpmn_build.run_build` without touching the disk: build_tree + compute_diagram, then serialised."""
    tree = bpmn_build.build_tree(spec)
    root = tree.getroot()
    for process in root.findall(f"{{{bpmn_tool.BPMN_NS}}}process"):
        root.append(bpmn_tool.compute_diagram(process))
    ET.indent(tree, space="  ")
    return bpmn_build._serialise(tree)


SPEC_SOURCES = [EXAMPLE_SPEC] + TEMPLATE_FILES + TEST_FILES


def load_spec_for(path):
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return spec_of(path)


EXTRACT_FILES = DIAGRAM_FILES + [ROOT / "references" / "example-broken.bpmn"]


@pytest.mark.parametrize("path", EXTRACT_FILES, ids=ids_of(EXTRACT_FILES))
def test_the_exported_spec_is_the_one_bpmn_tool_extract_writes(editor, path):
    """Parity (F3.5): the JS extractor and `extract_spec` write the very same JSON text."""
    text = editor.evaluate(
        "x => SkillPort.specToJson(SkillPort.extractSpecFromXml(x).spec)", path.read_text(encoding="utf-8"))
    assert text == spec_text(spec_of(path))


@pytest.mark.parametrize("path", SPEC_SOURCES, ids=ids_of(SPEC_SOURCES))
def test_the_imported_spec_builds_the_same_bpmn_as_bpmn_build(editor, deterministic_layout, path):
    """
    Parity (F3.5): ids, types, names, flows, conditions, default, lanes and events equal
    `bpmn_build.build_xml`, and with the layout the whole document equals `bpmn_build`'s.
    """
    spec = load_spec_for(path)
    semantic = editor.evaluate("s => SkillPort.specToXml(s, {layout: false})", spec)
    assert canonical(semantic) == canonical(semantic_xml(spec)), path.name
    full = editor.evaluate("s => SkillPort.specToXml(s)", spec)
    assert canonical(full) == canonical(laid_out_xml(spec)), path.name


def test_the_built_document_has_coherent_incoming_and_outgoing(editor):
    spec = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
    root = ET.fromstring(editor.evaluate("s => SkillPort.specToXml(s)", spec))
    process = root.find("bpmn:process", NS)
    nodes = {el.get("id"): el for el in process if el.get("id") and not el.tag.endswith(("sequenceFlow", "laneSet"))}
    for flow in process.findall("bpmn:sequenceFlow", NS):
        assert flow.get("id") in [e.text for e in nodes[flow.get("sourceRef")].findall("bpmn:outgoing", NS)]
        assert flow.get("id") in [e.text for e in nodes[flow.get("targetRef")].findall("bpmn:incoming", NS)]
    assert [f.get("id") for f in process.findall("bpmn:sequenceFlow", NS)] == [
        f"Flow_{i}" for i in range(1, len(spec["flows"]) + 1)], "Flow_N ids are sequential"
    covered = [ref.text for ref in process.iter(f"{{{bpmn_tool.BPMN_NS}}}flowNodeRef")]
    lane_ids = {l.get("id") for l in process.iter(f"{{{bpmn_tool.BPMN_NS}}}lane")}
    assert sorted(covered) == sorted(i for i in nodes if i not in lane_ids), "every node is in exactly one lane"


def minimal(**extra):
    spec = {"nodes": [{"id": "a", "type": "start", "name": "Inicio"}, {"id": "b", "type": "userTask", "name": "Fazer"}],
            "flows": [{"from": "a", "to": "b"}]}
    spec.update(extra)
    return spec


def with_nodes(*nodes, **extra):
    spec = {"nodes": list(nodes), "flows": []}
    spec.update(extra)
    return spec


START = {"id": "a", "type": "start", "name": "Inicio"}
TASK = {"id": "t", "type": "userTask", "name": "Tarefa"}
GATE = {"id": "g", "type": "xor", "name": "Decide"}

# (case, spec, what bpmn_build's SpecError says, the editor's stable code, what the message must name)
INVALID_SPECS = [
    ("no nodes", {"flows": []}, "non-empty 'nodes'", "nodes-empty", ""),
    ("empty nodes", {"nodes": []}, "non-empty 'nodes'", "nodes-empty", ""),
    ("node is not an object", {"nodes": ["a"]}, "must be an object", "node-not-object", ""),
    ("node without id", {"nodes": [{"type": "start"}]}, "without a usable 'id'", "node-no-id", ""),
    ("duplicate id", with_nodes(START, dict(START)), "duplicate node id 'a'", "node-duplicate-id", "'a'"),
    ("unknown type", with_nodes({"id": "a", "type": "banana"}), "unknown type 'banana'", "node-unknown-type", "banana"),
    ("missing type", with_nodes({"id": "a"}), "unknown type", "node-unknown-type", "'a'"),
    ("unknown event", with_nodes({"id": "a", "type": "start", "event": "raio"}), "unknown event 'raio'",
     "node-unknown-event", "raio"),
    ("event on a task", with_nodes({"id": "a", "type": "userTask", "event": "timer"}), "cannot carry an event",
     "node-event-not-allowed", "'a'"),
    ("boundary without attachedTo", with_nodes(TASK, {"id": "b", "type": "boundary", "event": "timer"}),
     "needs 'attachedTo'", "boundary-no-host", "'b'"),
    ("boundary on a missing node", with_nodes({"id": "b", "type": "boundary", "attachedTo": "zzz"}),
     "attached to unknown node 'zzz'", "boundary-unknown-host", "zzz"),
    ("boundary on a gateway", with_nodes(GATE, {"id": "b", "type": "boundary", "attachedTo": "g"}),
     "boundary events only attach to activities", "boundary-bad-host", "'g'"),
    ("flows is not a list", minimal(flows={"x": 1}), "'flows' must be a list", "flows-not-list", ""),
    ("flow is not an object", minimal(flows=["a"]), "flow #1 must be an object", "flow-not-object", ""),
    ("flow without 'to'", minimal(flows=[{"from": "a"}]), "needs both 'from' and 'to'", "flow-missing-ends", ""),
    ("flow from a missing node", minimal(flows=[{"from": "zzz", "to": "b"}]), "starts at unknown node 'zzz'",
     "flow-unknown-source", "zzz"),
    ("flow to a missing node", minimal(flows=[{"from": "a", "to": "zzz"}]), "ends at unknown node 'zzz'",
     "flow-unknown-target", "zzz"),
    ("default flow out of a task", minimal(flows=[{"from": "b", "to": "a", "default": True}]),
     "only gateways have a default flow", "flow-default-not-gateway", "'b'"),
    ("default flow with a condition", with_nodes(GATE, TASK, flows=[{"from": "g", "to": "t", "default": True,
                                                                       "condition": "x > 1"}]),
     "AND carries a condition", "flow-default-with-condition", ""),
    ("lanes is not a list", minimal(lanes="x"), "'lanes' must be a list", "lanes-not-list", ""),
    ("lane is not an object", minimal(lanes=["x"]), "lane #1 must be an object", "lane-not-object", ""),
    ("lane without id or name", minimal(lanes=[{}]), "needs an 'id' or a 'name'", "lane-no-id", ""),
    ("duplicate lane", minimal(lanes=[{"id": "l"}, {"id": "l"}]), "duplicate lane id 'l'", "lane-duplicate-id", "'l'"),
    ("node on a missing lane", with_nodes(dict(START, lane="zzz"), lanes=[{"id": "l"}]),
     "points at unknown lane 'zzz'", "node-unknown-lane", "zzz"),
]

BUILD_JS = """
s => {
  try { SkillPort.specToXml(s); return null; }
  catch (e) { return {code: e.code, message: e.message, spec: e instanceof SkillPort.SpecError}; }
}
"""


@pytest.mark.parametrize("case", INVALID_SPECS, ids=[c[0] for c in INVALID_SPECS])
def test_an_invalid_spec_is_rejected_for_the_same_reason_as_spec_error(editor, case):
    """Parity (F3.5): whatever `SpecError` rejects, the editor rejects, naming the same culprit in pt-BR."""
    name, spec, python_says, code, culprit = case
    with pytest.raises(bpmn_build.SpecError, match=re.escape(python_says)):
        bpmn_build.build_tree(spec)
    result = editor.evaluate(BUILD_JS, spec)
    assert result and result["spec"], f"the editor accepted a spec that SpecError rejects: {name}"
    assert result["code"] == code
    assert culprit in result["message"]
    assert python_says not in result["message"], "the message is pt-BR, not the English one"


def test_the_editor_does_not_reject_what_the_builder_accepts(editor):
    """The other direction of the parity: odd-but-valid specs still build (no stricter than SpecError)."""
    odd = [
        minimal(id="Process_X", name=None),
        minimal(executable=True, name="Com acentuação"),
        with_nodes(START, {"id": "b", "type": "catch", "event": "timer"}, {"id": "c", "type": "end", "event": None}),
        with_nodes(dict(START, name=None), dict(TASK, name="")),
        minimal(lanes=[{"name": "Só nome"}]),
        minimal(flows=None),
        with_nodes(GATE, TASK, flows=[{"from": "g", "to": "t", "default": True}]),
    ]
    for spec in odd:
        bpmn_build.build_xml(spec)
        assert editor.evaluate(BUILD_JS, spec) is None, spec


def test_generated_ids_follow_the_builders_rules(editor):
    """PascalCase, accent-free, prefixed by kind, numeric suffix on a clash, Flow_N in order."""
    spec = with_nodes(
        {"id": "i", "type": "start", "name": "Resolvível? Não"},
        {"id": "t1", "type": "userTask", "name": "Notificar cliente"},
        {"id": "t2", "type": "serviceTask", "name": "Notificar cliente"},
        {"id": "t3", "type": "task", "name": "notificar cliente"},
        {"id": "g", "type": "or"},
        {"id": "e", "type": "end", "name": "Emitir NFe"},
        flows=[{"from": "i", "to": "t1"}, {"from": "t1", "to": "t2"}, {"from": "t2", "to": "t3"},
               {"from": "t3", "to": "g"}, {"from": "g", "to": "e"}])

    def ids(xml):
        return [el.get("id") for el in ET.fromstring(xml).find("bpmn:process", NS)]

    assert ids(editor.evaluate("s => SkillPort.specToXml(s, {layout: false})", spec)) == ids(bpmn_build.build_xml(spec))
    assert "Task_NotificarCliente_2" in ids(bpmn_build.build_xml(spec))


EXAMPLE_TEXT = EXAMPLE_SPEC.read_text(encoding="utf-8")


def diagram_signature(xml):
    """Ids, tags, names and wiring of a saved diagram: what must survive bpmn-js loading it."""
    process = ET.fromstring(xml).find("bpmn:process", NS)

    def condition(flow):
        found = flow.find("bpmn:conditionExpression", NS)
        return found.text if found is not None else None

    nodes = sorted((el.get("id"), el.tag.split("}")[1], el.get("name"), el.get("default"), el.get("attachedToRef"))
                   for el in process if el.tag.split("}")[1] in bpmn_tool.FLOW_NODE_TAGS)
    flows = sorted((f.get("id"), f.get("sourceRef"), f.get("targetRef"), f.get("name"), condition(f))
                   for f in process.findall("bpmn:sequenceFlow", NS))
    lanes = sorted((lane.get("id"), lane.get("name"), tuple(r.text for r in lane.findall("bpmn:flowNodeRef", NS)))
                   for lane in process.iter(f"{{{bpmn_tool.BPMN_NS}}}lane"))
    return nodes, flows, lanes


def test_importing_a_spec_opens_a_new_laid_out_diagram(editor, deterministic_layout, tmp_path):
    result = editor.evaluate("t => importSpecText(t, 'atendimento-spec.json')", EXAMPLE_TEXT)
    assert result == {"ok": True, "name": "atendimento.bpmn"}
    assert editor.evaluate("currentFileName") == "atendimento.bpmn"
    assert editor.evaluate("isDirty") is True, "a new, unsaved diagram"
    assert editor.evaluate("currentFileHandle") is None

    spec = json.loads(EXAMPLE_TEXT)
    saved = saved_xml(editor)
    assert diagram_signature(saved) == diagram_signature(semantic_xml(spec)), "same ids, types, names, wiring, lanes"
    expected = read_di_from_xml(laid_out_xml(spec))
    actual = read_di_from_xml(saved)
    assert actual["shapes"] == expected["shapes"], "laid out like bpmn_build"
    assert editor.evaluate("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').length") == 2
    code, output = validate_with_tool(tmp_path, saved, "importado.bpmn")
    assert code == 0, output
    assert editor.evaluate("refreshValidation().filter(f => f.severity === 'error').length") == 0


def test_an_invalid_spec_shows_a_portuguese_message_and_leaves_the_diagram_alone(editor):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    before = saved_xml(editor)
    bad = json.dumps(with_nodes(START, flows=[{"from": "a", "to": "zzz"}]))
    result = editor.evaluate("t => importSpecText(t, 'ruim-spec.json')", bad)
    assert result["ok"] is False and result["code"] == "flow-unknown-target"
    text = editor.inner_text("#notice-spec-problem .notice-text")
    assert "Spec inválido" in text and "zzz" in text
    assert saved_xml(editor) == before and editor.evaluate("currentFileName") == "01-user-onboarding.bpmn"
    assert editor.evaluate("isDirty") is False and stack_index(editor) == 0


@pytest.mark.parametrize("text, code", [("{nao e json", "json-invalid"), ("[1, 2]", "spec-not-object"),
                                        ('"x"', "spec-not-object")])
def test_text_that_is_not_a_spec_object_is_rejected_without_touching_the_diagram(editor, text, code):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    before = saved_xml(editor)
    result = editor.evaluate("t => importSpecText(t, 'x.json')", text)
    assert result["ok"] is False and result["code"] == code
    assert editor.is_visible("#notice-spec-problem")
    assert saved_xml(editor) == before


def test_text_that_cannot_go_into_xml_is_rejected_before_replacing_anything(editor):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    before = saved_xml(editor)
    spec = minimal()
    spec["nodes"][1]["name"] = "Tarefa \u0001 com controle"
    result = editor.evaluate("t => importSpecText(t, 'x.json')", json.dumps(spec))
    assert result == {"ok": False, "code": "invalid-xml"}
    assert saved_xml(editor) == before


def test_importing_over_unsaved_changes_asks_first(editor):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    task = editor.evaluate(
        "modeler.get('elementRegistry').filter(e => e.type === 'bpmn:ServiceTask' && !e.labelTarget)[0].id")
    editor.evaluate(
        "id => modeler.get('modeling').updateProperties(modeler.get('elementRegistry').get(id), {name: 'Mudei'})",
        task)
    assert editor.evaluate("isDirty") is True
    before = saved_xml(editor)

    with answering(editor, accept=False) as questions:
        result = editor.evaluate("t => importSpecText(t, 'novo-spec.json')", EXAMPLE_TEXT)
    assert result == {"ok": False, "code": "cancelled"} and len(questions) == 1
    assert "não salvas" in questions[0]
    assert saved_xml(editor) == before, "declining keeps the current diagram"

    with answering(editor, accept=True) as questions:
        result = editor.evaluate("t => importSpecText(t, 'novo-spec.json')", EXAMPLE_TEXT)
    assert result["ok"] is True and len(questions) == 1
    assert editor.evaluate("currentFileName") == "novo.bpmn"


def test_importing_without_unsaved_changes_does_not_ask(editor):
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    with answering(editor, accept=False) as questions:
        result = editor.evaluate("t => importSpecText(t, 'novo-spec.json')", EXAMPLE_TEXT)
    assert result["ok"] is True and questions == []


def test_the_import_menu_item_reads_a_spec_from_a_file(editor, tmp_path):
    spec_file = tmp_path / "pelo-arquivo-spec.json"
    spec_file.write_text(EXAMPLE_TEXT, encoding="utf-8")
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    editor.click("#menu-file-trigger")
    assert editor.get_attribute("#btn-import-spec", "role") == "menuitem"
    assert "Importar" in editor.inner_text("#btn-import-spec")
    editor.click("#btn-import-spec")
    editor.set_input_files("#spec-input", str(spec_file))
    editor.wait_for_function("currentFileName === 'pelo-arquivo.bpmn'")
    assert editor.evaluate("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').length") == 2


def test_the_import_uses_the_same_layout_code_as_organize(editor):
    """Organising the imported diagram changes nothing: import and 'Organizar' share one engine."""
    editor.evaluate("t => importSpecText(t, 'x-spec.json')", EXAMPLE_TEXT)
    before = snapshot(editor)
    lay_out(editor)
    assert snapshot(editor) == before


ROUND_TRIP_FILES = TEMPLATE_FILES + [ROOT / "tests" / name for name in (
    "02-credit-card-approval.bpmn", "03-order-fulfillment.bpmn", "04-incident-management.bpmn",
    "05-document-revision-cycle.bpmn", "06-bus-boarding-process.bpmn", "movimentacao-frota.bpmn")]


@pytest.mark.parametrize("path", ROUND_TRIP_FILES, ids=ids_of(ROUND_TRIP_FILES))
def test_editor_to_spec_to_editor_preserves_the_process(editor, path):
    """Round trip (F3.5): the same nodes, flows, conditions, default, events and lanes come back."""
    from test_spec_roundtrip import spec_shape

    open_diagram(editor, path)
    first = editor.evaluate("buildSpecExport().then(r => r.text)")
    assert first == spec_text(spec_of(path)), "the editor exports what bpmn_tool extract writes for the file"
    assert editor.evaluate("t => importSpecText(t, 'volta-spec.json').then(r => r.ok)", first) is True
    second = editor.evaluate("buildSpecExport().then(r => r.text)")
    assert spec_shape(json.loads(second)) == spec_shape(json.loads(first))


def test_exporting_from_the_menu_downloads_the_spec_named_after_the_diagram(editor):
    path = ROOT / "tests" / "04-incident-management.bpmn"
    open_diagram(editor, path)
    editor.click("#menu-file-trigger")
    assert editor.get_attribute("#btn-export-spec", "role") == "menuitem"
    with editor.expect_download() as info:
        editor.click("#btn-export-spec")
    download = info.value
    assert download.suggested_filename == "04-incident-management-spec.json"
    content = Path(download.path()).read_text(encoding="utf-8")
    assert content == spec_text(spec_of(path)), "UTF-8, indented, accents unescaped, as `extract` writes"
    assert "\\u00" not in content
    assert not editor.is_visible("#notice-spec-export-warning"), "a plain diagram raises no warning"
    assert editor.evaluate("isDirty") is False, "exporting does not change the diagram"


def test_exporting_warns_about_pools_without_blocking(editor):
    editor.evaluate("([x, n]) => loadDiagram(x, n, null)", [COLLABORATION, "pools.bpmn"])
    editor.wait_for_function("currentFileName === 'pools.bpmn'")
    with editor.expect_download() as info:
        editor.evaluate("exportSpec()")
    assert info.value.suggested_filename == "pools-spec.json"
    warning = editor.inner_text("#notice-spec-export-warning .notice-text")
    assert "2 processos" in warning and "Process_A" in warning


def test_exporting_warns_about_an_expanded_subprocess_with_inner_flow(editor):
    editor.evaluate("([x, n]) => loadDiagram(x, n, null)", [EXPANDED, "sub.bpmn"])
    editor.wait_for_function("currentFileName === 'sub.bpmn'")
    with editor.expect_download():
        editor.evaluate("exportSpec()")
    warning = editor.inner_text("#notice-spec-export-warning .notice-text")
    assert "SubProcess_1" in warning and "subprocesso" in warning


# ===========================================================================
# F3.7 - review comments in a side file
# ===========================================================================

def prevented_unload(page):
    return page.evaluate(
        "() => { const e = new Event('beforeunload', {cancelable: true}); "
        "window.dispatchEvent(e); return e.defaultPrevented; }")


def comment(page, element, text, author=""):
    """Add a comment through the panel, as a person would."""
    select(page, element)
    page.fill("#review-author", author)
    page.fill("#review-text", text)
    page.click("#review-add")


def review_items(page, selector="#review-list"):
    return page.locator(f"{selector} .review-item")


def counter(page):
    return int(page.inner_text("#rv-open")), int(page.inner_text("#rv-orphans"))


def open_review_diagram(page, name="01-user-onboarding.bpmn"):
    open_diagram(page, ROOT / "tests" / name)
    return element_id(page, "bpmn:UserTask"), element_id(page, "bpmn:ServiceTask")


def test_comments_never_change_the_saved_xml_the_history_or_the_dirty_flag(editor):
    task, service = open_review_diagram(editor)
    xml = saved_xml(editor)
    def export_svg():
        editor.evaluate("modeler.get('selection').select([])")  # a selection outline is not a comment
        return editor.evaluate("modeler.saveSVG().then(r => r.svg)")

    svg = export_svg()

    comment(editor, task, "Falta o prazo desta etapa", "Ana")
    assert saved_xml(editor) == xml
    comment(editor, service, "Quem é o dono do sistema?")
    editor.locator("#review-list [data-review-action='toggle']").first.click()
    assert saved_xml(editor) == xml, "resolving a comment is no change to the diagram either"
    select(editor, task)
    editor.locator("#review-list [data-review-action='delete']").first.click()

    assert saved_xml(editor) == xml, "byte for byte"
    assert export_svg() == svg, "nor does the SVG export see them"
    assert editor.evaluate("isDirty") is False, "commenting does not mark the diagram as changed"
    assert stack_index(editor) == 0 and not editor.evaluate("modeler.get('commandStack').canUndo()")
    assert "Ana" not in xml and "prazo" not in saved_xml(editor)


def test_the_panel_lists_adds_resolves_reopens_and_deletes_comments(editor):
    task, _service = open_review_diagram(editor)
    select(editor, task)
    assert editor.is_visible("#review-section")
    assert "Comentários de revisão" in editor.text_content("#review-title")
    assert review_items(editor).count() == 0

    comment(editor, task, "Primeira dúvida", "Ana")
    comment(editor, task, "Segunda dúvida")
    items = review_items(editor)
    assert items.count() == 2
    assert "Primeira dúvida" in items.nth(0).inner_text() and "Ana" in items.nth(0).inner_text()
    assert "Sem autor" in items.nth(1).inner_text(), "the author is optional"
    assert re.search(r"\d{2}/\d{2}/\d{4}", items.nth(0).inner_text()), "the date is automatic"
    assert editor.input_value("#review-text") == "", "the field is cleared for the next one"

    first = items.nth(0)
    first.locator("[data-review-action='toggle']").click()
    assert first.get_attribute("data-resolved") == "true"
    assert first.locator("[data-review-action='toggle']").inner_text() == "Reabrir"
    assert "Resolvido" in first.inner_text()
    first.locator("[data-review-action='toggle']").click()
    assert first.get_attribute("data-resolved") == "false"
    assert first.locator("[data-review-action='toggle']").inner_text() == "Resolver"

    items.nth(1).locator("[data-review-action='delete']").click()
    assert items.count() == 1 and "Primeira" in items.nth(0).inner_text()


def test_an_empty_comment_is_refused_and_ctrl_enter_adds(editor):
    task, _service = open_review_diagram(editor)
    select(editor, task)
    editor.click("#review-add")
    assert review_items(editor).count() == 0 and "Escreva" in editor.inner_text("#toast")
    editor.fill("#review-text", "   ")
    editor.click("#review-add")
    assert review_items(editor).count() == 0
    editor.fill("#review-text", "Pelo teclado")
    editor.press("#review-text", "Control+Enter")
    assert review_items(editor).count() == 1


def test_each_element_shows_only_its_own_comments(editor):
    task, service = open_review_diagram(editor)
    comment(editor, task, "Da tarefa")
    comment(editor, service, "Do serviço")
    select(editor, task)
    assert review_items(editor).count() == 1 and "Da tarefa" in review_items(editor).first.inner_text()
    select(editor, service)
    assert review_items(editor).count() == 1 and "Do serviço" in review_items(editor).first.inner_text()
    editor.evaluate("modeler.get('selection').select([])")
    assert not editor.is_visible("#review-section"), "no selection, no element section"


def test_the_review_controls_have_accessible_names_and_visible_focus(editor):
    task, _service = open_review_diagram(editor)
    comment(editor, task, "Revisar prazo desta etapa", "Ana")
    select(editor, task)
    assert editor.get_attribute("#review-section", "aria-labelledby") == "review-title"
    for field in ("review-author", "review-text"):
        assert editor.query_selector(f"label[for='{field}']"), field
    assert editor.inner_text("#review-add").strip()
    for button in editor.locator("#review-list button").all():
        label = button.get_attribute("aria-label")
        assert label and "Revisar prazo" in label, "each action names the comment it acts on"
    editor.focus("#review-text")
    editor.keyboard.press("Tab")
    assert editor.evaluate("document.activeElement.id") == "review-add"
    outline = editor.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    assert outline != "none", "keyboard focus is visible"
    # the menu items and the footer counter are named too
    for item in ("btn-save-comments", "btn-open-comments", "btn-import-spec", "btn-export-spec", "btn-auto-layout"):
        assert editor.evaluate(
            "id => { const b = document.getElementById(id); return !!(b.getAttribute('aria-label') || b.textContent.trim()); }",
            item), item
    assert "Comentários de revisão" in editor.get_attribute("#review-summary", "aria-label")


def test_open_comments_put_a_badge_on_the_canvas_that_is_not_exported(editor):
    task, _service = open_review_diagram(editor)
    comment(editor, task, "Um")
    comment(editor, task, "Dois")
    badge = editor.locator(".rev-badge")
    assert badge.count() == 1 and badge.inner_text().strip().endswith("2")
    assert "2 comentários de revisão abertos" in badge.get_attribute("aria-label")
    # it sits on the top-right corner of the element; validation badges use the top-left (and another class)
    placement = editor.evaluate(
        "id => { const r = modeler.get('elementRegistry').getGraphics(id).getBoundingClientRect();"
        " const b = document.querySelector('.rev-badge').getBoundingClientRect();"
        " return {badgeCenter: (b.left + b.right) / 2, elementCenter: (r.left + r.right) / 2, top: b.top < r.top + 10}; }",
        task)
    assert placement["badgeCenter"] > placement["elementCenter"] and placement["top"]
    assert "vld-" not in badge.get_attribute("class")
    # not in the exports, not in the XML, hidden when printing
    assert "rev-badge" not in editor.evaluate("modeler.saveSVG().then(r => r.svg)")
    assert "rev-badge" not in saved_xml(editor) and "💬" not in saved_xml(editor)
    editor.emulate_media(media="print")
    try:
        assert editor.evaluate("getComputedStyle(document.querySelector('.rev-badge')).display") == "none"
    finally:
        editor.emulate_media(media="screen")
    # resolving all of them takes the badge away
    for button in editor.locator("#review-list [data-review-action='toggle']").all():
        button.click()
    assert editor.locator(".rev-badge").count() == 0


def test_the_footer_counts_the_open_comments(editor):
    task, service = open_review_diagram(editor)
    assert counter(editor) == (0, 0)
    comment(editor, task, "A")
    comment(editor, task, "B")
    comment(editor, service, "C")
    assert counter(editor) == (3, 0)
    editor.locator("#review-list [data-review-action='toggle']").first.click()
    assert counter(editor) == (2, 0)
    assert "2 abertos" in editor.get_attribute("#review-summary", "aria-label")
    assert editor.is_visible("#review-summary"), "visible even with the panel closed"


def test_the_footer_counter_takes_you_to_a_commented_element(editor):
    task, service = open_review_diagram(editor)
    comment(editor, service, "Olha isto")
    editor.evaluate("modeler.get('selection').select([])")
    editor.click("#review-summary")
    assert editor.evaluate("modeler.get('selection').get().map(e => e.id)") == [service]
    assert review_items(editor).count() == 1


def test_saving_the_comments_writes_a_review_json_next_to_the_diagram_name(editor):
    task, service = open_review_diagram(editor)
    comment(editor, task, "Acentuação: ação não é opção", "Ana Maria")
    comment(editor, service, "Segundo")
    editor.locator("#review-list [data-review-action='toggle']").first.click()
    editor.click("#menu-file-trigger")
    with editor.expect_download() as info:
        editor.click("#btn-save-comments")
    assert info.value.suggested_filename == "01-user-onboarding.review.json"
    content = Path(info.value.path()).read_text(encoding="utf-8")
    data = json.loads(content)
    assert data["version"] == 1 and data["diagram"] == "01-user-onboarding.bpmn"
    assert {c["text"]: c["resolved"] for c in data["comments"]} == {
        "Acentuação: ação não é opção": False, "Segundo": True}
    assert {c["author"] for c in data["comments"]} == {"Ana Maria", ""}
    assert "\\u00" not in content, "accents are written as they are"
    for entry in data["comments"]:
        assert set(entry) == {"id", "elementId", "text", "author", "createdAt", "resolved"}
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", entry["createdAt"])
    assert saved_xml(editor).count("Segundo") == 0, "and the .bpmn is untouched by it"


def test_a_saved_review_file_round_trips_through_open(editor, tmp_path):
    task, service = open_review_diagram(editor)
    comment(editor, task, "Ida e volta", "Ana")
    comment(editor, service, "Resolvido", "Beto")
    editor.locator("#review-list [data-review-action='toggle']").first.click()
    saved = json.loads(editor.evaluate("saveReviewFile().then(r => r.text)"))
    target = tmp_path / "x.review.json"
    target.write_text(json.dumps(saved), encoding="utf-8")

    editor.evaluate("loadReviewText('{\"version\": 1, \"comments\": []}', 'vazio.review.json', null)")
    assert counter(editor) == (0, 0)
    editor.click("#menu-file-trigger")
    editor.click("#btn-open-comments")
    editor.set_input_files("#comments-input", str(target))
    editor.wait_for_function("document.getElementById('rv-open').textContent !== '0'")
    assert counter(editor) == (1, 0), "the resolved one is not counted as open"
    select(editor, task)
    assert "Ida e volta" in review_items(editor).first.inner_text()
    select(editor, service)
    assert review_items(editor).first.get_attribute("data-resolved") == "true"


def test_comments_of_missing_elements_are_kept_and_listed_as_orphans(editor, tmp_path):
    task, _service = open_review_diagram(editor)
    payload = {"version": 1, "diagram": "01-user-onboarding.bpmn", "comments": [
        {"id": "c1", "elementId": task, "text": "Existe", "author": "Ana", "createdAt": "2026-01-02T03:04:05.000Z",
         "resolved": False},
        {"id": "c2", "elementId": "Task_QueSumiu", "text": "Sobrou", "author": "", "createdAt": "2026-01-02T03:04:05.000Z",
         "resolved": False},
        {"id": "c3", "elementId": "Task_QueSumiu", "text": "Resolvido e órfão", "author": "Beto",
         "createdAt": "2026-01-02T03:04:05.000Z", "resolved": True},
        {"nonsense": True},
    ]}
    target = tmp_path / "orfaos.review.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    editor.set_input_files("#comments-input", str(target))
    editor.wait_for_function("document.getElementById('rv-orphans').textContent !== '0'")

    assert counter(editor) == (1, 2)
    assert editor.is_visible("#review-orphans")
    assert review_items(editor, "#review-orphans-list").count() == 2
    assert "Task_QueSumiu" in editor.inner_text("#review-orphans-list")
    assert "Sobrou" in editor.inner_text("#review-orphans-list")
    assert "órfão" in editor.inner_text("#toast") and "inválido" in editor.inner_text("#toast")
    # preserved, not discarded: saving writes them back
    saved = json.loads(editor.evaluate("saveReviewFile().then(r => r.text)"))
    assert {c["id"] for c in saved["comments"]} == {"c1", "c2", "c3"}
    # an orphan can still be dealt with
    editor.locator("#review-orphans-list [data-review-action='delete']").first.click()
    assert counter(editor) == (1, 1)


def test_deleting_an_element_orphans_its_comments_and_undo_brings_them_back(editor):
    task, _service = open_review_diagram(editor)
    comment(editor, task, "Vai ficar sem dono")
    assert counter(editor) == (1, 0)
    editor.evaluate(
        "id => modeler.get('modeling').removeElements([modeler.get('elementRegistry').get(id)])", task)
    assert counter(editor) == (0, 1), "the comment is kept, now as an orphan"
    assert editor.is_visible("#review-orphans") and "Vai ficar sem dono" in editor.inner_text("#review-orphans-list")
    assert editor.locator(".rev-badge").count() == 0
    editor.keyboard.press("Control+z")
    assert counter(editor) == (1, 0), "undoing the removal reattaches it"
    assert not editor.is_visible("#review-orphans")


def test_comments_have_their_own_local_draft_apart_from_the_diagram_draft(page):
    open_editor(page)
    task = element_id(page, "bpmn:UserTask")
    comment(page, task, "Rascunho de comentário", "Ana")
    keys = page.evaluate("Object.keys(localStorage)")
    assert [k for k in keys if k.startswith("bpmn-editor-review:")], keys
    assert not [k for k in keys if k.startswith("bpmn-editor-draft:")], "the diagram has no draft of its own here"

    page.reload()
    page.wait_for_function(
        "typeof modeler !== 'undefined' && modeler && modeler.get('elementRegistry').getAll().length > 1",
        timeout=45000)
    page.wait_for_function("document.getElementById('rv-open').textContent === '1'")
    select(page, element_id(page, "bpmn:UserTask"))
    assert "Rascunho de comentário" in review_items(page).first.inner_text(), "comments survive between sessions"
    assert prevented_unload(page) is True, "and they are still pending, so closing warns"

    page.evaluate("saveReviewFile()")
    assert not [k for k in page.evaluate("Object.keys(localStorage)") if k.startswith("bpmn-editor-review:")], \
        "saving to the file retires the draft"
    assert not page.errors, page.errors


def test_blocked_local_storage_does_not_break_the_comments(browser):
    context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 800})
    context.add_init_script(NO_PICKERS)
    context.add_init_script(
        "Object.defineProperty(window, 'localStorage', {get() { throw new Error('storage bloqueado'); }});")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        open_editor(page)
        task = element_id(page, "bpmn:UserTask")
        comment(page, task, "Sem storage")
        assert review_items(page).count() == 1 and counter(page) == (1, 0)
        assert errors == [], errors
    finally:
        context.close()


def test_unsaved_comments_have_their_own_close_warning(editor):
    task, _service = open_review_diagram(editor)
    assert prevented_unload(editor) is False, "nothing pending: no warning at all"
    comment(editor, task, "Pendente")
    assert editor.evaluate("isDirty") is False
    assert prevented_unload(editor) is True, "the diagram is clean, yet unsaved comments warn"
    editor.evaluate("saveReviewFile()")
    assert prevented_unload(editor) is False, "saved comments, no warning"
    # the diagram's own warning stays independent of the comments
    editor.evaluate(
        "id => modeler.get('modeling').updateProperties(modeler.get('elementRegistry').get(id), {name: 'Mexi'})", task)
    assert prevented_unload(editor) is True


def test_each_diagram_keeps_its_own_comments(editor):
    task, _service = open_review_diagram(editor, "01-user-onboarding.bpmn")
    comment(editor, task, "Do onboarding")
    assert counter(editor) == (1, 0)
    open_diagram(editor, ROOT / "tests" / "02-credit-card-approval.bpmn")
    assert counter(editor) == (0, 0), "another diagram, another list"
    open_diagram(editor, ROOT / "tests" / "01-user-onboarding.bpmn")
    assert counter(editor) == (1, 0), "and the first one's comments are still there (local draft)"


def test_opening_a_review_file_over_unsaved_comments_asks_first(editor):
    task, _service = open_review_diagram(editor)
    comment(editor, task, "Não perder")
    with answering(editor, accept=False) as questions:
        result = editor.evaluate("loadReviewText('{\"version\": 1, \"comments\": []}', 'x.review.json', null)")
    assert result == {"ok": False, "code": "cancelled"} and "não salvos" in questions[0]
    assert counter(editor) == (1, 0)


@pytest.mark.parametrize("text, code", [
    ("{nao e json", "json-invalid"),
    ('{"comments": []}', "not-review-file"),
    ('{"version": 1}', "not-review-file"),
    ('{"version": 99, "comments": []}', "newer-version"),
])
def test_a_bad_review_file_is_rejected_without_losing_the_current_comments(editor, text, code):
    task, _service = open_review_diagram(editor)
    comment(editor, task, "Fica")
    result = editor.evaluate("t => loadReviewText(t, 'ruim.review.json', null)", text)
    assert result["ok"] is False and result["code"] == code
    assert editor.is_visible("#notice-review-problem")
    assert counter(editor) == (1, 0)
