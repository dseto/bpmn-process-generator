from pathlib import Path
from xml.etree import ElementTree as ET
import pytest

from generate_editor_html import PRESET_FILES, BLANK_TEMPLATE


def test_preset_files_exist():
    """Verify that every preset registered in generate_editor_html.py exists on disk."""
    for name, path in PRESET_FILES.items():
        assert path.exists(), f"Preset file missing: {path} ({name})"
        assert path.stat().st_size > 0, f"Preset file is empty: {path}"


def test_blank_template_is_well_formed_xml():
    """Verify the embedded blank template is well-formed XML with valid initial BPMNDiagram."""
    root = ET.fromstring(BLANK_TEMPLATE)
    assert root.tag.endswith("definitions")

    diagram = root.find("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNDiagram")
    assert diagram is not None

    plane = diagram.find("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNPlane")
    assert plane is not None

    shape = plane.find("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape")
    assert shape is not None
    assert shape.get("bpmnElement") == "Start_1"


def test_editor_html_exists_and_contains_presets(project_root: Path):
    """Verify that editor.html exists in project root and contains all embedded presets."""
    editor_path = project_root / "editor.html"
    assert editor_path.exists(), "editor.html missing from project root"
    content = editor_path.read_text(encoding="utf-8")

    # Verify preset dropdown entries
    for name in PRESET_FILES.keys():
        assert name in content, f"Preset '{name}' not found in editor.html"


def test_editor_html_has_task_resize_capabilities(project_root: Path):
    """Verify editor.html includes CustomResizeModule to allow resizing task elements."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")
    assert "CustomResizeModule" in content
    assert "shape.resize" in content
    assert "min" in content
    assert "additionalModules" in content


def test_editor_html_has_grid_snapping_and_orthogonal_routing(project_root: Path):
    """Verify editor.html configures gridSnapping and 90-degree orthogonal line layout."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")
    assert "gridSnapping" in content
    assert "layoutConnection" in content
    assert "btn-route-90" in content
    assert "Curva 90°" in content


def test_editor_html_has_enhanced_toolbar_and_features(project_root: Path):
    """Verify editor.html includes undo/redo, colors, zoom, search, and image exports."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")

    # History
    assert "btn-undo" in content
    assert "btn-redo" in content

    # Zoom & Search
    assert "btn-zoom-in" in content
    assert "btn-zoom-out" in content
    assert "btn-zoom-fit" in content
    assert "btn-search" in content
    assert "searchPad" in content

    # Color palette
    assert "color-dot" in content
    assert "setColor" in content

    # Image Exports
    assert "btn-export-svg" in content
    assert "btn-export-png" in content
    assert "saveSVG" in content


def test_template_html_has_task_resize_and_90deg_routing(project_root: Path):
    """Verify assets/bpmn-editor-template.html includes task resize, grid snapping and 90deg routing."""
    template_path = project_root / "assets" / "bpmn-editor-template.html"
    content = template_path.read_text(encoding="utf-8")
    assert "CustomResizeModule" in content
    assert "gridSnapping" in content
    assert "layoutConnection" in content
    assert "btn-route-90" in content


def test_editor_html_has_font_styling_controls(project_root: Path):
    """Verify editor.html includes element-specific typography controls and logic."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")

    assert "font-size-select" in content
    assert "btn-font-bold" in content
    assert "btn-font-italic" in content
    assert "elementFontStyles" in content
    assert "getSelectedElements" in content
    assert "applyAllElementFontStyles" in content
    assert "updateFontToolbarFromSelection" in content
    assert "data-element-id" in content
    assert "setFontSize" in content
    assert "toggleBold" in content
    assert "toggleItalic" in content
    assert "svg-font-style" in content


def test_template_html_has_font_styling_controls(project_root: Path):
    """Verify assets/bpmn-editor-template.html includes element-specific typography controls."""
    template_path = project_root / "assets" / "bpmn-editor-template.html"
    content = template_path.read_text(encoding="utf-8")

    assert "font-size-select" in content
    assert "btn-font-bold" in content
    assert "btn-font-italic" in content
    assert "elementFontStyles" in content
    assert "getSelectedElements" in content
    assert "applyAllElementFontStyles" in content
    assert "updateFontToolbarFromSelection" in content
    assert "data-element-id" in content


def test_editor_html_has_file_param_query_support(project_root: Path):
    """Verify editor.html supports loading or configuring a file via ?file= query parameter."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")

    assert "urlParams.get('file')" in content
    assert "initEditor" in content


def test_editor_html_does_not_auto_load_skill_examples(project_root: Path):
    """Verify central editor.html has DEFAULT_DIAGRAM hooks and does not auto-load skill examples on startup."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")

    assert "DEFAULT_DIAGRAM_NAME" in content
    assert "DEFAULT_DIAGRAM_XML" in content
    # Ensure it doesn't auto-load the bus process or any other preset as startup default
    assert "loadXML(PRESETS['06-bus-boarding-process.bpmn']" not in content


def test_editor_html_toolbar_is_responsive_and_accessible(project_root: Path):
    """Verify editor.html uses flexbox wrapping, flexible canvas, and wheel scrolling for toolbar accessibility."""
    editor_path = project_root / "editor.html"
    content = editor_path.read_text(encoding="utf-8")

    # Responsive layout rules
    assert "flex-direction: column" in content
    assert "flex-wrap: wrap" in content
    assert "flex: 1 1 auto" in content
    assert "min-height: 48px" in content
    assert "appHeader.addEventListener('wheel'" in content
    assert "#drop-overlay" in content
    assert "position: fixed" in content


def test_template_html_toolbar_is_responsive_and_accessible(project_root: Path):
    """Verify assets/bpmn-editor-template.html uses flexbox wrapping and flexible canvas."""
    template_path = project_root / "assets" / "bpmn-editor-template.html"
    content = template_path.read_text(encoding="utf-8")

    assert "flex-direction: column" in content
    assert "flex-wrap: wrap" in content
    assert "flex: 1 1 auto" in content
    assert "toolbarEl.addEventListener('wheel'" in content
