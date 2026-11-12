"""
Behaviour tests for Fase 2 of the BPMN editor ("mais intuitivo"), run in a real
Chromium through Playwright: menus and toolbar (F2.1-F2.5), pt-BR labels (F2.6),
alignment (F2.7-F2.9), properties panel (F2.10-F2.12), shortcuts help and
templates (F2.13-F2.14) and zoom/minimap (F2.15).

Like tests/test_editor_behavior.py these need bpmn-js (CDN or assets/vendor) and
FAIL, instead of skipping, when it cannot be loaded.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
EDITOR_URL = (ROOT / "editor.html").as_uri()
BPMN_TOOL = ROOT / "scripts" / "bpmn_tool.py"
NO_PICKERS = "window.showSaveFilePicker = undefined; window.showOpenFilePicker = undefined;"
LANES_FILE = "06-bus-boarding-process.bpmn"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 800})
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    yield page
    context.close()


def open_editor(page, file="01-user-onboarding.bpmn"):
    page.goto(f"{EDITOR_URL}?file={file}")
    page.wait_for_function(
        "typeof modeler !== 'undefined' && modeler && "
        "modeler.get('elementRegistry').getAll().length > 1",
        timeout=45000,
    )
    return page


def load_xml(page, xml, name="teste.bpmn"):
    page.evaluate("([x, n]) => loadDiagram(x, n, null)", [xml, name])
    page.wait_for_function("modeler.get('elementRegistry').getAll().length > 1")


def element_id(page, type_name, index=0):
    return page.evaluate(
        "([t, i]) => { const e = modeler.get('elementRegistry').filter(x => x.type === t && !x.labelTarget)[i]; return e && e.id; }",
        [type_name, index],
    )


def select(page, *ids):
    page.evaluate(
        "ids => modeler.get('selection').select(ids.map(id => modeler.get('elementRegistry').get(id)))",
        list(ids),
    )


def saved_xml(page):
    return page.evaluate("modeler.saveXML({format: true}).then(r => r.xml)")


def stack_index(page):
    """Undo steps on the stack: nested commands of one action share a single action id."""
    return page.evaluate(
        "(() => { const cs = modeler.get('commandStack');"
        " return new Set(cs._stack.slice(0, cs._stackIdx + 1).map(e => e.id)).size; })()")


def bounds(page, element):
    return page.evaluate(
        "id => { const e = modeler.get('elementRegistry').get(id); return {x: e.x, y: e.y, w: e.width, h: e.height}; }",
        element,
    )


def validate_with_tool(tmp_path, xml):
    target = tmp_path / "check.bpmn"
    target.write_text(xml, encoding="utf-8")
    result = subprocess.run([sys.executable, str(BPMN_TOOL), "validate", str(target)],
                            capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def linear_diagram(task_count, process_name="Grande"):
    """A sequential process of `task_count` user tasks, 150 px apart."""
    nodes = ['<bpmn:startEvent id="Start_1" name="Inicio"/>']
    flows, shapes, edges = [], [], []
    prev = "Start_1"
    shapes.append('<bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1"><omgdc:Bounds x="100" y="102" width="36" height="36"/></bpmndi:BPMNShape>')
    prev_right = 136
    for i in range(1, task_count + 1):
        tid = f"Task_{i}"
        x = 100 + 150 * i
        nodes.append(f'<bpmn:userTask id="{tid}" name="Etapa {i}"/>')
        shapes.append(f'<bpmndi:BPMNShape id="{tid}_di" bpmnElement="{tid}"><omgdc:Bounds x="{x}" y="80" width="100" height="80"/></bpmndi:BPMNShape>')
        fid = f"Flow_{i}"
        flows.append(f'<bpmn:sequenceFlow id="{fid}" sourceRef="{prev}" targetRef="{tid}"/>')
        edges.append(f'<bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}"><omgdi:waypoint x="{prev_right}" y="120"/><omgdi:waypoint x="{x}" y="120"/></bpmndi:BPMNEdge>')
        prev, prev_right = tid, x + 100
    end_x = prev_right + 50
    nodes.append('<bpmn:endEvent id="End_1" name="Fim"/>')
    flows.append(f'<bpmn:sequenceFlow id="Flow_end" sourceRef="{prev}" targetRef="End_1"/>')
    shapes.append(f'<bpmndi:BPMNShape id="End_1_di" bpmnElement="End_1"><omgdc:Bounds x="{end_x}" y="102" width="36" height="36"/></bpmndi:BPMNShape>')
    edges.append(f'<bpmndi:BPMNEdge id="Flow_end_di" bpmnElement="Flow_end"><omgdi:waypoint x="{prev_right}" y="120"/><omgdi:waypoint x="{end_x}" y="120"/></bpmndi:BPMNEdge>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
        'xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC" '
        'xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI" id="Defs_1" targetNamespace="http://bpmn.io/schema/bpmn">'
        f'<bpmn:process id="Process_Big" name="{process_name}" isExecutable="false">'
        + "".join(nodes) + "".join(flows) +
        '</bpmn:process><bpmndi:BPMNDiagram id="D1"><bpmndi:BPMNPlane id="P1" bpmnElement="Process_Big">'
        + "".join(shapes) + "".join(edges) + '</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>'
    )


EVENTS_DIAGRAM = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
  id="Defs_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_Eventos" name="Eventos" isExecutable="false">
    <bpmn:startEvent id="Start_Timer" name="Todo dia">
      <bpmn:outgoing>F1</bpmn:outgoing>
      <bpmn:timerEventDefinition id="Timer_1"/>
    </bpmn:startEvent>
    <bpmn:userTask id="Task_1" name="Analisar">
      <bpmn:incoming>F1</bpmn:incoming>
      <bpmn:outgoing>F2</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:intermediateCatchEvent id="Catch_Msg" name="Aguardar resposta">
      <bpmn:incoming>F2</bpmn:incoming>
      <bpmn:outgoing>F3</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MsgDef_1"/>
    </bpmn:intermediateCatchEvent>
    <bpmn:endEvent id="End_Error" name="Falhou">
      <bpmn:incoming>F3</bpmn:incoming>
      <bpmn:errorEventDefinition id="ErrDef_1"/>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="F1" sourceRef="Start_Timer" targetRef="Task_1"/>
    <bpmn:sequenceFlow id="F2" sourceRef="Task_1" targetRef="Catch_Msg"/>
    <bpmn:sequenceFlow id="F3" sourceRef="Catch_Msg" targetRef="End_Error"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="D1">
    <bpmndi:BPMNPlane id="P1" bpmnElement="Process_Eventos">
      <bpmndi:BPMNShape id="Start_Timer_di" bpmnElement="Start_Timer"><omgdc:Bounds x="100" y="102" width="36" height="36"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_1_di" bpmnElement="Task_1"><omgdc:Bounds x="200" y="80" width="100" height="80"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Catch_Msg_di" bpmnElement="Catch_Msg"><omgdc:Bounds x="360" y="102" width="36" height="36"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="End_Error_di" bpmnElement="End_Error"><omgdc:Bounds x="460" y="102" width="36" height="36"/></bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="F1_di" bpmnElement="F1"><omgdi:waypoint x="136" y="120"/><omgdi:waypoint x="200" y="120"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F2_di" bpmnElement="F2"><omgdi:waypoint x="300" y="120"/><omgdi:waypoint x="360" y="120"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F3_di" bpmnElement="F3"><omgdi:waypoint x="396" y="120"/><omgdi:waypoint x="460" y="120"/></bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""

HEADER_CONTROLS = (
    "btn-save", "btn-undo", "btn-redo", "btn-zoom-out", "btn-zoom-in", "btn-props-toggle",
    "menu-file-trigger", "menu-edit-trigger", "menu-view-trigger",
)
# Every function the Fase 1 toolbar offered must still be reachable.
LEGACY_FUNCTIONS = (
    "btn-open", "btn-save", "btn-save-as", "btn-new", "btn-undo", "btn-redo", "btn-route-90",
    "btn-search", "btn-zoom-out", "btn-zoom-in", "btn-zoom-fit", "btn-zoom-reset",
    "btn-export-svg", "btn-export-png", "btn-export-pdf", "btn-props-toggle",
    "preset-select", "font-size-select", "btn-font-bold", "btn-font-italic",
    "btn-align-left", "btn-align-middle", "btn-distribute-h",
)


# ---------------------------------------------------------------------------
# F2.1 menus
# ---------------------------------------------------------------------------

def test_the_toolbar_has_file_edit_and_view_menus(page):
    open_editor(page)
    for label, trigger in (("Arquivo", "menu-file-trigger"), ("Editar", "menu-edit-trigger"),
                           ("Exibir", "menu-view-trigger")):
        assert page.inner_text(f"#{trigger}").strip() == label
        assert page.get_attribute(f"#{trigger}", "aria-haspopup") == "menu"
        assert page.get_attribute(f"#{trigger}", "aria-expanded") == "false"


def test_the_file_menu_lists_open_save_save_as_new_and_export(page):
    open_editor(page)
    page.click("#menu-file-trigger")
    assert page.get_attribute("#menu-file-trigger", "aria-expanded") == "true"
    for item in ("btn-open", "menu-save", "btn-save-as", "btn-new",
                 "btn-export-svg", "btn-export-png", "btn-export-pdf"):
        assert page.is_visible(f"#{item}"), item


def test_the_edit_and_view_menus_hold_undo_redo_search_zoom_minimap_and_help(page):
    open_editor(page)
    page.click("#menu-edit-trigger")
    for item in ("menu-undo", "menu-redo", "btn-search", "btn-route-90"):
        assert page.is_visible(f"#{item}"), item
    page.click("#menu-view-trigger")
    for item in ("menu-zoom-in", "menu-zoom-out", "btn-zoom-fit", "btn-zoom-reset",
                 "menu-minimap", "menu-shortcuts"):
        assert page.is_visible(f"#{item}"), item
    # opening a menu closes the previous one
    assert not page.is_visible("#menu-edit-list")


def test_no_function_of_the_old_toolbar_was_lost(page):
    open_editor(page)
    select_id = element_id(page, "bpmn:ServiceTask")
    select(page, select_id)
    for control in LEGACY_FUNCTIONS:
        assert page.query_selector(f"#{control}") is not None, f"{control} disappeared"
    # the common actions stay on the bar itself
    for control in ("btn-save", "btn-undo", "btn-redo", "btn-zoom-in", "btn-zoom-out"):
        assert page.is_visible(f"#{control}"), control


def test_a_menu_closes_when_clicking_outside(page):
    open_editor(page)
    page.click("#menu-file-trigger")
    assert page.is_visible("#menu-file-list")
    page.mouse.click(700, 500)
    assert not page.is_visible("#menu-file-list")
    assert page.get_attribute("#menu-file-trigger", "aria-expanded") == "false"


def test_a_menu_closes_after_choosing_an_item(page):
    open_editor(page)
    page.click("#menu-view-trigger")
    page.click("#menu-zoom-in")
    assert not page.is_visible("#menu-view-list")


def test_menus_open_and_navigate_by_keyboard(page):
    open_editor(page)
    page.focus("#menu-edit-trigger")
    page.keyboard.press("Enter")
    assert page.is_visible("#menu-edit-list")
    assert page.evaluate("document.activeElement.id") == "menu-undo" or \
        page.evaluate("document.activeElement.getAttribute('role')") == "menuitem"
    first = page.evaluate("document.activeElement.id")
    page.keyboard.press("ArrowDown")
    second = page.evaluate("document.activeElement.id")
    assert second and second != first
    page.keyboard.press("Escape")
    assert not page.is_visible("#menu-edit-list")
    assert page.evaluate("document.activeElement.id") == "menu-edit-trigger"
    # Space opens too, ArrowDown on the trigger as well
    page.keyboard.press("Space")
    assert page.is_visible("#menu-edit-list")
    page.keyboard.press("Escape")
    page.keyboard.press("ArrowDown")
    assert page.is_visible("#menu-edit-list")


def test_keyboard_activation_of_a_menu_item_runs_the_action(page):
    open_editor(page)
    page.focus("#menu-view-trigger")
    page.keyboard.press("Enter")
    # first item is "Aumentar zoom"
    before = page.evaluate("modeler.get('canvas').zoom()")
    page.keyboard.press("Enter")
    assert page.evaluate("modeler.get('canvas').zoom()") > before
    assert not page.is_visible("#menu-view-list")


def test_existing_shortcuts_still_work_after_the_reorganisation(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    page.evaluate("id => modeler.get('modeling').updateLabel(modeler.get('elementRegistry').get(id), 'Novo nome')", task)
    page.keyboard.press("Control+z")
    assert page.evaluate(
        "id => modeler.get('elementRegistry').get(id).businessObject.name", task) != "Novo nome"


# ---------------------------------------------------------------------------
# F2.2 contextual toolbar
# ---------------------------------------------------------------------------

def test_the_contextual_toolbar_only_exists_with_a_selection(page):
    open_editor(page)
    assert not page.is_visible("#context-toolbar")
    select(page, element_id(page, "bpmn:ServiceTask"))
    assert page.is_visible("#context-toolbar")
    for control in ("font-size-select", "btn-font-bold", "btn-font-italic"):
        assert page.is_visible(f"#{control}")
    assert page.locator("#context-toolbar .color-dot").count() == 7
    page.evaluate("modeler.get('selection').select([])")
    assert not page.is_visible("#context-toolbar")


def test_the_contextual_toolbar_offers_the_compatible_types(page):
    open_editor(page)
    select(page, element_id(page, "bpmn:ServiceTask"))
    assert page.is_visible("#ctx-type")
    assert page.input_value("#ctx-type") == "bpmn:ServiceTask"
    page.select_option("#ctx-type", "bpmn:UserTask")
    assert page.evaluate("modeler.get('selection').get()[0].type") == "bpmn:UserTask"
    select(page, element_id(page, "bpmn:StartEvent"))
    assert not page.is_visible("#ctx-type")


def test_alignment_appears_only_for_a_multiple_selection(page):
    open_editor(page)
    tasks = page.evaluate(
        "modeler.get('elementRegistry').filter(e => /Task$/.test(e.type) && !e.labelTarget).map(e => e.id)")
    select(page, tasks[0])
    assert not page.is_visible("#btn-align-left")
    select(page, tasks[0], tasks[1])
    assert page.is_visible("#btn-align-left")
    assert page.is_visible("#btn-distribute-v")


def test_picking_a_color_from_the_contextual_toolbar_colors_the_selection(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#context-toolbar .color-dot[aria-label='Cor: Verde']")
    assert 'bioc:fill="#dcfce7"' in saved_xml(page)
    assert page.get_attribute("#context-toolbar .color-dot[aria-label='Cor: Verde']", "aria-pressed") == "true"
    assert page.get_attribute("#context-toolbar .color-dot[aria-label='Cor: Azul']", "aria-pressed") == "false"


# ---------------------------------------------------------------------------
# F2.3 footer zoom
# ---------------------------------------------------------------------------

def test_the_footer_shows_the_live_zoom_percentage(page):
    open_editor(page)
    page.evaluate("modeler.get('canvas').zoom(1.0)")
    assert page.inner_text("#zoom-percent").strip() == "100%"
    page.evaluate("modeler.get('canvas').zoom(0.5)")
    assert page.inner_text("#zoom-percent").strip() == "50%"
    page.click("#btn-zoom-in")
    assert page.inner_text("#zoom-percent").strip() == "62%" or page.inner_text("#zoom-percent").strip() == "63%"


def test_fit_to_selection_zooms_into_the_selection(page):
    open_editor(page)
    page.evaluate("modeler.get('canvas').zoom(0.4)")
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#btn-zoom-selection")
    zoom = page.evaluate("modeler.get('canvas').zoom()")
    assert zoom > 0.9
    box = page.evaluate(
        "id => { const v = modeler.get('canvas').viewbox(); const e = modeler.get('elementRegistry').get(id);"
        " return v.x <= e.x && v.y <= e.y && v.x + v.width >= e.x + e.width && v.y + v.height >= e.y + e.height; }",
        task)
    assert box is True


def test_fit_without_selection_fits_the_whole_diagram(page):
    open_editor(page)
    page.evaluate("modeler.get('selection').select([])")
    page.evaluate("modeler.get('canvas').zoom(3.0)")
    page.click("#btn-zoom-selection")
    inside = page.evaluate(
        "(() => { const v = modeler.get('canvas').viewbox(); const i = v.inner;"
        " return v.x <= i.x && v.y <= i.y && v.x + v.width >= i.x + i.width && v.y + v.height >= i.y + i.height; })()")
    assert inside is True


# ---------------------------------------------------------------------------
# F2.4 accessibility
# ---------------------------------------------------------------------------

ACCESSIBLE_NAME_JS = """
() => {
  const controls = document.querySelectorAll(
    '#app-header button, #app-header select, #context-toolbar button, #context-toolbar select, '
    + '.menu-list button, .menu-list select, #status-footer button');
  const missing = [];
  controls.forEach(el => {
    let name = (el.getAttribute('aria-label') || '').trim();
    if (!name && el.getAttribute('aria-labelledby')) name = 'labelled';
    if (!name && el.id && document.querySelector('label[for="' + el.id + '"]')) name = 'label';
    if (!name) name = (el.textContent || '').replace(/[^A-Za-z0-9\\u00C0-\\u017F]/g, '').trim();
    if (!name) missing.push(el.id || el.className || el.tagName);
  });
  return {count: controls.length, missing};
}
"""


def test_every_toolbar_control_has_an_accessible_name(page):
    open_editor(page)
    result = page.evaluate(ACCESSIBLE_NAME_JS)
    assert result["count"] >= 30
    assert result["missing"] == []


def test_colors_are_buttons_with_names_and_pressed_state(page):
    open_editor(page)
    dots = page.query_selector_all(".color-dot")
    assert len(dots) == 7
    for dot in dots:
        assert dot.evaluate("el => el.tagName") == "BUTTON"
        assert dot.get_attribute("aria-label").startswith("Cor: ")
        assert dot.get_attribute("aria-pressed") in ("true", "false")
        assert dot.evaluate("el => el.tabIndex") >= 0


def test_toggle_buttons_expose_their_state(page):
    open_editor(page)
    select(page, element_id(page, "bpmn:ServiceTask"))
    assert page.get_attribute("#btn-font-bold", "aria-pressed") == "false"
    page.click("#btn-font-bold")
    assert page.get_attribute("#btn-font-bold", "aria-pressed") == "true"


def test_the_toolbar_controls_are_keyboard_operable(page):
    open_editor(page)
    focusable = page.evaluate(
        "Array.from(document.querySelectorAll('#app-header button, #app-header select')).filter(e => !e.disabled)"
        ".every(e => e.tabIndex >= 0)")
    assert focusable is True
    page.focus("#btn-zoom-in")
    before = page.evaluate("modeler.get('canvas').zoom()")
    page.keyboard.press("Enter")
    assert page.evaluate("modeler.get('canvas').zoom()") > before
    page.focus("#btn-zoom-in")
    outline = page.evaluate(
        "getComputedStyle(document.activeElement).outlineStyle")
    assert outline != "none"


# ---------------------------------------------------------------------------
# F2.5 responsive
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("width", [1440, 1024, 800])
def test_the_toolbar_does_not_break_into_three_rows(browser, width):
    context = browser.new_context(viewport={"width": width, "height": 700})
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    try:
        open_editor(page)
        select(page, element_id(page, "bpmn:ServiceTask"))
        row = page.evaluate("document.getElementById('btn-save').getBoundingClientRect().height")
        header = page.evaluate("document.getElementById('app-header').getBoundingClientRect().height")
        assert header < row * 2 + 40, f"header is {header}px tall at {width}px"
        assert page.evaluate(
            "document.getElementById('app-header').scrollWidth <= document.getElementById('app-header').clientWidth + 1")
        # the contextual bar stays inside the window too
        right = page.evaluate("document.getElementById('context-toolbar').getBoundingClientRect().right")
        assert right <= width + 1
    finally:
        context.close()


# ---------------------------------------------------------------------------
# F2.6 pt-BR
# ---------------------------------------------------------------------------

def test_the_palette_is_translated_to_portuguese(page):
    open_editor(page)
    titles = page.evaluate(
        "Array.from(document.querySelectorAll('.djs-palette .entry')).map(e => e.title)")
    assert "Ativar ferramenta de laço (seleção em área)" in titles
    assert "Criar tarefa" in titles
    assert not any(t.startswith("Create ") or t.startswith("Activate ") for t in titles)


def test_unmapped_terms_fall_back_to_the_original_without_error(page):
    open_editor(page)
    result = page.evaluate(
        "[modeler.get('translate')('Totally unknown term'), modeler.get('translate')('Hello {name}', {name: 'Ana'}),"
        " modeler.get('translate')('Create task')]")
    assert result == ["Totally unknown term", "Hello Ana", "Criar tarefa"]
    assert page.errors == []


def test_the_context_pad_is_translated(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.evaluate("id => modeler.get('contextPad').open(modeler.get('elementRegistry').get(id), true)", task)
    titles = page.evaluate(
        "Array.from(document.querySelectorAll('.djs-context-pad .entry')).map(e => e.title)")
    assert "Excluir" in titles
    assert "Adicionar tarefa" in titles


# ---------------------------------------------------------------------------
# F2.7-F2.9 alignment
# ---------------------------------------------------------------------------

def stagger(page, ids):
    """Move three tasks so that all alignments have something to do."""
    page.evaluate(
        "ids => { const reg = modeler.get('elementRegistry'); const m = modeler.get('modeling');"
        " m.moveElements([reg.get(ids[1])], {x: 0, y: 60}); m.moveElements([reg.get(ids[2])], {x: 40, y: -50}); }",
        ids)


def three_tasks(page):
    return page.evaluate(
        "modeler.get('elementRegistry').filter(e => /Task$/.test(e.type) && !e.labelTarget).map(e => e.id).slice(0, 3)")


ALIGN_CASES = [
    ("btn-align-left", lambda b: b["x"]),
    ("btn-align-right", lambda b: b["x"] + b["w"]),
    ("btn-align-top", lambda b: b["y"]),
    ("btn-align-bottom", lambda b: b["y"] + b["h"]),
    ("btn-align-center", lambda b: b["x"] + b["w"] / 2),
    ("btn-align-middle", lambda b: b["y"] + b["h"] / 2),
]


@pytest.mark.parametrize("button,measure", ALIGN_CASES)
def test_each_alignment_aligns_and_is_one_undo(page, button, measure):
    open_editor(page, "02-credit-card-approval.bpmn")
    ids = three_tasks(page)
    stagger(page, ids)
    select(page, *ids)
    before = [bounds(page, i) for i in ids]
    index = stack_index(page)
    page.click(f"#{button}")
    after = [bounds(page, i) for i in ids]
    assert len({round(measure(b), 1) for b in after}) == 1
    assert after != before
    assert stack_index(page) == index + 1, "alignment must be a single command"
    page.keyboard.press("Control+z")
    assert [bounds(page, i) for i in ids] == before


def test_distribute_vertically_is_one_undo(page):
    open_editor(page, "02-credit-card-approval.bpmn")
    ids = three_tasks(page)
    page.evaluate(
        "ids => { const reg = modeler.get('elementRegistry'); const m = modeler.get('modeling');"
        " m.moveElements([reg.get(ids[0])], {x: 0, y: -100}); m.moveElements([reg.get(ids[1])], {x: 0, y: 80});"
        " m.moveElements([reg.get(ids[2])], {x: 0, y: 200}); }", ids)
    select(page, *ids)
    before = [bounds(page, i) for i in ids]
    index = stack_index(page)
    page.click("#btn-distribute-v")
    assert stack_index(page) == index + 1
    after = sorted((bounds(page, i) for i in ids), key=lambda b: b["y"])
    gaps = [round(after[k + 1]["y"] - (after[k]["y"] + after[k]["h"]), 1) for k in range(2)]
    assert gaps[0] == gaps[1]
    page.keyboard.press("Control+z")
    assert [bounds(page, i) for i in ids] == before


def test_the_center_buttons_name_their_axis(page):
    open_editor(page)
    assert page.get_attribute("#btn-align-center", "aria-label") == "Centro vertical"
    assert page.get_attribute("#btn-align-middle", "aria-label") == "Centro horizontal"
    html = page.content()
    assert "Centralizar" not in html
    for control in ("btn-align-left", "btn-align-right", "btn-align-top", "btn-align-bottom",
                    "btn-align-center", "btn-align-middle", "btn-distribute-h", "btn-distribute-v"):
        assert len(page.get_attribute(f"#{control}", "title")) > 20, control


# ---------------------------------------------------------------------------
# F2.10 live name / documentation
# ---------------------------------------------------------------------------

def test_name_is_applied_while_typing_without_leaving_the_field(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#prop-name")
    page.fill("#prop-name", "")
    page.keyboard.type("Nome digitado")
    page.wait_for_function(
        "id => modeler.get('elementRegistry').get(id).businessObject.name === 'Nome digitado'", arg=task,
        timeout=3000)
    assert page.evaluate("document.activeElement.id") == "prop-name"
    assert page.input_value("#prop-name") == "Nome digitado"


def test_typing_does_not_flood_the_history_and_keeps_the_caret(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#prop-name")
    page.fill("#prop-name", "")
    start = stack_index(page)
    page.keyboard.type("abcdef", delay=500)  # slower than the debounce: applies several times
    page.wait_for_timeout(600)
    assert stack_index(page) - start <= 1, "typing must coalesce into one history step"
    caret = page.evaluate("[document.getElementById('prop-name').selectionStart, document.getElementById('prop-name').value.length]")
    assert caret[0] == caret[1]
    page.keyboard.press("Tab")
    assert stack_index(page) - start <= 1
    # a single Ctrl+Z (outside the field) reverts the whole typing
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("Control+z")
    assert page.evaluate(
        "id => modeler.get('elementRegistry').get(id).businessObject.name", task) != "abcdef"


def test_documentation_is_applied_while_typing(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#prop-documentation")
    page.keyboard.type("Regra importante")
    page.wait_for_function(
        "id => { const d = modeler.get('elementRegistry').get(id).businessObject.documentation;"
        " return d && d[0] && d[0].text === 'Regra importante'; }", arg=task, timeout=3000)
    assert page.evaluate("document.activeElement.id") == "prop-documentation"


def test_pending_typing_is_not_lost_when_the_selection_changes(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#prop-name")
    page.fill("#prop-name", "")
    page.keyboard.type("Rapido")
    select(page, element_id(page, "bpmn:EndEvent"))
    assert page.evaluate(
        "id => modeler.get('elementRegistry').get(id).businessObject.name", task) == "Rapido"


# ---------------------------------------------------------------------------
# F2.11 type specific fields
# ---------------------------------------------------------------------------

def fill_and_commit(page, selector, text):
    page.fill(selector, text)
    page.evaluate("document.activeElement && document.activeElement.blur()")


def test_type_specific_fields_follow_the_selected_element(page):
    open_editor(page)
    load_xml(page, EVENTS_DIAGRAM)
    select(page, "Start_Timer")
    assert page.is_visible("#prop-timer-fields")
    assert not page.is_visible("#prop-message-fields") and not page.is_visible("#prop-error-fields")
    select(page, "Catch_Msg")
    assert page.is_visible("#prop-message-fields") and not page.is_visible("#prop-timer-fields")
    select(page, "End_Error")
    assert page.is_visible("#prop-error-fields")
    select(page, "Task_1")
    assert page.is_visible("#prop-task-fields")
    assert not page.is_visible("#prop-timer-fields")


def test_timer_message_error_and_assignee_are_saved_as_valid_bpmn(page, tmp_path):
    open_editor(page)
    load_xml(page, EVENTS_DIAGRAM)
    select(page, "Start_Timer")
    page.select_option("#prop-timer-type", "timeCycle")
    fill_and_commit(page, "#prop-timer-value", "R/P1D")
    select(page, "Catch_Msg")
    fill_and_commit(page, "#prop-message-name", "Resposta recebida")
    select(page, "End_Error")
    fill_and_commit(page, "#prop-error-code", "ERR_PAGAMENTO")
    select(page, "Task_1")
    fill_and_commit(page, "#prop-assignee", "Analista de credito")

    xml = saved_xml(page)
    assert re.search(r"<bpmn:timeCycle[^>]*>R/P1D</bpmn:timeCycle>", xml)
    assert 'name="Resposta recebida"' in xml and "messageRef=" in xml
    assert 'errorCode="ERR_PAGAMENTO"' in xml and "errorRef=" in xml
    assert "Analista de credito" in xml and "humanPerformer" in xml

    code, output = validate_with_tool(tmp_path, xml)
    assert code == 0, output

    # survives save / reopen
    load_xml(page, xml, "reaberto.bpmn")
    select(page, "Start_Timer")
    assert page.input_value("#prop-timer-type") == "timeCycle"
    assert page.input_value("#prop-timer-value") == "R/P1D"
    select(page, "Catch_Msg")
    assert page.input_value("#prop-message-name") == "Resposta recebida"
    select(page, "End_Error")
    assert page.input_value("#prop-error-code") == "ERR_PAGAMENTO"
    select(page, "Task_1")
    assert page.input_value("#prop-assignee") == "Analista de credito"


def test_creating_a_message_or_error_is_one_undo_step(page):
    open_editor(page)
    load_xml(page, EVENTS_DIAGRAM)
    select(page, "Catch_Msg")
    index = stack_index(page)
    fill_and_commit(page, "#prop-message-name", "Mensagem")
    assert stack_index(page) == index + 1
    page.keyboard.press("Control+z")
    assert "bpmn:message " not in saved_xml(page)


def test_a_lane_has_an_editable_name(page):
    open_editor(page, LANES_FILE)
    lane = element_id(page, "bpmn:Lane")
    select(page, lane)
    fill_and_commit(page, "#prop-name", "Raia renomeada")
    assert page.evaluate(
        "id => modeler.get('elementRegistry').get(id).businessObject.name", lane) == "Raia renomeada"


def test_a_task_can_be_moved_to_another_lane_from_the_panel(page):
    open_editor(page, LANES_FILE)
    task = page.evaluate(
        "modeler.get('elementRegistry').filter(e => /Task$/.test(e.type) && !e.labelTarget)[0].id")
    select(page, task)
    assert page.is_visible("#prop-lane")
    options = page.eval_on_selector_all("#prop-lane option", "els => els.map(e => e.value)")
    assert len(options) >= 2
    current = page.input_value("#prop-lane")
    target = next(o for o in options if o != current)
    page.select_option("#prop-lane", target)
    membership = page.evaluate(
        "([lane, task]) => modeler.get('elementRegistry').get(lane).businessObject.flowNodeRef"
        ".some(r => r.id === task)", [target, task])
    assert membership is True
    assert page.input_value("#prop-lane") == target


# ---------------------------------------------------------------------------
# F2.12 process properties
# ---------------------------------------------------------------------------

def test_without_selection_the_panel_shows_the_process(page):
    open_editor(page)
    page.evaluate("modeler.get('selection').select([])")
    assert page.is_visible("#proc-name")
    assert page.input_value("#proc-id").startswith("Process_")
    assert page.input_value("#proc-name") != ""
    select(page, element_id(page, "bpmn:ServiceTask"))
    assert not page.is_visible("#proc-name")


def test_the_process_name_can_be_edited_and_undone(page):
    open_editor(page)
    page.evaluate("modeler.get('selection').select([])")
    index = stack_index(page)
    page.click("#proc-name")
    page.fill("#proc-name", "")
    page.keyboard.type("Processo renomeado")
    page.evaluate("document.activeElement.blur()")
    assert 'name="Processo renomeado"' in saved_xml(page)
    assert stack_index(page) == index + 1
    page.keyboard.press("Control+z")
    assert 'name="Processo renomeado"' not in saved_xml(page)


# ---------------------------------------------------------------------------
# F2.13 shortcuts help
# ---------------------------------------------------------------------------

def test_question_mark_opens_the_shortcuts_list_and_escape_closes_it(page):
    open_editor(page)
    assert not page.is_visible("#shortcuts-dialog")
    page.keyboard.press("?")
    assert page.is_visible("#shortcuts-dialog")
    assert page.get_attribute("#shortcuts-dialog .dialog", "role") == "dialog"
    assert "Ctrl+S" in page.inner_text("#shortcuts-dialog")
    page.keyboard.press("Escape")
    assert not page.is_visible("#shortcuts-dialog")


def test_question_mark_is_ignored_inside_text_fields(page):
    open_editor(page)
    select(page, element_id(page, "bpmn:ServiceTask"))
    page.click("#prop-name")
    page.fill("#prop-name", "")
    page.keyboard.type("quem?")
    assert not page.is_visible("#shortcuts-dialog")
    assert page.input_value("#prop-name") == "quem?"


def test_the_view_menu_opens_the_shortcuts_list(page):
    open_editor(page)
    page.click("#menu-view-trigger")
    page.click("#menu-shortcuts")
    assert page.is_visible("#shortcuts-dialog")
    page.click("#shortcuts-close")
    assert not page.is_visible("#shortcuts-dialog")


# ---------------------------------------------------------------------------
# F2.14 templates
# ---------------------------------------------------------------------------

TEMPLATE_KEYS = ["linear", "decision", "lanes", "loop"]


def test_new_diagram_offers_the_templates(page):
    open_editor(page)
    page.click("#menu-file-trigger")
    page.click("#btn-new")
    assert page.is_visible("#templates-dialog")
    for key in ["_blank"] + TEMPLATE_KEYS:
        assert page.is_visible(f"#templates-dialog [data-template='{key}']"), key
    page.keyboard.press("Escape")
    assert not page.is_visible("#templates-dialog")


def test_the_start_screen_offers_templates_when_no_file_is_given(page):
    page.goto(EDITOR_URL)
    page.wait_for_selector("#templates-dialog:not([hidden])", timeout=45000)
    assert page.is_visible("#templates-dialog [data-template='linear']")


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_each_template_loads_and_passes_the_embedded_validator(page, key):
    open_editor(page)
    page.click("#menu-file-trigger")
    page.click("#btn-new")
    page.click(f"#templates-dialog [data-template='{key}']")
    page.wait_for_function(
        "modeler.get('elementRegistry').filter(e => e.type === 'bpmn:EndEvent').length > 0", timeout=10000)
    assert not page.is_visible("#templates-dialog")
    page.click("#btn-validate")
    assert page.locator(".validation-finding").count() == 0
    assert page.is_visible(".validation-ok")


def test_the_lane_template_has_lanes_and_the_loop_template_has_a_cycle(page):
    open_editor(page)
    load_xml(page, page.evaluate("TEMPLATES.lanes"))
    assert page.evaluate("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').length") == 2
    load_xml(page, page.evaluate("TEMPLATES.loop"))
    assert page.evaluate(
        "modeler.get('elementRegistry').filter(e => e.type === 'bpmn:ExclusiveGateway').length") == 2


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_each_template_passes_bpmn_tool_validate(page, tmp_path, key):
    open_editor(page)
    xml = page.evaluate("k => TEMPLATES[k]", key)
    code, output = validate_with_tool(tmp_path, xml)
    assert code == 0 and "WARN" not in output, output


def test_choosing_a_template_with_unsaved_changes_asks_first(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    page.evaluate("id => modeler.get('modeling').updateLabel(modeler.get('elementRegistry').get(id), 'Sujo')", task)
    seen = []
    page.once("dialog", lambda dialog: (seen.append(dialog.message), dialog.dismiss()))
    page.click("#menu-file-trigger")
    page.click("#btn-new")
    page.click("#templates-dialog [data-template='linear']")
    page.wait_for_timeout(300)
    assert seen and "não salvas" in seen[0]
    assert page.evaluate("id => modeler.get('elementRegistry').get(id).businessObject.name", task) == "Sujo"


# ---------------------------------------------------------------------------
# F2.15 opening zoom and minimap
# ---------------------------------------------------------------------------

def test_a_large_diagram_opens_at_a_readable_zoom_at_the_start_of_the_flow(page):
    open_editor(page)
    load_xml(page, linear_diagram(40))
    zoom = page.evaluate("modeler.get('canvas').zoom()")
    assert zoom >= 0.55, f"opened at {zoom:.2f}"
    assert page.evaluate(
        "(() => { const v = modeler.get('canvas').viewbox(); const s = modeler.get('elementRegistry').get('Start_1');"
        " return v.x <= s.x && v.x + v.width >= s.x + s.width && v.y <= s.y && v.y + v.height >= s.y + s.height; })()")
    assert page.inner_text("#zoom-percent").strip() == f"{round(zoom * 100)}%"


def test_a_small_diagram_still_opens_fitted_to_the_screen(page):
    open_editor(page)
    zoom = page.evaluate("modeler.get('canvas').zoom()")
    assert 0.6 <= zoom <= 1.0
    inside = page.evaluate(
        "(() => { const v = modeler.get('canvas').viewbox(); const i = v.inner;"
        " return v.x <= i.x && v.y <= i.y && v.x + v.width >= i.x + i.width && v.y + v.height >= i.y + i.height; })()")
    assert inside is True


def test_the_minimap_draws_the_diagram_and_navigates(page):
    open_editor(page)
    load_xml(page, linear_diagram(40))
    page.wait_for_selector("#minimap svg rect[data-role='viewport']", timeout=5000)
    assert page.locator("#minimap svg rect, #minimap svg ellipse").count() > 40
    box = page.evaluate("(() => { const r = document.getElementById('minimap').getBoundingClientRect();"
                        " return {x: r.x, y: r.y, w: r.width, h: r.height}; })()")
    before = page.evaluate("modeler.get('canvas').viewbox().x")
    page.mouse.click(box["x"] + box["w"] - 10, box["y"] + box["h"] / 2)
    after = page.evaluate("modeler.get('canvas').viewbox().x")
    assert after > before + 1000
    # the viewport rectangle follows the canvas
    page.wait_for_function(
        "parseFloat(document.querySelector('#minimap rect[data-role=viewport]').getAttribute('x'))"
        " > 1000", timeout=3000)


def test_the_minimap_can_be_toggled_from_the_view_menu(page):
    open_editor(page)
    assert page.is_visible("#minimap")
    page.click("#menu-view-trigger")
    page.click("#menu-minimap")
    assert not page.is_visible("#minimap")
    assert page.get_attribute("#menu-minimap", "aria-checked") == "false"


def test_no_script_errors_in_phase2_flows(page):
    open_editor(page)
    select(page, element_id(page, "bpmn:ServiceTask"))
    page.click("#menu-view-trigger")
    page.click("#menu-shortcuts")
    page.keyboard.press("Escape")
    page.click("#btn-zoom-selection")
    assert page.errors == []
