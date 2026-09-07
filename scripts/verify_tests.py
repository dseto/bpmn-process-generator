#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from bpmn_tool import validate
from build_editor import build_editor
import tempfile

TEST_NAMES = [
    "01-user-onboarding",
    "02-credit-card-approval",
    "03-order-fulfillment",
    "04-incident-management",
    "05-document-revision-cycle",
    "06-bus-boarding-process",
]

def main():
    print("==================================================")
    print("EVALUATION & VERIFICATION SUITE: 6 BPMN TEST CASES")
    print("==================================================")
    all_passed = True
    template_path = Path("assets/bpmn-editor-template.html")

    for name in TEST_NAMES:
        bpmn_path = Path(f"tests/{name}.bpmn")
        html_path = Path(f"tests/{name}.html")

        print(f"\n--- Testing: {name} ---")
        if not bpmn_path.exists():
            print(f"[FAIL] Missing BPMN file: {bpmn_path}")
            all_passed = False
            continue

        temp_html = None
        if not html_path.exists():
            # Dynamically build editor HTML in temp storage
            temp_dir = tempfile.TemporaryDirectory()
            temp_html = Path(temp_dir.name) / f"{name}.html"
            build_editor(bpmn_path, template_path, temp_html, name)
            target_html_path = temp_html
        else:
            target_html_path = html_path

        # 1. Structural & control-flow validation
        print(f"[1/3] Running bpmn_tool.py validate on {bpmn_path.name}:")
        val_res = validate(str(bpmn_path))
        if not val_res:
            print(f"[FAIL] Validation failed for {bpmn_path.name}")
            all_passed = False
            continue

        # 2. DI completeness verification
        print("[2/3] Verifying DI completeness & coordinates:")
        tree = ET.parse(bpmn_path)
        root = tree.getroot()
        BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
        diagram = root.find(f"{{{BPMNDI_NS}}}BPMNDiagram")
        plane = diagram.find(f"{{{BPMNDI_NS}}}BPMNPlane") if diagram is not None else None
        shapes = plane.findall(f"{{{BPMNDI_NS}}}BPMNShape") if plane is not None else []
        edges = plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge") if plane is not None else []
        print(f"      Shapes found: {len(shapes)}, Edges found: {len(edges)}")
        if not shapes or not edges:
            print(f"[FAIL] Incomplete DI for {name}")
            all_passed = False
            continue

        # 3. HTML Round-Trip & Security Contract check
        print("[3/3] Verifying HTML embedding contract (double JSON encoding):")
        html_content = target_html_path.read_text(encoding="utf-8")
        
        # Check no unescaped </script>
        script_pattern = re.compile(r"</script", re.IGNORECASE)
        # Find all occurrences of </script in the document except the legit closing script tag
        closing_tags = re.findall(r"</script>", html_content, re.IGNORECASE)
        # In assets/bpmn-editor-template.html there are exactly 2 script tags (CDN import in head and main script in body)
        if len(closing_tags) != 2:
            print(f"[FAIL] Found unexpected closing script tags ({len(closing_tags)})")
            all_passed = False
            continue

        m = re.search(r'const ORIGINAL_BPMN_XML = JSON\.parse\(("(?:\\.|[^"\\])*")\);', html_content)
        if not m:
            print(f"[FAIL] Could not match JSON.parse literal in {target_html_path.name}")
            all_passed = False
            continue

        encoded_literal = m.group(1)
        try:
            outer = json.loads(encoded_literal)
            inner_xml = json.loads(outer)
            bpmn_raw = bpmn_path.read_text(encoding="utf-8")
            if inner_xml == bpmn_raw:
                print(f"      XML round-trip check: 100% MATCH ({len(inner_xml)} chars)")
            else:
                print(f"[FAIL] Round-trip mismatch: {len(inner_xml)} != {len(bpmn_raw)}")
                all_passed = False
                continue
        except Exception as err:
            print(f"[FAIL] JSON decode exception: {err}")
            all_passed = False
            continue

        print(f"[RESULT] PASS: {name}")

    print("\n==================================================")
    if all_passed:
        print("[SUMMARY] 6/6 TESTS PASSED WITH EVIDENCE.")
        sys.exit(0)
    else:
        print("[SUMMARY] SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
