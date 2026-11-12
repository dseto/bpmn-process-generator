"""
Round 2b hardening tests for the Fase 2 editor: overlap between the toast and the
minimap, the responsible field on every kind of activity, and the Fase 2 features
running in the self-contained (vendored) mode with the network blocked.

Like the other browser tests these need bpmn-js (downloaded once from the CDN to
build the vendored editor) and FAIL, instead of skipping, when it is unavailable.
"""
import importlib

import pytest

import generate_editor_html
from test_editor_ui_phase2 import (
    EDITOR_URL,
    EVENTS_DIAGRAM,
    NO_PICKERS,
    browser,
    element_id,
    load_xml,
    open_editor,
    page,
    saved_xml,
    select,
    validate_with_tool,
)

CDN = generate_editor_html.CDN_BASE
VENDOR_SOURCES = {
    generate_editor_html.VENDOR_JS: "/bpmn-modeler.production.min.js",
    generate_editor_html.VENDOR_DIAGRAM_CSS: "/assets/diagram-js.css",
    generate_editor_html.VENDOR_BPMN_CSS: "/assets/bpmn-font/css/bpmn.css",
    generate_editor_html.VENDOR_FONT: "/assets/bpmn-font/font/bpmn.woff",
}


def commit(page, selector, value):
    page.fill(selector, value)
    page.evaluate("document.activeElement && document.activeElement.blur()")


def rect(page, selector):
    return page.evaluate(
        "s => { const r = document.querySelector(s).getBoundingClientRect();"
        " return {top: r.top, bottom: r.bottom, left: r.left, right: r.right}; }", selector)


def overlaps(a, b):
    return not (a["right"] <= b["left"] or b["right"] <= a["left"]
                or a["bottom"] <= b["top"] or b["bottom"] <= a["top"])


# ---------------------------------------------------------------------------
# Toast x minimap x bpmn.io mark
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("width,height", [(1440, 800), (800, 600)])
def test_the_toast_does_not_cover_the_minimap(browser, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    try:
        open_editor(page)
        assert page.is_visible("#minimap")
        page.evaluate("showToast('Salvamento cancelado: o arquivo no disco foi alterado.')")
        page.wait_for_selector("#toast.show")
        assert not overlaps(rect(page, "#toast"), rect(page, "#minimap"))
    finally:
        context.close()


def test_the_toast_returns_to_the_corner_when_the_minimap_is_hidden(page):
    open_editor(page)
    page.click("#menu-view-trigger")
    page.click("#menu-minimap")
    page.evaluate("showToast('Aviso')")
    page.wait_for_selector("#toast.show")
    assert page.evaluate("document.getElementById('toast').style.bottom") == ""


def test_the_minimap_does_not_cover_the_bpmn_io_mark(page):
    open_editor(page)
    assert page.locator(".bjs-powered-by").count() == 1, "the bpmn.io mark must stay in the page"
    assert not overlaps(rect(page, "#minimap"), rect(page, ".bjs-powered-by"))
    assert page.is_visible(".bjs-powered-by")


def test_the_panel_explains_a_multiple_selection_and_recovers(page):
    open_editor(page)
    tasks = page.evaluate(
        "modeler.get('elementRegistry').filter(e => /Task$/.test(e.type) && !e.labelTarget).map(e => e.id)")
    select(page, *tasks[:2])
    assert "2 elementos selecionados" in page.inner_text("#prop-hint")
    select(page)
    assert "Selecione um elemento" in page.inner_text("#prop-hint")


def test_the_editor_version_reflects_the_hardening_round():
    parts = tuple(int(part) for part in generate_editor_html.EDITOR_VERSION.split("."))
    assert parts >= (1, 3, 1)


# ---------------------------------------------------------------------------
# F2.11: the responsible field works on every activity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_type", [
    "bpmn:ServiceTask", "bpmn:ScriptTask", "bpmn:BusinessRuleTask", "bpmn:SendTask",
    "bpmn:ReceiveTask", "bpmn:ManualTask", "bpmn:Task", "bpmn:SubProcess", "bpmn:CallActivity",
])
def test_the_responsible_field_is_offered_for_every_activity(page, task_type, tmp_path):
    open_editor(page)
    load_xml(page, EVENTS_DIAGRAM)
    page.evaluate(
        "t => { const el = modeler.get('elementRegistry').get('Task_1');"
        " const r = modeler.get('bpmnReplace').replaceElement(el, {type: t});"
        " modeler.get('selection').select(r); }", task_type)
    assert page.is_visible("#prop-task-fields")
    commit(page, "#prop-assignee", "Equipe de TI")
    xml = saved_xml(page)
    assert "Equipe de TI" in xml
    assert "performer" in xml.lower()
    code, output = validate_with_tool(tmp_path, xml)
    assert code == 0, output

    commit(page, "#prop-assignee", "")
    assert "Equipe de TI" not in saved_xml(page)


def test_the_responsible_field_is_hidden_for_non_activities(page):
    open_editor(page)
    load_xml(page, EVENTS_DIAGRAM)
    for element in ("Start_Timer", "Catch_Msg", "End_Error", "F1"):
        select(page, element)
        assert not page.is_visible("#prop-task-fields"), element


def test_a_user_task_keeps_a_human_performer_and_other_tasks_a_performer(page):
    open_editor(page)
    load_xml(page, EVENTS_DIAGRAM)
    select(page, "Task_1")
    commit(page, "#prop-assignee", "Analista")
    assert "humanPerformer" in saved_xml(page)
    # a role that already exists keeps its kind when the task type changes
    page.evaluate(
        "() => { const el = modeler.get('elementRegistry').get('Task_1');"
        " modeler.get('selection').select(modeler.get('bpmnReplace').replaceElement(el, {type: 'bpmn:ServiceTask'})); }")
    assert page.input_value("#prop-assignee") == "Analista"
    commit(page, "#prop-assignee", "Robo")
    assert "Robo" in saved_xml(page) and "Analista" not in saved_xml(page)

    # a fresh non-human task gets a plain performer
    page.evaluate(
        "() => { const el = modeler.get('elementRegistry').get('Task_1');"
        " modeler.get('selection').select(modeler.get('bpmnReplace').replaceElement(el, {type: 'bpmn:ScriptTask'})); }")
    commit(page, "#prop-assignee", "")
    commit(page, "#prop-assignee", "Motor")
    xml = saved_xml(page)
    assert "<bpmn:performer" in xml and "Motor" in xml


# ---------------------------------------------------------------------------
# Vendored (self-contained) mode, network blocked
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vendored_editor(browser, tmp_path_factory):
    """Build an editor with bpmn-js embedded, from the real bpmn-js release."""
    vendor = tmp_path_factory.mktemp("vendor")
    context = browser.new_context()
    try:
        for name, path in VENDOR_SOURCES.items():
            response = context.request.get(CDN + path, timeout=60000)
            assert response.ok, f"could not download {path} to build the vendored editor"
            (vendor / name).write_bytes(response.body())
    finally:
        context.close()
    html = generate_editor_html.render_editor_html(vendor_dir=vendor)
    target = tmp_path_factory.mktemp("vendored-editor") / "editor.html"
    target.write_text(html, encoding="utf-8")
    return html, target


@pytest.fixture
def offline_page(browser, vendored_editor):
    _, target = vendored_editor
    context = browser.new_context(viewport={"width": 1440, "height": 800})
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    page.errors = []
    page.network = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))

    def block(route):
        page.network.append(route.request.url)
        route.abort()

    context.route("http://**/*", block)
    context.route("https://**/*", block)
    page.goto(target.as_uri())
    page.wait_for_selector("#templates-dialog:not([hidden])", timeout=45000)
    yield page
    context.close()


def test_the_vendored_editor_embeds_bpmn_js_and_declares_it(vendored_editor):
    html, _ = vendored_editor
    assert 'name="bpmn-editor-assets" content="vendored"' in html
    assert "unpkg.com" not in html


def test_the_phase2_editor_code_never_references_the_network():
    html = importlib.reload(generate_editor_html).html_content
    outside_head = html.split("</head>", 1)[1]
    assert "unpkg.com" not in outside_head
    assert "https://" not in outside_head.replace("http://www.w3.org", "")


def test_phase2_features_work_offline_with_the_network_blocked(offline_page):
    page = offline_page
    page.click("#templates-dialog [data-template='lanes']")
    page.wait_for_function("modeler.get('elementRegistry').filter(e => e.type === 'bpmn:Lane').length > 1",
                           timeout=20000)

    # F2.6 pt-BR palette
    titles = page.evaluate("Array.from(document.querySelectorAll('.djs-palette .entry')).map(e => e.title)")
    assert "Criar tarefa" in titles

    # F2.15 minimap
    page.wait_for_selector("#minimap svg rect[data-role='viewport']", timeout=5000)

    # F2.1 menus + F2.13 shortcuts
    page.click("#menu-view-trigger")
    assert page.is_visible("#menu-shortcuts")
    page.click("#menu-shortcuts")
    assert page.is_visible("#shortcuts-dialog") or page.locator("[id*='shortcuts']:visible").count() > 0
    page.keyboard.press("Escape")

    # F2.7 alignment is a single undo step, F2.11 properties
    tasks = page.evaluate(
        "modeler.get('elementRegistry').filter(e => /Task$/.test(e.type) && !e.labelTarget).map(e => e.id)")
    assert len(tasks) >= 2
    select(page, *tasks[:2])
    assert page.is_visible("#btn-align-top")
    page.click("#btn-align-top")
    select(page, tasks[0])
    commit(page, "#prop-assignee", "Equipe")
    assert "Equipe" in saved_xml(page)

    assert page.network == [], f"the vendored editor tried to reach the network: {page.network}"
    assert page.errors == []
