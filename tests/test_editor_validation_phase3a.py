"""
Fase 3A of the BPMN editor: live validation (F3.1 to F3.4).

  F3.1  the linter's rules, ported to the editor with the same ids and severities
        (contract test + parity test against `lint_rules.run_rules`);
  F3.2  validation that runs by itself (debounced) and a counter that stays visible;
  F3.3  markers on the canvas that never leak into the XML, the history or the exports;
  F3.4  a "Corrigir" button with a preview, applied as one undo step.

Like the other browser tests these need bpmn-js (CDN or assets/vendor) and FAIL,
instead of skipping, when it cannot be loaded.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import generate_editor_html
import lint_rules
from test_editor_ui_phase2 import (
    EDITOR_URL,
    ROOT,
    browser,
    load_xml,
    open_editor,
    page,
    saved_xml,
    select,
    stack_index,
)

@pytest.fixture(scope="module")
def shared_page(browser):
    """One editor session for the whole module: opening the editor (bpmn-js) dominates a test's cost."""
    from test_editor_ui_phase2 import NO_PICKERS

    context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 800})
    context.add_init_script(NO_PICKERS)
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    open_editor(page)
    yield page
    context.close()


@pytest.fixture
def live(shared_page):
    """The shared session, back to a neutral UI state (panel open, filter on 'Todos', no dialog)."""
    page = shared_page
    page.keyboard.press("Escape")
    page.evaluate(
        "() => { propertiesPanel.classList.remove('hidden'); btnPropsToggle.setAttribute('aria-pressed', 'true');"
        " document.querySelectorAll('.dialog-backdrop').forEach(d => { d.hidden = true; }); }")
    page.evaluate("() => modeler.get('selection').select([])")
    page.click("[data-severity-filter='all']")
    yield page
    assert not page.errors, page.errors


PARITY_FILES = [
    "references/example-broken.bpmn",
    "references/example-complete.bpmn",
    "assets/templates/decision.bpmn",
    "assets/templates/lanes.bpmn",
    "assets/templates/linear.bpmn",
    "assets/templates/loop.bpmn",
    "tests/03-order-fulfillment.bpmn",
    "tests/04-incident-management.bpmn",
    "tests/06-bus-boarding-process.bpmn",
    "tests/movimentacao-frota.bpmn",
]

DEFS_OPEN = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
    'xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC" '
    'xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI" '
    'id="Defs_1" targetNamespace="http://bpmn.io/schema/bpmn">'
)


def shape(element_id, x, y, w=100, h=80):
    return (f'<bpmndi:BPMNShape id="{element_id}_di" bpmnElement="{element_id}">'
            f'<omgdc:Bounds x="{x}" y="{y}" width="{w}" height="{h}"/></bpmndi:BPMNShape>')


def edge(flow_id, x1, y1, x2, y2):
    return (f'<bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
            f'<omgdi:waypoint x="{x1}" y="{y1}"/><omgdi:waypoint x="{x2}" y="{y2}"/></bpmndi:BPMNEdge>')


def diagram(body, shapes, edges):
    return (DEFS_OPEN + f'<bpmn:process id="Process_T" name="Teste" isExecutable="false">{body}</bpmn:process>'
            '<bpmndi:BPMNDiagram id="D1"><bpmndi:BPMNPlane id="P1" bpmnElement="Process_T">'
            + "".join(shapes) + "".join(edges) + '</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>')


# A clean three-node process: no findings at all.
CLEAN = diagram(
    '<bpmn:startEvent id="Start_Inicio" name="Inicio"><bpmn:outgoing>Flow_1</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:userTask id="Task_Analisar" name="Analisar pedido"><bpmn:incoming>Flow_1</bpmn:incoming>'
    '<bpmn:outgoing>Flow_2</bpmn:outgoing></bpmn:userTask>'
    '<bpmn:endEvent id="End_Fim" name="Fim"><bpmn:incoming>Flow_2</bpmn:incoming></bpmn:endEvent>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_Inicio" targetRef="Task_Analisar"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Analisar" targetRef="End_Fim"/>',
    [shape("Start_Inicio", 100, 102, 36, 36), shape("Task_Analisar", 200, 80), shape("End_Fim", 400, 102, 36, 36)],
    [edge("Flow_1", 136, 120, 200, 120), edge("Flow_2", 300, 120, 400, 120)],
)

# The same process with a repeated flow (and a default pointing at it), and a
# task whose <incoming> list lies about its flows.
DUPLICATED = diagram(
    '<bpmn:startEvent id="Start_Inicio" name="Inicio"><bpmn:outgoing>Flow_1</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:userTask id="Task_Analisar" name="Analisar pedido"><bpmn:incoming>Flow_1</bpmn:incoming>'
    '<bpmn:incoming>Flow_1b</bpmn:incoming><bpmn:outgoing>Flow_2</bpmn:outgoing></bpmn:userTask>'
    '<bpmn:endEvent id="End_Fim" name="Fim"><bpmn:incoming>Flow_2</bpmn:incoming></bpmn:endEvent>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_Inicio" targetRef="Task_Analisar"/>'
    '<bpmn:sequenceFlow id="Flow_1b" sourceRef="Start_Inicio" targetRef="Task_Analisar"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Analisar" targetRef="End_Fim"/>',
    [shape("Start_Inicio", 100, 102, 36, 36), shape("Task_Analisar", 200, 80), shape("End_Fim", 400, 102, 36, 36)],
    [edge("Flow_1", 136, 120, 200, 120), edge("Flow_1b", 136, 120, 200, 130), edge("Flow_2", 300, 120, 400, 120)],
)

# Lies about incoming/outgoing only (no duplicates): `flow-refs-mismatch`.
STALE_REFS = diagram(
    '<bpmn:startEvent id="Start_Inicio" name="Inicio"><bpmn:outgoing>Flow_1</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:userTask id="Task_Analisar" name="Analisar pedido"><bpmn:outgoing>Flow_2</bpmn:outgoing></bpmn:userTask>'
    '<bpmn:endEvent id="End_Fim" name="Fim"><bpmn:incoming>Flow_2</bpmn:incoming></bpmn:endEvent>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_Inicio" targetRef="Task_Analisar"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Analisar" targetRef="End_Fim"/>',
    [shape("Start_Inicio", 100, 102, 36, 36), shape("Task_Analisar", 200, 80), shape("End_Fim", 400, 102, 36, 36)],
    [edge("Flow_1", 136, 120, 200, 120), edge("Flow_2", 300, 120, 400, 120)],
)

# Mechanical duplicate whose gateway names the duplicate as its default flow.
DUPLICATE_DEFAULT = diagram(
    '<bpmn:startEvent id="Start_Inicio" name="Inicio"><bpmn:outgoing>Flow_1</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:exclusiveGateway id="Gateway_Decide" name="Decide?" default="Flow_Dup">'
    '<bpmn:incoming>Flow_1</bpmn:incoming><bpmn:outgoing>Flow_Sim</bpmn:outgoing>'
    '<bpmn:outgoing>Flow_Orig</bpmn:outgoing><bpmn:outgoing>Flow_Dup</bpmn:outgoing></bpmn:exclusiveGateway>'
    '<bpmn:userTask id="Task_Seguir" name="Seguir"><bpmn:incoming>Flow_Sim</bpmn:incoming>'
    '<bpmn:incoming>Flow_Orig</bpmn:incoming><bpmn:incoming>Flow_Dup</bpmn:incoming>'
    '<bpmn:outgoing>Flow_2</bpmn:outgoing></bpmn:userTask>'
    '<bpmn:endEvent id="End_Fim" name="Fim"><bpmn:incoming>Flow_2</bpmn:incoming></bpmn:endEvent>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_Inicio" targetRef="Gateway_Decide"/>'
    '<bpmn:sequenceFlow id="Flow_Sim" name="Sim" sourceRef="Gateway_Decide" targetRef="Task_Seguir">'
    '<bpmn:conditionExpression xsi:type="bpmn:tFormalExpression" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">ok</bpmn:conditionExpression></bpmn:sequenceFlow>'
    '<bpmn:sequenceFlow id="Flow_Orig" name="Nao" sourceRef="Gateway_Decide" targetRef="Task_Seguir"/>'
    '<bpmn:sequenceFlow id="Flow_Dup" name="Nao" sourceRef="Gateway_Decide" targetRef="Task_Seguir"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Seguir" targetRef="End_Fim"/>',
    [shape("Start_Inicio", 100, 202, 36, 36), shape("Gateway_Decide", 200, 195, 50, 50),
     shape("Task_Seguir", 340, 180), shape("End_Fim", 520, 202, 36, 36)],
    [edge("Flow_1", 136, 220, 200, 220), edge("Flow_Sim", 250, 220, 340, 210),
     edge("Flow_Orig", 250, 220, 340, 220), edge("Flow_Dup", 250, 220, 340, 230),
     edge("Flow_2", 440, 220, 520, 220)],
)


def editor_findings(page):
    """(rule, element) pairs the editor reports for the diagram that is open."""
    found = page.evaluate("collectValidationFindings().map(f => [f.rule, f.id])")
    return {(rule, element) for rule, element in found}


def python_findings(path):
    tree = ET.parse(ROOT / path)
    return {(finding.rule, finding.element) for finding in lint_rules.run_rules(tree)}


def summary_counts(page):
    return page.evaluate(
        "(() => { const s = document.getElementById('validation-summary');"
        " return [s.dataset.errors, s.dataset.warnings, s.dataset.infos].map(Number); })()")


# ---------------------------------------------------------------------------
# F3.1: contract of ported / omitted rules
# ---------------------------------------------------------------------------

def linter_rules():
    return {rule.name: rule for rule in lint_rules.RULES}


def test_every_linter_rule_is_either_ported_or_deliberately_omitted():
    ported = set(generate_editor_html.PORTED_RULES)
    omitted = set(generate_editor_html.OMITTED_RULES)
    known = set(linter_rules())
    assert not ported & omitted, f"decided twice: {sorted(ported & omitted)}"
    assert ported | omitted == known, (
        f"a rule of the linter has no decision (or the editor invents one): "
        f"{sorted(known ^ (ported | omitted))}")


def test_ported_rules_carry_the_severity_of_the_linter():
    rules = linter_rules()
    for rule_id, severity in generate_editor_html.PORTED_RULES.items():
        assert rules[rule_id].severity == severity, rule_id


def test_the_plan_names_the_rules_that_must_be_ported():
    required = {
        "missing-start-event", "missing-end-event", "start-has-incoming", "end-has-outgoing",
        "not-reachable-from-start", "default-flow-invalid", "boundary-invalid", "boundary-host-missing",
        "lane-coverage-duplicate", "implicit-split", "implicit-merge", "mixed-gateway",
        "parallel-join-without-split", "parallel-split-without-join", "duplicate-flow", "self-loop",
        "useless-gateway", "id-convention", "name-too-long", "di-overlap",
        "dead-end", "unreachable-node", "no-path-to-end", "gateway-without-condition",
        "unnamed-element", "lane-coverage-missing",
    }
    assert required <= set(generate_editor_html.PORTED_RULES)


def test_every_omitted_rule_explains_why():
    for rule_id, reason in generate_editor_html.OMITTED_RULES.items():
        assert len(reason.split()) >= 5, f"{rule_id}: the reason is too thin"


def test_the_editor_page_carries_the_rule_table_with_ids_severities_and_fixable():
    html = (ROOT / "editor.html").read_text(encoding="utf-8")
    table = dict(re.findall(r"\{ rule: '([a-z0-9-]+)', severity: '(error|warn|info)', fixable: (?:true|false) \}", html))
    assert table == generate_editor_html.PORTED_RULES
    for rule_id in generate_editor_html.EDITOR_FIXABLE_RULES:
        assert f"rule: '{rule_id}', severity: '{generate_editor_html.PORTED_RULES[rule_id]}', fixable: true" in html


def test_editor_fixable_rules_are_a_mechanical_subset():
    assert set(generate_editor_html.EDITOR_FIXABLE_RULES) <= set(generate_editor_html.PORTED_RULES)
    # `duplicate-flow` is the one the plan names explicitly.
    assert "duplicate-flow" in generate_editor_html.EDITOR_FIXABLE_RULES


# ---------------------------------------------------------------------------
# F3.1: parity with the Python linter on the repository examples
# ---------------------------------------------------------------------------

def test_the_editor_agrees_with_the_python_linter(live):
    """One editor session walks every file: (rule id, element id) must match for the ported rules."""
    page = live
    ported = set(generate_editor_html.PORTED_RULES)
    divergences = {}
    for path in PARITY_FILES:
        load_xml(page, (ROOT / path).read_text(encoding="utf-8"), Path(path).name)
        expected = {pair for pair in python_findings(path) if pair[0] in ported}
        actual = editor_findings(page)
        if actual != expected:
            divergences[path] = {"only in the editor": sorted(actual - expected, key=str),
                                 "only in the linter": sorted(expected - actual, key=str)}
    assert not divergences, divergences


def kitchen_sink():
    """A synthetic process that makes most of the ported rules fire at once."""
    nodes = [
        ("startEvent", "Start_A", "Inicio", None), ("userTask", "Task_A", "A", None),
        ("userTask", "Task_B", "B", None), ("userTask", "Task_C", "C", None),
        ("exclusiveGateway", "Gateway_Mixed", "Mistura?", None),
        ("userTask", "Task_Z", "Z", None), ("parallelGateway", "Gateway_Join", "Junta", None),
        ("parallelGateway", "Gateway_Split", "Divide", None),
        ("userTask", "Task_D", "D" * 70, None), ("userTask", "Task_E", "", None),
        ("inclusiveGateway", "Gateway_Useless", "Inutil", None),
        ("userTask", "task_lower", "Fora do padrao", None),
        ("userTask", "Task_Overlap1", "Sobre 1", (900, 80)), ("userTask", "Task_Overlap2", "Sobre 2", (900, 80)),
        ("boundaryEvent", "Boundary_Ok", "Prazo", "Task_A"), ("boundaryEvent", "Boundary_Gw", "Prazo gw", "Gateway_Mixed"),
        ("userTask", "Task_Loop", "Laco", None), ("endEvent", "End_A", "Fim", None),
        ("endEvent", "End_B", "Fim B", None),
    ]
    flows = [
        ("Flow_1", "Start_A", "Task_A"), ("Flow_2", "Start_A", "Task_B"),
        ("Flow_3", "Task_A", "Task_C"), ("Flow_4", "Task_B", "Task_C"),
        ("Flow_5", "Task_C", "Gateway_Mixed"), ("Flow_6", "Task_Z", "Gateway_Mixed"),
        ("Flow_7", "Gateway_Mixed", "Gateway_Join"), ("Flow_8", "Gateway_Mixed", "Gateway_Join"),
        ("Flow_9", "Gateway_Join", "Gateway_Split"), ("Flow_10", "Gateway_Split", "Task_D"),
        ("Flow_11", "Gateway_Split", "Task_E"), ("Flow_12", "Task_D", "Gateway_Useless"),
        ("Flow_13", "Gateway_Useless", "End_A"), ("Flow_14", "Task_E", "End_B"),
        ("Flow_15", "Task_Loop", "Task_Loop"), ("Flow_16", "Boundary_Ok", "task_lower"),
        ("Flow_17", "Boundary_Gw", "End_B"), ("Flow_18", "Task_E", "End_B"),
    ]
    body, shapes, edges = [], [], []
    for index, (tag, node_id, name, extra) in enumerate(nodes):
        attrs = f'id="{node_id}" name="{name}"'
        if tag == "boundaryEvent":
            attrs += f' attachedToRef="{extra}"'
        body.append(f"<bpmn:{tag} {attrs}/>")
        small = tag.endswith("Event")
        gateway = tag.endswith("Gateway")
        w, h = (36, 36) if small else ((50, 50) if gateway else (100, 80))
        x, y = extra if isinstance(extra, tuple) else (100 + (index % 6) * 170, 80 + (index // 6) * 140)
        shapes.append(shape(node_id, x, y, w, h))
    for flow_id, src, tgt in flows:
        body.append(f'<bpmn:sequenceFlow id="{flow_id}" sourceRef="{src}" targetRef="{tgt}"/>')
        edges.append(edge(flow_id, 0, 0, 10, 10))
    return diagram("".join(body), shapes, edges)


def test_the_editor_agrees_with_the_linter_on_a_process_that_breaks_many_rules(live, tmp_path):
    page = live
    xml = kitchen_sink()
    target = tmp_path / "kitchen.bpmn"
    target.write_text(xml, encoding="utf-8")
    load_xml(page, xml, "kitchen.bpmn")
    ported = set(generate_editor_html.PORTED_RULES)
    expected = {(f.rule, f.element) for f in lint_rules.run_rules(ET.parse(target)) if f.rule in ported}
    actual = editor_findings(page)
    fired = {rule for rule, _ in expected}
    assert {"implicit-split", "implicit-merge", "mixed-gateway", "parallel-join-without-split",
            "parallel-split-without-join", "useless-gateway", "id-convention", "name-too-long",
            "di-overlap", "self-loop", "duplicate-flow", "unnamed-element",
            "gateway-without-condition", "boundary-invalid"} <= fired
    assert actual == expected, (sorted(actual - expected, key=str), sorted(expected - actual, key=str))


def test_the_parity_files_cover_findings_of_every_severity():
    seen = set()
    for path in PARITY_FILES:
        tree = ET.parse(ROOT / path)
        seen |= {finding.severity for finding in lint_rules.run_rules(tree)}
    assert seen == {"error", "warn", "info"}


def test_the_broken_example_exercises_error_and_warning_rules(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "example-broken.bpmn")
    rules = {rule for rule, _ in editor_findings(page)}
    assert {"unreachable-node", "start-has-incoming", "end-has-outgoing", "default-flow-invalid",
            "boundary-invalid", "lane-coverage-duplicate", "flow-refs-mismatch"} <= rules


@pytest.mark.parametrize("rule_id,xml_body,element", [
    ("self-loop", '<bpmn:sequenceFlow id="Flow_Self" sourceRef="Task_Analisar" targetRef="Task_Analisar"/>', "Flow_Self"),
])
def test_a_self_loop_is_reported(live, rule_id, xml_body, element):
    page = live
    xml = CLEAN.replace("</bpmn:process>", xml_body + "</bpmn:process>").replace(
        "</bpmndi:BPMNPlane>", edge("Flow_Self", 250, 160, 250, 170) + "</bpmndi:BPMNPlane>")
    load_xml(page, xml)
    assert (rule_id, element) in editor_findings(page)


def test_each_finding_carries_rule_severity_message_and_element(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    findings = page.evaluate("collectValidationFindings()")
    assert findings
    rules = linter_rules()
    for finding in findings:
        assert finding["severity"] == rules[finding["rule"]].severity
        assert finding["message"].strip()
    assert [f["severity"] for f in findings] == sorted(
        (f["severity"] for f in findings), key=["error", "warn", "info"].index), "errors come first"


# ---------------------------------------------------------------------------
# F3.1: the panel shows id and severity, filters and counts by severity
# ---------------------------------------------------------------------------

def test_the_panel_lists_rule_id_and_severity_of_every_finding(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.click("#btn-validate")
    items = page.locator(".validation-finding")
    assert items.count() == page.evaluate("collectValidationFindings().length")
    first = items.first
    assert first.get_attribute("data-severity") == "error"
    assert first.get_attribute("data-rule")
    # the rule label is rendered in capitals by CSS; the text content keeps the id
    assert first.get_attribute("data-rule") in first.text_content()
    assert "error" in first.text_content()


def test_the_panel_filters_by_severity_and_counts_each_one(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.click("#btn-validate")
    counts = page.evaluate(
        "(() => { const c = {error: 0, warn: 0, info: 0};"
        " collectValidationFindings().forEach(f => { c[f.severity] += 1; }); return c; })()")
    total = sum(counts.values())
    assert counts["error"] and counts["warn"]
    assert page.inner_text("[data-severity-filter='all'] .count") == str(total)
    for severity in ("error", "warn", "info"):
        assert page.inner_text(f"[data-severity-filter='{severity}'] .count") == str(counts[severity])
    page.click("[data-severity-filter='warn']")
    assert page.get_attribute("[data-severity-filter='warn']", "aria-pressed") == "true"
    assert page.get_attribute("[data-severity-filter='all']", "aria-pressed") == "false"
    shown = page.locator(".validation-finding")
    assert shown.count() == counts["warn"]
    assert set(shown.evaluate_all("els => els.map(e => e.dataset.severity)")) == {"warn"}
    page.click("[data-severity-filter='all']")
    assert page.locator(".validation-finding").count() == total


def test_a_filter_with_no_matches_says_so(live):
    page = live
    load_xml(page, CLEAN.replace('name="Analisar pedido"', 'name=""'))
    wait_for_marker(page, "Task_Analisar", "vld-warn")
    page.click("[data-severity-filter='error']")
    assert page.locator(".validation-finding").count() == 0
    assert page.is_visible(".validation-empty")


def test_clicking_a_finding_selects_and_centres_the_element(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.click("#btn-validate")
    page.click(".validation-finding[data-rule='start-has-incoming']")
    assert page.evaluate("modeler.get('selection').get().map(e => e.id)") == ["Start_ExpenseSubmitted"]


# ---------------------------------------------------------------------------
# F3.2: automatic validation and the always-visible counter
# ---------------------------------------------------------------------------

def test_the_counter_is_visible_with_the_panel_closed_and_has_an_accessible_name(live):
    page = live
    page.click("#btn-props-toggle")
    assert not page.is_visible("#properties-panel")
    assert page.is_visible("#validation-summary")
    label = page.get_attribute("#validation-summary", "aria-label")
    assert label and "Validação" in label


def test_opening_a_diagram_validates_without_any_click(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.wait_for_function(
        "Number(document.getElementById('validation-summary').dataset.errors) > 0", timeout=5000)
    errors, warnings, _infos = summary_counts(page)
    found = page.evaluate(
        "(() => { const c = {error: 0, warn: 0, info: 0};"
        " collectValidationFindings().forEach(f => { c[f.severity] += 1; }); return c; })()")
    assert (errors, warnings) == (found["error"], found["warn"])
    assert page.locator(".validation-finding").count() > 0, "the list is filled without pressing the button"
    label = page.get_attribute("#validation-summary", "aria-label")
    assert f"{errors} erros" in label


def test_editing_the_diagram_updates_the_counter_by_itself(live):
    page = live
    load_xml(page, CLEAN)
    page.wait_for_function("document.getElementById('validation-summary').dataset.state === 'ok'", timeout=5000)
    assert summary_counts(page) == [0, 0, 0]
    page.evaluate(
        "modeler.get('modeling').updateProperties(modeler.get('elementRegistry').get('Task_Analisar'), {name: ''})")
    page.wait_for_function("Number(document.getElementById('validation-summary').dataset.warnings) === 1", timeout=5000)
    assert summary_counts(page) == [0, 1, 0]
    page.evaluate(
        "modeler.get('modeling').updateProperties(modeler.get('elementRegistry').get('Task_Analisar'), {name: 'Analisar'})")
    page.wait_for_function("document.getElementById('validation-summary').dataset.state === 'ok'", timeout=5000)


def test_validation_is_debounced_not_run_per_change(page):
    open_editor(page)
    load_xml(page, CLEAN)
    page.wait_for_function("document.getElementById('validation-summary').dataset.state === 'ok'", timeout=5000)
    start = page.evaluate("getValidationRuns()")
    after_burst = page.evaluate(
        """() => {
          const modeling = modeler.get('modeling');
          const task = modeler.get('elementRegistry').get('Task_Analisar');
          for (let i = 0; i < 12; i++) modeling.updateProperties(task, {name: 'Analisar ' + i});
          return getValidationRuns();
        }""")
    assert after_burst == start, "nothing runs synchronously while the edits are still coming"
    page.wait_for_function("(n) => getValidationRuns() > n", arg=start, timeout=5000)
    page.wait_for_timeout(900)  # a runaway loop would show up as more runs
    assert page.evaluate("getValidationRuns()") == start + 1, "a burst of 12 edits costs one validation run"


def test_validation_does_not_loop_when_nothing_changes(page):
    open_editor(page)
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.wait_for_function("document.getElementById('validation-summary').dataset.state === 'error'", timeout=5000)
    page.wait_for_timeout(300)
    settled = page.evaluate("getValidationRuns()")
    page.wait_for_timeout(1200)
    assert page.evaluate("getValidationRuns()") == settled


def test_automatic_validation_does_not_dirty_the_document_or_the_history(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.wait_for_function("document.getElementById('validation-summary').dataset.state === 'error'", timeout=5000)
    assert stack_index(page) == 0
    assert page.evaluate("isDirty") is False


def test_the_counter_opens_the_panel(live):
    page = live
    page.click("#btn-props-toggle")
    assert not page.is_visible("#properties-panel")
    page.click("#validation-summary")
    assert page.is_visible("#properties-panel")
    assert page.is_visible("#validation-section")


def test_the_manual_button_still_validates_right_away(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.click("#btn-validate")
    assert page.locator(".validation-finding").count() > 0


def test_a_clean_diagram_shows_zero_everywhere(live):
    page = live
    load_xml(page, CLEAN)
    page.click("#btn-validate")
    assert page.is_visible(".validation-ok")
    assert summary_counts(page) == [0, 0, 0]
    label = page.get_attribute("#validation-summary", "aria-label")
    assert "nenhum problema" in label


# ---------------------------------------------------------------------------
# F3.3: markers on the canvas
# ---------------------------------------------------------------------------

MARKER_JS = (
    "id => { const c = modeler.get('canvas'); "
    "return ['vld-error', 'vld-warn'].filter(m => c.hasMarker(id, m)); }"
)


def wait_for_marker(page, element_id, marker):
    page.wait_for_function(
        "([id, m]) => modeler.get('canvas').hasMarker(id, m)", arg=[element_id, marker], timeout=5000)


def test_elements_with_problems_get_a_marker_per_severity(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    wait_for_marker(page, "Start_ExpenseSubmitted", "vld-error")
    # Task_ReviewExpense is unreachable (error); Gateway_Approved has an invalid default (error).
    assert page.evaluate(MARKER_JS, "Task_ReviewExpense") == ["vld-error"]
    assert page.evaluate(MARKER_JS, "Gateway_Approved") == ["vld-error"]


def test_a_warning_only_element_gets_the_warning_marker_and_a_clean_one_none(live):
    page = live
    load_xml(page, CLEAN.replace('name="Analisar pedido"', 'name=""'))
    wait_for_marker(page, "Task_Analisar", "vld-warn")
    assert page.evaluate(MARKER_JS, "Task_Analisar") == ["vld-warn"]
    assert page.evaluate(MARKER_JS, "Start_Inicio") == []


def test_the_marker_is_not_only_a_colour(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    wait_for_marker(page, "Task_ReviewExpense", "vld-error")
    badges = page.locator(".vld-badge")
    assert badges.count() >= 1
    first = badges.first
    assert first.get_attribute("role") == "img"
    assert "Problema de validação" in first.get_attribute("aria-label")
    assert first.inner_text().strip() in ("✖", "▲")
    # Error = solid thick stroke, warning = dashed: shape, not just hue.
    page.evaluate("modeler.get('selection').select([])")
    dash = page.evaluate(
        "id => getComputedStyle(modeler.get('elementRegistry').getGraphics(id).querySelector('.djs-visual > rect'))"
        ".strokeDasharray", "Task_ReviewExpense")
    assert dash in ("none", "")


def test_a_warning_marker_is_dashed(live):
    page = live
    load_xml(page, CLEAN.replace('name="Analisar pedido"', 'name=""'))
    wait_for_marker(page, "Task_Analisar", "vld-warn")
    dash = page.evaluate(
        "id => getComputedStyle(modeler.get('elementRegistry').getGraphics(id).querySelector('.djs-visual > rect'))"
        ".strokeDasharray", "Task_Analisar")
    assert dash not in ("none", "")


def test_a_marker_disappears_when_the_problem_is_fixed(live):
    page = live
    load_xml(page, CLEAN.replace('name="Analisar pedido"', 'name=""'))
    wait_for_marker(page, "Task_Analisar", "vld-warn")
    page.evaluate(
        "modeler.get('modeling').updateProperties(modeler.get('elementRegistry').get('Task_Analisar'), {name: 'Analisar'})")
    page.wait_for_function(
        "!modeler.get('canvas').hasMarker('Task_Analisar', 'vld-warn')", timeout=5000)
    assert page.locator(".vld-badge").count() == 0


def test_a_connection_with_a_problem_is_marked_too(live):
    page = live
    xml = CLEAN.replace("</bpmn:process>", '<bpmn:sequenceFlow id="Flow_Self" sourceRef="Task_Analisar" '
                        'targetRef="Task_Analisar"/></bpmn:process>').replace(
        "</bpmndi:BPMNPlane>", edge("Flow_Self", 250, 160, 250, 170) + "</bpmndi:BPMNPlane>")
    load_xml(page, xml)
    wait_for_marker(page, "Flow_Self", "vld-warn")


def test_markers_stay_out_of_the_xml_the_history_and_the_dirty_flag(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    wait_for_marker(page, "Task_ReviewExpense", "vld-error")
    xml = saved_xml(page)
    assert "vld-" not in xml and "validation" not in xml.lower()
    assert stack_index(page) == 0
    assert page.evaluate("isDirty") is False


def test_the_svg_download_has_no_markers_and_they_come_back_after_it(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    wait_for_marker(page, "Task_ReviewExpense", "vld-error")
    page.click("#menu-file-trigger")
    with page.expect_download() as info:
        page.click("#btn-export-svg")
    svg = Path(info.value.path()).read_text(encoding="utf-8")
    assert "<svg" in svg
    assert "vld-" not in svg
    assert "Problema de validação" not in svg
    page.wait_for_function("modeler.get('canvas').hasMarker('Task_ReviewExpense', 'vld-error')", timeout=5000)
    assert page.locator(".vld-badge").count() >= 1


def test_the_markers_are_hidden_when_printing(live):
    page = live
    html = (ROOT / "editor.html").read_text(encoding="utf-8")
    assert re.search(r"@media print \{\s*\.vld-badge \{ display: none", html)


# ---------------------------------------------------------------------------
# F3.4: "Corrigir" with preview, one undo step
# ---------------------------------------------------------------------------

def flow_ids(page):
    return sorted(page.evaluate(
        "modeler.get('elementRegistry').filter(e => e.type === 'bpmn:SequenceFlow').map(e => e.id)"))


def test_the_fix_button_is_disabled_without_fixable_problems(live):
    page = live
    load_xml(page, CLEAN)
    page.wait_for_function("document.getElementById('validation-summary').dataset.state === 'ok'", timeout=5000)
    assert page.is_disabled("#btn-fix")


def test_the_fix_button_enables_with_a_duplicate_flow(live):
    page = live
    load_xml(page, DUPLICATED)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    assert "Corrigir" in page.get_attribute("#btn-fix", "aria-label")


def test_the_preview_lists_the_changes_and_cancel_changes_nothing(live):
    page = live
    load_xml(page, DUPLICATED)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    before = saved_xml(page)
    page.click("#btn-fix")
    assert page.is_visible("#fix-dialog")
    text = page.inner_text("#fix-preview-list")
    assert "Flow_1b" in text and "Flow_1" in text
    page.click("#fix-cancel")
    assert not page.is_visible("#fix-dialog")
    assert saved_xml(page) == before
    assert stack_index(page) == 0


def test_escape_closes_the_preview_without_applying(live):
    page = live
    load_xml(page, DUPLICATED)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    page.click("#btn-fix")
    page.keyboard.press("Escape")
    assert not page.is_visible("#fix-dialog")
    assert "Flow_1b" in flow_ids(page)


def test_applying_removes_the_duplicate_flow_in_one_undo_step(live):
    page = live
    load_xml(page, DUPLICATED)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    page.click("#btn-fix")
    page.click("#fix-apply")
    assert flow_ids(page) == ["Flow_1", "Flow_2"]
    assert stack_index(page) == 1, "everything the fix did is one history entry"
    page.wait_for_function("document.getElementById('btn-fix').disabled", timeout=5000)
    assert not page.is_visible("#fix-dialog")
    # No duplicate-flow / flow-refs-mismatch left, and the saved XML is clean for the Python linter.
    assert not {r for r, _ in editor_findings(page)} & {"duplicate-flow", "flow-refs-mismatch"}
    page.keyboard.press("Control+z")
    assert flow_ids(page) == ["Flow_1", "Flow_1b", "Flow_2"]
    assert "Flow_1b" in saved_xml(page)


def test_the_fix_moves_a_default_flow_to_the_survivor_and_keeps_conditions(live):
    page = live
    load_xml(page, DUPLICATE_DEFAULT)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    page.click("#btn-fix")
    assert "Flow_Dup" in page.inner_text("#fix-preview-list")
    page.click("#fix-apply")
    assert "Flow_Dup" not in flow_ids(page)
    assert "Flow_Sim" in flow_ids(page) and "Flow_Orig" in flow_ids(page)
    default = page.evaluate(
        "modeler.get('elementRegistry').get('Gateway_Decide').businessObject.default.id")
    assert default == "Flow_Orig"
    assert "default-flow-invalid" not in {r for r, _ in editor_findings(page)}
    assert stack_index(page) == 1


def test_the_fix_rebuilds_stale_incoming_outgoing_lists(live):
    page = live
    load_xml(page, STALE_REFS)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    assert ("flow-refs-mismatch", "Task_Analisar") in editor_findings(page)
    page.click("#btn-fix")
    assert "Task_Analisar" in page.inner_text("#fix-preview-list")
    page.click("#fix-apply")
    assert "flow-refs-mismatch" not in {r for r, _ in editor_findings(page)}
    xml = saved_xml(page)
    task = re.search(r'<bpmn:userTask id="Task_Analisar".*?</bpmn:userTask>', xml, re.S).group(0)
    assert "<bpmn:incoming>Flow_1</bpmn:incoming>" in task
    assert stack_index(page) == 1


def test_the_fix_never_creates_nodes_flows_or_names(live):
    page = live
    load_xml(page, DUPLICATE_DEFAULT)
    before = page.evaluate(
        "modeler.get('elementRegistry').filter(e => !e.labelTarget).map(e => [e.id, e.businessObject.name || ''])")
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    page.click("#btn-fix")
    page.click("#fix-apply")
    after = page.evaluate(
        "modeler.get('elementRegistry').filter(e => !e.labelTarget).map(e => [e.id, e.businessObject.name || ''])")
    ids_before = {entry[0] for entry in before}
    assert {entry[0] for entry in after} <= ids_before, "the fix only removes, it never invents ids"
    assert {tuple(entry) for entry in after} <= {tuple(entry) for entry in before}, "names are untouched"


def test_the_fixed_diagram_passes_the_python_linter(live, tmp_path):
    page = live
    load_xml(page, DUPLICATE_DEFAULT)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    page.click("#btn-fix")
    page.click("#fix-apply")
    target = tmp_path / "fixed.bpmn"
    target.write_text(saved_xml(page), encoding="utf-8")
    findings = lint_rules.run_rules(ET.parse(target))
    assert not [f for f in findings if f.severity == "error"], findings
    assert not [f for f in findings if f.rule in ("duplicate-flow", "flow-refs-mismatch", "default-flow-invalid")]


def test_the_fix_dialog_is_labelled_and_traps_keyboard_focus(live):
    page = live
    load_xml(page, DUPLICATED)
    page.wait_for_function("!document.getElementById('btn-fix').disabled", timeout=5000)
    page.click("#btn-fix")
    dialog = page.locator("#fix-dialog .dialog")
    assert dialog.get_attribute("role") == "dialog"
    assert dialog.get_attribute("aria-modal") == "true"
    assert page.evaluate("document.activeElement.id") == "fix-apply"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "fix-cancel"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "fix-apply"


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_the_editor_version_reflects_phase_3a():
    parts = tuple(int(part) for part in generate_editor_html.EDITOR_VERSION.split("."))
    assert parts >= (1, 4, 0)


# ---------------------------------------------------------------------------
# Critic gaps of iteration 1: readable messages, parity on mutated templates
# ---------------------------------------------------------------------------

def test_finding_messages_wrap_instead_of_being_cut_off(live):
    page = live
    load_xml(page, (ROOT / "references/example-broken.bpmn").read_text(encoding="utf-8"), "broken.bpmn")
    page.click("#btn-validate")
    overflowing = page.evaluate(
        "Array.from(document.querySelectorAll('.validation-finding'))"
        ".filter(el => el.scrollWidth > el.clientWidth + 1).length")
    assert page.locator(".validation-finding").count() > 0
    assert overflowing == 0


def _swap_tag(xml, old, new):
    return re.sub(rf"(</?)bpmn:{old}\b", rf"\1bpmn:{new}", xml)


TEMPLATE_MUTATIONS = {
    "no-start-event": lambda xml: _swap_tag(xml, "startEvent", "userTask"),
    "no-end-event": lambda xml: _swap_tag(xml, "endEvent", "userTask"),
    "lane-duplicate": lambda xml: xml.replace(
        "<bpmn:flowNodeRef>Task_TratarSolicitacao</bpmn:flowNodeRef>",
        "<bpmn:flowNodeRef>Task_TratarSolicitacao</bpmn:flowNodeRef>"
        "<bpmn:flowNodeRef>Task_AbrirSolicitacao</bpmn:flowNodeRef>", 1),
    "gateway-to-parallel": lambda xml: _swap_tag(xml, "exclusiveGateway", "parallelGateway"),
}


@pytest.mark.parametrize("mutation, template", [
    ("no-start-event", "linear"),
    ("no-end-event", "linear"),
    ("no-start-event", "decision"),
    ("gateway-to-parallel", "decision"),
    ("lane-duplicate", "lanes"),
])
def test_the_editor_agrees_with_the_linter_on_mutated_templates(live, tmp_path, mutation, template):
    page = live
    xml = TEMPLATE_MUTATIONS[mutation]((ROOT / f"assets/templates/{template}.bpmn").read_text(encoding="utf-8"))
    target = tmp_path / f"{template}-{mutation}.bpmn"
    target.write_text(xml, encoding="utf-8")
    load_xml(page, xml, target.name)
    ported = set(generate_editor_html.PORTED_RULES)
    expected = {(f.rule, f.element) for f in lint_rules.run_rules(ET.parse(target)) if f.rule in ported}
    assert expected, "the mutation must make the linter report something"
    actual = editor_findings(page)
    assert actual == expected, (sorted(actual - expected, key=str), sorted(expected - actual, key=str))
