"""
G1 (carry-over from Fase 1): `bpmn_tool.py layout` / `fix` recompute the whole
BPMNDiagram, and must not throw away the per-element font styles the editor stores
(`bpmndi:BPMNLabel labelStyle` + `bpmndi:BPMNLabelStyle` / `dc:Font`).
"""
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
BPMN_TOOL = ROOT / "scripts" / "bpmn_tool.py"
SOURCE = ROOT / "tests" / "01-user-onboarding.bpmn"

BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"


def styled_copy(tmp_path, with_flow_style=False):
    """The onboarding example with a bold 16px font on one task and an italic one on the end event."""
    text = SOURCE.read_text(encoding="utf-8")
    text = text.replace(
        '<omgdc:Bounds x="310" y="80" width="100" height="80" /></bpmndi:BPMNShape>',
        '<omgdc:Bounds x="310" y="80" width="100" height="80" />'
        '<bpmndi:BPMNLabel labelStyle="LabelStyle_A" /></bpmndi:BPMNShape>')
    text = text.replace(
        '<omgdc:Bounds x="760" y="102" width="36" height="36" /></bpmndi:BPMNShape>',
        '<omgdc:Bounds x="760" y="102" width="36" height="36" />'
        '<bpmndi:BPMNLabel labelStyle="LabelStyle_B" /></bpmndi:BPMNShape>')
    styles = ('<bpmndi:BPMNLabelStyle id="LabelStyle_A"><omgdc:Font name="Arial" size="16" isBold="true" /></bpmndi:BPMNLabelStyle>'
              '<bpmndi:BPMNLabelStyle id="LabelStyle_B"><omgdc:Font name="Arial" size="9" isItalic="true" /></bpmndi:BPMNLabelStyle>'
              '<bpmndi:BPMNLabelStyle id="LabelStyle_Unused"><omgdc:Font size="20" /></bpmndi:BPMNLabelStyle>')
    text = text.replace("</bpmndi:BPMNPlane>", "</bpmndi:BPMNPlane>" + styles)
    target = tmp_path / "styled.bpmn"
    target.write_text(text, encoding="utf-8")
    return target


def run_tool(*args):
    return subprocess.run([sys.executable, str(BPMN_TOOL), *args], capture_output=True, text=True)


def fonts_by_element(path):
    root = ET.parse(path).getroot()
    styles = {}
    for style in root.iter(f"{{{BPMNDI}}}BPMNLabelStyle"):
        font = style.find(f"{{{DC}}}Font")
        styles[style.get("id")] = dict(font.attrib)
    result = {}
    for shape in root.iter(f"{{{BPMNDI}}}BPMNShape"):
        label = shape.find(f"{{{BPMNDI}}}BPMNLabel")
        if label is not None and label.get("labelStyle"):
            result[shape.get("bpmnElement")] = styles[label.get("labelStyle")]
    return result


def test_layout_keeps_the_font_style_of_each_element(tmp_path):
    source = styled_copy(tmp_path)
    assert run_tool("layout", str(source), "--no-copy-editor").returncode == 0
    fonts = fonts_by_element(source)
    assert fonts["Task_ValidateRegistration"] == {"name": "Arial", "size": "16", "isBold": "true"}
    assert fonts["End_OnboardingCompleted"] == {"name": "Arial", "size": "9", "isItalic": "true"}
    assert len(fonts) == 2, "only the styled elements carry a style"


def test_layout_does_not_keep_unreferenced_styles_and_stays_valid(tmp_path):
    source = styled_copy(tmp_path)
    run_tool("layout", str(source), "--no-copy-editor")
    text = source.read_text(encoding="utf-8")
    assert "LabelStyle_Unused" not in text
    result = run_tool("validate", str(source))
    assert result.returncode == 0, result.stdout + result.stderr


def test_layout_keeps_the_style_when_the_diagram_has_moved_elements(tmp_path):
    source = styled_copy(tmp_path)
    text = source.read_text(encoding="utf-8").replace('x="310" y="80"', 'x="999" y="500"')
    source.write_text(text, encoding="utf-8")
    run_tool("layout", str(source), "--no-copy-editor")
    assert re.search(r'x="999"', source.read_text(encoding="utf-8")) is None
    assert fonts_by_element(source)["Task_ValidateRegistration"]["isBold"] == "true"


def test_fix_keeps_the_style_when_it_has_to_rebuild_the_diagram(tmp_path):
    source = styled_copy(tmp_path)
    text = source.read_text(encoding="utf-8")
    # drop one edge so `fix` recomputes the DI
    text = re.sub(r'<bpmndi:BPMNEdge id="Flow_2_di".*?</bpmndi:BPMNEdge>', "", text, flags=re.S)
    source.write_text(text, encoding="utf-8")
    result = run_tool("fix", str(source))
    assert result.returncode == 0, result.stdout + result.stderr
    assert fonts_by_element(source)["Task_ValidateRegistration"]["size"] == "16"


def test_a_file_without_styles_gets_none_added(tmp_path):
    target = tmp_path / "plain.bpmn"
    target.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    run_tool("layout", str(target), "--no-copy-editor")
    assert "BPMNLabelStyle" not in target.read_text(encoding="utf-8")
