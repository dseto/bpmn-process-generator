"""
Behaviour tests for the BPMN editor, run in a real Chromium (Playwright).

These cover the "do not lose work" round (Fase 1): one shortcut = one undo (B1),
shortcuts that respect focus (B2), font stored in the BPMN DI and undoable (B3/B4),
`beforeunload` only while there are unsaved changes (B5), automatic draft (F1.5),
disk-first loading (B6), changed-on-disk warning and no silent overwrite (F1.7),
and the compatible-types selector (F1.8).

The editor pulls bpmn-js from the CDN unless it was vendored under assets/vendor,
so these tests need either network access or the vendored bundle. They fail (rather
than skip) when bpmn-js cannot be loaded, so that an offline CI is noticed.
"""
import functools
import http.server
import json
import re
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from bpmn_tool import copy_editor_if_needed

ROOT = Path(__file__).resolve().parent.parent
EDITOR = ROOT / "editor.html"
EDITOR_URL = EDITOR.as_uri()
ONBOARDING = ROOT / "tests" / "01-user-onboarding.bpmn"
WITH_LANES = ROOT / "tests" / "06-bus-boarding-process.bpmn"

# Force the download fallback: the native pickers cannot be driven in headless runs.
NO_PICKERS = "window.showSaveFilePicker = undefined; window.showOpenFilePicker = undefined;"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(accept_downloads=True)
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    yield page
    context.close()


def open_editor(page, url=None):
    """Open the editor and wait until a diagram is on the canvas."""
    page.goto(url or f"{EDITOR_URL}?file=01-user-onboarding.bpmn")
    page.wait_for_function(
        "typeof modeler !== 'undefined' && modeler && "
        "modeler.get('elementRegistry').getAll().length > 1",
        timeout=45000,
    )
    return page


def element_id(page, type_name):
    return page.evaluate(
        "t => { const e = modeler.get('elementRegistry').filter(x => x.type === t)[0]; return e && e.id; }",
        type_name,
    )


def select(page, element):
    page.evaluate(
        "id => modeler.get('selection').select(modeler.get('elementRegistry').get(id))", element)


def name_of(page, element):
    return page.evaluate(
        "id => modeler.get('elementRegistry').get(id).businessObject.name || ''", element)


def rename(page, element, text):
    page.evaluate(
        "([id, t]) => modeler.get('modeling').updateLabel(modeler.get('elementRegistry').get(id), t)",
        [element, text],
    )


def wait_until(page, condition, attempts=100):
    """Poll a Python-side condition (e.g. a list filled by a dialog handler)."""
    for _ in range(attempts):
        if condition():
            return
        page.wait_for_timeout(100)
    raise AssertionError("condition not met in time")


def blur(page):
    page.evaluate("document.activeElement && document.activeElement.blur()")


def stack_index(page):
    return page.evaluate("modeler.get('commandStack')._stackIdx")


def saved_xml(page):
    return page.evaluate("modeler.saveXML({format: true}).then(r => r.xml)")


def is_dirty(page):
    return page.evaluate("isDirty")


def font_of(page, element):
    return page.evaluate("id => fontOfElement(modeler.get('elementRegistry').get(id))", element)


# ---------------------------------------------------------------------------
# B1 - one shortcut, one undo/redo
# ---------------------------------------------------------------------------

def test_ctrl_z_undoes_exactly_one_action(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    original = name_of(page, task)
    rename(page, task, "Primeiro")
    rename(page, task, "Segundo")
    blur(page)

    page.keyboard.press("Control+z")

    assert name_of(page, task) == "Primeiro"


def test_ctrl_y_and_ctrl_shift_z_redo_exactly_one_action(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    rename(page, task, "Primeiro")
    rename(page, task, "Segundo")
    rename(page, task, "Terceiro")
    blur(page)
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    assert name_of(page, task) != "Primeiro"

    page.keyboard.press("Control+y")
    assert name_of(page, task) == "Primeiro"

    page.keyboard.press("Control+z")
    page.keyboard.press("Control+Shift+z")
    assert name_of(page, task) == "Primeiro"


def test_ctrl_f_opens_the_search_pad_once(page):
    open_editor(page)
    blur(page)
    page.keyboard.press("Control+f")
    assert page.evaluate("modeler.get('searchPad').isOpen()") is True


# ---------------------------------------------------------------------------
# B2 - shortcuts respect focus
# ---------------------------------------------------------------------------

def test_ctrl_z_in_a_text_field_does_not_undo_another_element(page):
    open_editor(page)
    tasks = page.evaluate(
        "modeler.get('elementRegistry').filter(x => /Task$/.test(x.type)).map(x => x.id)")
    other, edited = tasks[0], tasks[1]
    rename(page, other, "Renomeado antes")
    index_before = stack_index(page)

    select(page, edited)
    page.click("#prop-name")
    page.keyboard.press("End")
    page.keyboard.type("XYZ")
    assert page.input_value("#prop-name").endswith("XYZ")
    page.keyboard.press("Control+z")

    assert stack_index(page) == index_before
    assert name_of(page, other) == "Renomeado antes"
    assert "XYZ" not in page.input_value("#prop-name")


def test_ctrl_b_and_ctrl_i_in_a_text_field_leave_the_element_font_alone(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#prop-name")
    page.keyboard.press("Control+b")
    page.keyboard.press("Control+i")

    assert font_of(page, task) == {"size": 12, "isBold": False, "isItalic": False}
    assert is_dirty(page) is False


def test_ctrl_b_and_ctrl_i_on_the_canvas_style_the_selection(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    blur(page)
    page.keyboard.press("Control+b")
    page.keyboard.press("Control+i")

    assert font_of(page, task) == {"size": 12, "isBold": True, "isItalic": True}


def test_ctrl_s_in_a_text_field_saves_the_typed_text_without_undoing_anything(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#prop-name")
    page.fill("#prop-name", "Nome digitado")
    index_before = stack_index(page)

    with page.expect_download() as download:
        page.keyboard.press("Control+s")

    path = download.value.path()
    assert 'name="Nome digitado"' in Path(path).read_text(encoding="utf-8")
    assert name_of(page, task) == "Nome digitado"
    assert stack_index(page) >= index_before  # nothing was undone
    assert is_dirty(page) is False


# ---------------------------------------------------------------------------
# B3 / B4 - font in the BPMN DI, through the command stack
# ---------------------------------------------------------------------------

def test_opening_a_file_without_font_info_keeps_it_untouched(page):
    open_editor(page)
    assert is_dirty(page) is False
    assert "LabelStyle" not in saved_xml(page)
    assert "dc:Font" not in saved_xml(page)
    task = element_id(page, "bpmn:ServiceTask")
    assert font_of(page, task) == {"size": 12, "isBold": False, "isItalic": False}


def test_bold_italic_and_size_are_written_to_the_bpmn_di(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#btn-font-bold")
    page.click("#btn-font-italic")
    page.select_option("#font-size-select", "16px")

    xml = saved_xml(page)
    assert re.search(r"<bpmndi:BPMNLabelStyle", xml)
    font = re.search(r"<\w+:Font [^>]*>", xml).group(0)
    assert 'isBold="true"' in font and 'isItalic="true"' in font and 'size="16"' in font
    assert re.search(r'<bpmndi:BPMNLabel [^>]*labelStyle="', xml)
    assert is_dirty(page) is True


def test_font_change_is_undoable_redoable_and_marks_the_diagram_dirty(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    assert is_dirty(page) is False
    page.click("#btn-font-bold")
    assert is_dirty(page) is True
    assert page.evaluate("modeler.get('commandStack').canUndo()") is True
    assert font_of(page, task)["isBold"] is True

    blur(page)
    page.keyboard.press("Control+z")
    assert font_of(page, task)["isBold"] is False
    assert "LabelStyle" not in saved_xml(page)

    page.keyboard.press("Control+y")
    assert font_of(page, task)["isBold"] is True
    assert 'isBold="true"' in saved_xml(page)


def test_one_undo_reverts_a_font_change_on_a_multiple_selection(page):
    open_editor(page)
    tasks = page.evaluate(
        "modeler.get('elementRegistry').filter(x => /Task$/.test(x.type)).map(x => x.id)")
    page.evaluate(
        "ids => modeler.get('selection').select(ids.map(i => modeler.get('elementRegistry').get(i)))", tasks)
    page.click("#btn-font-bold")
    assert all(font_of(page, t)["isBold"] for t in tasks)

    page.evaluate("modeler.get('commandStack').undo()")
    assert not any(font_of(page, t)["isBold"] for t in tasks)


def test_going_back_to_the_default_font_leaves_no_label_style_behind(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#btn-font-bold")
    page.click("#btn-font-bold")
    assert "LabelStyle" not in saved_xml(page)


def test_font_survives_save_and_reopen(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.click("#btn-font-bold")
    page.select_option("#font-size-select", "18px")

    with page.expect_download() as download:
        page.click("#btn-save")
    saved = Path(download.value.path()).read_text(encoding="utf-8")
    assert "BPMNLabelStyle" in saved

    page.evaluate("xml => modeler.importXML(xml)", saved)
    assert font_of(page, task) == {"size": 18, "isBold": True, "isItalic": False}

    # and the reopened file is rendered with it, not just remembered
    page.evaluate("applyAllElementFontStyles()")
    weight = page.evaluate(
        "id => getComputedStyle(modeler.get('elementRegistry').getGraphics(id).querySelector('text')).fontWeight",
        task)
    assert weight in ("700", "bold")


def test_font_toolbar_reflects_the_stored_font_of_the_selection(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.select_option("#font-size-select", "14px")
    page.click("#btn-font-bold")
    select(page, element_id(page, "bpmn:EndEvent"))
    assert page.input_value("#font-size-select") == "12px"
    select(page, task)
    assert page.input_value("#font-size-select") == "14px"
    assert "active" in page.get_attribute("#btn-font-bold", "class")


# ---------------------------------------------------------------------------
# B5 - beforeunload only while there is unsaved work
# ---------------------------------------------------------------------------

def beforeunload_prevented(page):
    return page.evaluate(
        "() => { const e = new Event('beforeunload', {cancelable: true}); "
        "window.dispatchEvent(e); return e.defaultPrevented; }")


def test_beforeunload_is_active_only_with_unsaved_changes(page):
    open_editor(page)
    assert beforeunload_prevented(page) is False

    rename(page, element_id(page, "bpmn:ServiceTask"), "Alterado")
    assert beforeunload_prevented(page) is True

    with page.expect_download():
        page.click("#btn-save")
    assert beforeunload_prevented(page) is False


# ---------------------------------------------------------------------------
# F1.5 - automatic draft
# ---------------------------------------------------------------------------

def draft_keys(page):
    return page.evaluate(
        "Object.keys(localStorage).filter(k => k.indexOf('bpmn-editor-draft:') === 0)")


def test_draft_is_stored_offered_on_reopen_recovered_and_dropped_on_save(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    rename(page, task, "Texto do rascunho")
    page.wait_for_function(
        "Object.keys(localStorage).some(k => k.indexOf('bpmn-editor-draft:') === 0)", timeout=10000)

    page.on("dialog", lambda dialog: dialog.accept())
    page.reload()
    page.wait_for_selector("#notice-draft", timeout=45000)
    assert name_of(page, task) != "Texto do rascunho"  # offered, not forced

    page.click("#notice-draft button:has-text('Recuperar')")
    page.wait_for_function(
        "id => modeler.get('elementRegistry').get(id).businessObject.name === 'Texto do rascunho'", arg=task)
    assert is_dirty(page) is True

    with page.expect_download():
        page.click("#btn-save")
    assert draft_keys(page) == []


def test_discarding_the_offered_draft_removes_it(page):
    open_editor(page)
    rename(page, element_id(page, "bpmn:ServiceTask"), "Rascunho descartavel")
    page.wait_for_function(
        "Object.keys(localStorage).some(k => k.indexOf('bpmn-editor-draft:') === 0)", timeout=10000)
    page.on("dialog", lambda dialog: dialog.accept())
    page.reload()
    page.wait_for_selector("#notice-draft", timeout=45000)
    page.click("#notice-draft button:has-text('Descartar')")
    assert draft_keys(page) == []
    assert page.locator("#notice-draft").count() == 0


def test_editor_keeps_working_when_local_storage_is_unavailable(browser):
    context = browser.new_context(accept_downloads=True)
    context.add_init_script(NO_PICKERS)
    context.add_init_script(
        "const boom = () => { throw new DOMException('blocked', 'SecurityError'); };"
        "Storage.prototype.setItem = boom; Storage.prototype.getItem = boom;"
        "Storage.prototype.removeItem = boom;")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    rename(page, task, "Sem storage")
    page.wait_for_timeout(1200)  # past the autosave debounce
    assert is_dirty(page) is True
    assert name_of(page, task) == "Sem storage"
    with page.expect_download():
        page.click("#btn-save")
    assert is_dirty(page) is False
    assert errors == []
    context.close()


# ---------------------------------------------------------------------------
# B6 / F1.7 - disk first, and never overwrite silently
# ---------------------------------------------------------------------------

@pytest.fixture
def served_project(tmp_path):
    """A project folder with the editor and one diagram, served over http://."""
    diagram = tmp_path / "processo.bpmn"
    diagram.write_text(ONBOARDING.read_text(encoding="utf-8"), encoding="utf-8")
    copy_editor_if_needed(tmp_path, diagram)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *args, **kwargs: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield tmp_path, diagram, f"http://127.0.0.1:{server.server_address[1]}/editor.html"
    server.shutdown()
    server.server_close()


def renamed_on_disk(diagram, old, new):
    text = diagram.read_text(encoding="utf-8")
    assert old in text
    diagram.write_text(text.replace(old, new), encoding="utf-8")


def test_project_editor_loads_the_disk_file_before_the_embedded_snapshot(page, served_project):
    _, diagram, url = served_project
    renamed_on_disk(diagram, "Validate registration data", "Nome so no disco")

    open_editor(page, url)

    names = page.evaluate(
        "modeler.get('elementRegistry').getAll().map(e => e.businessObject && e.businessObject.name)")
    assert "Nome so no disco" in names
    assert page.locator("#notice-snapshot-stale").count() == 1
    assert is_dirty(page) is False


def test_project_editor_without_changes_on_disk_shows_no_stale_warning(page, served_project):
    _, _, url = served_project
    open_editor(page, url)
    assert page.locator("#notice-snapshot-stale").count() == 0
    assert page.locator("#notice-snapshot-only").count() == 0


def test_snapshot_fallback_warns_when_the_disk_cannot_be_read(page, served_project):
    tmp_path, _, _ = served_project
    open_editor(page, (tmp_path / "editor.html").as_uri())  # file://: fetch is blocked
    assert page.locator("#notice-snapshot-only").count() == 1


def test_a_change_on_disk_is_announced_and_can_be_reloaded(page, served_project):
    _, diagram, url = served_project
    open_editor(page, url)
    renamed_on_disk(diagram, "Validate registration data", "Regenerado pela skill")

    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.wait_for_selector("#notice-disk-changed", timeout=10000)
    names = page.evaluate(
        "modeler.get('elementRegistry').getAll().map(e => e.businessObject && e.businessObject.name)")
    assert "Regenerado pela skill" not in names  # never swapped silently

    page.click("#notice-disk-changed button:has-text('Recarregar')")
    page.wait_for_function(
        "modeler.get('elementRegistry').getAll().some(e => e.businessObject && "
        "e.businessObject.name === 'Regenerado pela skill')", timeout=10000)
    assert is_dirty(page) is False


def test_keeping_my_version_dismisses_the_disk_change_notice(page, served_project):
    _, diagram, url = served_project
    open_editor(page, url)
    renamed_on_disk(diagram, "Validate registration data", "Outra versao")
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.wait_for_selector("#notice-disk-changed", timeout=10000)
    page.click("#notice-disk-changed button:has-text('Manter')")
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.wait_for_timeout(300)
    assert page.locator("#notice-disk-changed").count() == 0
    names = page.evaluate(
        "modeler.get('elementRegistry').getAll().map(e => e.businessObject && e.businessObject.name)")
    assert "Outra versao" not in names


FAKE_HANDLE = """
([diskText]) => {
  window.__writes = [];
  window.__disk = diskText;
  currentFileHandle = {
    name: 'processo.bpmn',
    getFile: async () => new File([window.__disk], 'processo.bpmn'),
    createWritable: async () => ({
      write: async (data) => { window.__writes.push(data); window.__disk = data; },
      close: async () => {}
    })
  };
  lastDiskText = diskText;
}
"""


def test_saving_over_a_file_that_changed_on_disk_asks_before_overwriting(page):
    open_editor(page)
    page.evaluate(FAKE_HANDLE, [ONBOARDING.read_text(encoding="utf-8")])
    rename(page, element_id(page, "bpmn:ServiceTask"), "Minha edicao")
    page.evaluate("window.__disk = window.__disk + '<!-- versao mais nova -->'")

    seen = []

    def decline(dialog):
        seen.append(dialog.message)
        dialog.dismiss()

    page.once("dialog", decline)
    page.click("#btn-save")
    wait_until(page, lambda: seen)

    assert "SOBRESCREVER" in seen[0]
    assert page.evaluate("window.__writes.length") == 0
    assert is_dirty(page) is True

    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#btn-save")
    page.wait_for_function("window.__writes.length === 1", timeout=10000)
    assert is_dirty(page) is False


def test_saving_over_an_unchanged_file_does_not_prompt(page):
    open_editor(page)
    page.evaluate(FAKE_HANDLE, [ONBOARDING.read_text(encoding="utf-8")])
    rename(page, element_id(page, "bpmn:ServiceTask"), "Minha edicao")
    prompts = []
    page.on("dialog", lambda dialog: (prompts.append(dialog.message), dialog.dismiss()))
    page.click("#btn-save")
    page.wait_for_function("window.__writes.length === 1", timeout=10000)
    assert prompts == []


def test_opening_another_file_with_unsaved_changes_asks_first(page):
    open_editor(page)
    rename(page, element_id(page, "bpmn:ServiceTask"), "Nao salvo")
    seen = []

    def decline(dialog):
        seen.append(dialog.message)
        dialog.dismiss()

    page.once("dialog", decline)
    page.click("#btn-open")
    wait_until(page, lambda: seen)
    assert "não salvas" in seen[0]
    assert name_of(page, element_id(page, "bpmn:ServiceTask")) == "Nao salvo"


# ---------------------------------------------------------------------------
# F1.8 - compatible types only
# ---------------------------------------------------------------------------

def type_options(page):
    return page.evaluate("Array.from(document.querySelectorAll('#prop-type option')).map(o => o.value)")


def test_task_shows_task_types_with_the_current_one_selected(page):
    open_editor(page)
    select(page, element_id(page, "bpmn:UserTask"))
    assert page.is_visible("#prop-type")
    assert page.input_value("#prop-type") == "bpmn:UserTask"
    options = type_options(page)
    assert "bpmn:ServiceTask" in options
    assert not any("Gateway" in value for value in options)


def test_gateway_shows_gateway_types_only(page):
    open_editor(page, f"{EDITOR_URL}?file=02-credit-card-approval.bpmn")
    gateway = page.evaluate(
        "modeler.get('elementRegistry').filter(x => /Gateway$/.test(x.type))[0].id")
    select(page, gateway)
    options = type_options(page)
    assert page.is_visible("#prop-type")
    assert options and all("Gateway" in value for value in options)
    assert page.input_value("#prop-type") in options


@pytest.mark.parametrize("type_name", ["bpmn:StartEvent", "bpmn:EndEvent"])
def test_events_have_no_type_selector(page, type_name):
    open_editor(page)
    select(page, element_id(page, type_name))
    assert page.is_visible("#prop-body")
    assert not page.is_visible("#prop-type")


def test_lane_has_no_type_selector(page):
    open_editor(page, f"{EDITOR_URL}?file=06-bus-boarding-process.bpmn")
    select(page, element_id(page, "bpmn:Lane"))
    assert page.is_visible("#prop-body")
    assert not page.is_visible("#prop-type")


def test_changing_the_type_replaces_the_element(page):
    open_editor(page)
    task = element_id(page, "bpmn:ServiceTask")
    select(page, task)
    page.select_option("#prop-type", "bpmn:UserTask")
    assert page.evaluate(
        "modeler.get('selection').get()[0].type") == "bpmn:UserTask"
    assert page.input_value("#prop-type") == "bpmn:UserTask"


def test_no_script_errors_were_raised(page):
    open_editor(page)
    select(page, element_id(page, "bpmn:ServiceTask"))
    page.click("#btn-font-bold")
    assert page.errors == []
    json.dumps(page.errors)
