#!/usr/bin/env python3
"""
build_editor.py - Pack a .bpmn file into a standalone HTML editor based on assets/bpmn-editor-template.html.
Follows the exact encoding contract documented in SKILL.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def build_editor(bpmn_path: Path, template_path: Path, output_path: Path, process_slug: str):
    if not bpmn_path.exists():
        raise FileNotFoundError(f"BPMN file not found: {bpmn_path}")
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    template = template_path.read_text(encoding="utf-8")
    xml_content = bpmn_path.read_text(encoding="utf-8")

    # Step 1: innerJson = JSON.stringify(xmlString)
    inner_json = json.dumps(xml_content)

    # Step 2: outerJson = JSON.stringify(innerJson)
    outer_json = json.dumps(inner_json)

    # Step 3: strip leading and trailing quote characters
    if not (outer_json.startswith('"') and outer_json.endswith('"')):
        raise ValueError("outerJson does not start and end with double quotes")
    content = outer_json[1:-1]

    # Step 4: replace </script with <\/script (case-insensitive)
    content = re.sub(r"</script", r"<\\/script", content, flags=re.IGNORECASE)

    # Step 5: substitute into template
    html = template.replace("PLACEHOLDER_BPMN_XML_JSON", content)
    html = html.replace("PLACEHOLDER_PROCESS_NAME", process_slug)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] Generated HTML editor: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Embed BPMN XML into standalone HTML editor.")
    parser.add_argument("bpmn", type=Path, help="Path to the input .bpmn file")
    parser.add_argument("-o", "--output", type=Path, help="Path to the output .html file")
    parser.add_argument("-t", "--template", type=Path, default=Path("assets/bpmn-editor-template.html"), help="Path to template HTML")
    parser.add_argument("-s", "--slug", type=str, help="Process name slug (defaults to input filename stem)")

    args = parser.parse_args()
    slug = args.slug or args.bpmn.stem
    out = args.output or args.bpmn.with_suffix(".html")

    build_editor(args.bpmn, args.template, out, slug)


if __name__ == "__main__":
    main()
