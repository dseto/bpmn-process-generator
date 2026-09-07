import json
import re
from pathlib import Path
import pytest

from build_editor import build_editor


def test_build_editor_missing_bpmn(template_path: Path, tmp_path: Path):
    """Verify build_editor raises FileNotFoundError when input BPMN does not exist."""
    non_existent = tmp_path / "does_not_exist.bpmn"
    out = tmp_path / "out.html"
    with pytest.raises(FileNotFoundError, match="BPMN file not found"):
        build_editor(non_existent, template_path, out, "test")


def test_build_editor_missing_template(tests_dir: Path, tmp_path: Path):
    """Verify build_editor raises FileNotFoundError when template does not exist."""
    bpmn = tests_dir / "01-user-onboarding.bpmn"
    non_existent_tpl = tmp_path / "fake_template.html"
    out = tmp_path / "out.html"
    with pytest.raises(FileNotFoundError, match="Template file not found"):
        build_editor(bpmn, non_existent_tpl, out, "test")


def test_build_editor_creates_parent_directory(template_path: Path, tests_dir: Path, tmp_path: Path):
    """Verify build_editor automatically creates parent directories for output HTML."""
    bpmn = tests_dir / "01-user-onboarding.bpmn"
    out = tmp_path / "nested" / "sub" / "dir" / "out.html"
    build_editor(bpmn, template_path, out, "onboarding")
    assert out.exists()


def test_build_editor_script_tag_escaping(template_path: Path, tmp_path: Path):
    """Verify build_editor safely escapes any </script> sequences inside BPMN XML."""
    malicious_xml = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D1">
  <bpmn:process id="P1">
    <bpmn:task id="T1" name="Check </script><script>alert('xss')</script> tag" />
  </bpmn:process>
</bpmn:definitions>"""

    bpmn_file = tmp_path / "malicious.bpmn"
    bpmn_file.write_text(malicious_xml, encoding="utf-8")
    out_file = tmp_path / "safe.html"

    build_editor(bpmn_file, template_path, out_file, "xss-test")
    html_content = out_file.read_text(encoding="utf-8")

    # There should only be the 2 authentic template </script> tags, none from the payload
    closing_tags = re.findall(r"</script>", html_content, re.IGNORECASE)
    assert len(closing_tags) == 2

    # Verify double JSON round-trip recovers the exact payload intact
    m = re.search(r'const ORIGINAL_BPMN_XML = JSON\.parse\(("(?:\\.|[^"\\])*")\);', html_content)
    assert m is not None
    outer = json.loads(m.group(1))
    recovered_xml = json.loads(outer)
    assert recovered_xml == malicious_xml
