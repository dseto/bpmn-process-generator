#!/usr/bin/env python3
"""
bpmn_tool.py - layout and validate BPMN 2.0 .bpmn files. Pure stdlib, no XSD.

Two subcommands:

    python bpmn_tool.py layout <in>.bpmn [-o <out>.bpmn]
        Compute BPMNDiagram DI (BPMNShape + BPMNEdge, plus lane bands when a
        laneSet is present) for every <bpmn:process> in the file and write it
        out, replacing any existing (possibly stale) <bpmndi:BPMNDiagram>.

    python bpmn_tool.py validate <file>.bpmn
        Two-stage check, stopping at the first stage with hard failures:
          1. well-formedness (valid XML syntax)
          2. control-flow lint (graph-level checks: DI completeness, start/end
             presence, reachability, dead ends, duplicate ids, parallel
             split/join balance)
        Deliberately does NOT do BPMN 2.0 XSD schema validation: bpmn-js's own
        importXML (via bpmn-moddle) already rejects structurally invalid BPMN
        the moment the user opens the generated HTML, which is the real
        acceptance test for this skill. Skipping it keeps this script
        dependency-free (no lxml/xmlschema, no bundled OMG schema files).

Both subcommands share the same tag list and graph-building logic
(FLOW_NODE_TAGS, build_graph) so layout and validate agree on what counts as
a flow node.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from xml.etree import ElementTree as ET

BLANK_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  id="Definitions_NewProcess"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_Novo" name="Novo Processo" isExecutable="false">
    <bpmn:startEvent id="Start_1" name="Início" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_Process_Novo">
    <bpmndi:BPMNPlane id="BPMNPlane_Process_Novo" bpmnElement="Process_Novo">
      <bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1">
        <omgdc:Bounds x="160" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NS = {"bpmn": BPMN_NS}

# Registering all five prefixes (not just the bpmndi/omgdc/omgdi trio) matters:
# ET.register_namespace is process-global, so if "bpmn" and "xsi" aren't
# registered here, re-serializing the WHOLE document (not just the DI section
# we add) comes out with auto-generated ns0: prefixes on every bpmn: element.
ET.register_namespace("bpmn", BPMN_NS)
ET.register_namespace("bpmndi", BPMNDI_NS)
ET.register_namespace("omgdc", DC_NS)
ET.register_namespace("omgdi", DI_NS)
ET.register_namespace("xsi", XSI_NS)

FLOW_NODE_TAGS = {
    "startEvent", "endEvent", "task", "userTask", "serviceTask",
    "sendTask", "receiveTask", "manualTask", "scriptTask", "businessRuleTask",
    "exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway",
    "complexGateway",
    "subProcess", "callActivity", "transaction", "adHocSubProcess",
    "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent",
}

SIZES = {
    "startEvent": (36, 36), "endEvent": (36, 36),
    "intermediateCatchEvent": (36, 36), "intermediateThrowEvent": (36, 36),
    "boundaryEvent": (36, 36),
    "exclusiveGateway": (50, 50), "parallelGateway": (50, 50),
    "inclusiveGateway": (50, 50), "eventBasedGateway": (50, 50),
    "complexGateway": (50, 50),
}
DEFAULT_SIZE = (100, 80)  # tasks, subprocesses, transactions, call activities

COL_SPACING = 150
ROW_SPACING = 120
BASE_X = 160
BASE_Y = 120
LANE_SLOTS = 3          # row-units of vertical room reserved per lane band
LANE_PADDING = 40
BACK_EDGE_DROP = 60     # how far below the row a back-edge dips before crossing


def _tag(el):
    return el.tag.split("}")[-1]


# ---------------------------------------------------------------------------
# Shared graph building (used by both `layout` and `validate`)
# ---------------------------------------------------------------------------

def build_graph(process_el):
    """
    Build a {id: {"tag", "in_edges", "out_edges", "attachedToRef"}} node index
    plus a flat edge list [(flow_id, src, tgt), ...] for a <bpmn:process>.

    Elements missing an `id` are skipped from the node index (an id-less node
    would otherwise silently "match" another id-less node, or a sequenceFlow
    with a missing sourceRef/targetRef) and reported as an issue instead.

    in_edges/out_edges are LISTS of (flow_id, other_id) tuples, not sets of
    unique neighbor ids -- callers that need "how many distinct flows" (e.g.
    the parallel split/join check) must count these lists; callers that need
    "which nodes are reachable" should dedupe on the fly.
    """
    nodes = {}
    issues = []
    for child in process_el:
        t = _tag(child)
        if t in FLOW_NODE_TAGS:
            nid = child.get("id")
            if not nid:
                issues.append(f"a '{t}' element has no id attribute (skipped)")
                continue
            nodes[nid] = {
                "tag": t,
                "in_edges": [],
                "out_edges": [],
                "attachedToRef": child.get("attachedToRef"),
            }

    edges = []
    for flow in process_el.findall("bpmn:sequenceFlow", NS):
        fid = flow.get("id")
        src = flow.get("sourceRef")
        tgt = flow.get("targetRef")
        if not fid:
            issues.append("a sequenceFlow element has no id attribute (skipped)")
            continue
        if not src or not tgt:
            issues.append(f"sequenceFlow '{fid}' is missing sourceRef and/or targetRef")
            continue
        edges.append((fid, src, tgt))
        if src in nodes:
            nodes[src]["out_edges"].append((fid, tgt))
        if tgt in nodes:
            nodes[tgt]["in_edges"].append((fid, src))
    return nodes, edges, issues


def _process_elements(root):
    return root.findall("bpmn:process", NS)


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------

def _topo_order(nodes):
    """
    Topological order used for longest-path column layering. Falls back to a
    best-effort order (fewest unresolved predecessors first) for any nodes
    left over once Kahn's algorithm stalls on a cycle, so rework/back-edge
    loops don't hang layout.
    """
    succ = {nid: [t for _, t in n["out_edges"] if t in nodes] for nid, n in nodes.items()}
    pred = {nid: [s for _, s in n["in_edges"] if s in nodes] for nid, n in nodes.items()}
    unique_indeg = {nid: len(set(pred[nid])) for nid in nodes}

    order = []
    seen = set()
    queue = [nid for nid in nodes if unique_indeg[nid] == 0]
    remaining_indeg = dict(unique_indeg)
    qi = 0
    while qi < len(queue):
        nid = queue[qi]
        qi += 1
        if nid in seen:
            continue
        seen.add(nid)
        order.append(nid)
        for t in set(succ[nid]):
            if t in seen:
                continue
            remaining_indeg[t] -= 1
            if remaining_indeg[t] <= 0:
                queue.append(t)

    if len(order) < len(nodes):
        remaining = [nid for nid in nodes if nid not in seen]
        while remaining:
            remaining.sort(key=lambda nid: sum(1 for p in set(pred[nid]) if p not in seen))
            nid = remaining.pop(0)
            seen.add(nid)
            order.append(nid)

    return order, pred, succ


def _assign_columns(order, pred):
    col = {}
    for nid in order:
        preds_placed = [p for p in set(pred[nid]) if p in col]
        col[nid] = 0 if not preds_placed else 1 + max(col[p] for p in preds_placed)
    return col


def _assign_raw_rows(nodes, order, starts):
    """
    Seed each start event at a distinct row (spread around 0) and propagate a
    row to each node's successors the first time it's reached (branch offsets
    fan out around the source row). Row assignment is independent of column
    assignment now, so a parallel-join's row no longer depends on which
    branch's BFS got there first in a way that would place it in the wrong
    column -- that's handled purely by _assign_columns's longest-path rule.
    """
    raw_row = {}
    n_starts = len(starts)
    for i, nid in enumerate(starts):
        raw_row[nid] = i - (n_starts - 1) / 2.0

    for nid in order:
        if nid not in raw_row:
            continue
        row0 = raw_row[nid]
        seen_targets = []
        for _, t in nodes[nid]["out_edges"]:
            if t in nodes and t not in seen_targets:
                seen_targets.append(t)
        n_out = len(seen_targets)
        for i, t in enumerate(seen_targets):
            if t in raw_row:
                continue
            offset = 0.0 if n_out == 1 else (i - (n_out - 1) / 2.0)
            raw_row[t] = row0 + offset

    for nid in nodes:
        raw_row.setdefault(nid, 0.0)
    return raw_row


def _build_lane_index(process_el):
    lane_set = process_el.find("bpmn:laneSet", NS)
    if lane_set is None:
        return None, []
    lanes = lane_set.findall("bpmn:lane", NS)
    lane_of = {}
    for i, lane in enumerate(lanes):
        for ref in lane.findall("bpmn:flowNodeRef", NS):
            if ref.text:
                lane_of[ref.text.strip()] = i
    return lane_of, lanes


def _resolve_collisions(order, col, final_row):
    """Nudge a node's row outward (whole-row steps) until its (col, row) cell is free."""
    occupied = set()
    positions = {}
    for nid in order:
        c = col[nid]
        r = final_row[nid]
        key = (c, round(r * 2))
        if key in occupied:
            k = 1
            while True:
                moved = False
                for delta in (k, -k):
                    cand = r + delta
                    cand_key = (c, round(cand * 2))
                    if cand_key not in occupied:
                        r, key = cand, cand_key
                        moved = True
                        break
                if moved:
                    break
                k += 1
        occupied.add(key)
        positions[nid] = (c, r)
    return positions


def _edge_waypoints(src_bounds, tgt_bounds, src_col, tgt_col):
    sx, sy, sw, sh = src_bounds
    tx, ty, tw, th = tgt_bounds
    if tgt_col <= src_col:
        # Back-edge (rework loop): a straight line would cut back across the
        # diagram through whatever sits between target and source. Route it
        # below both nodes instead: down, across, up.
        start = (sx + sw / 2.0, sy + sh)
        end = (tx + tw / 2.0, ty + th)
        drop_y = max(sy + sh, ty + th) + BACK_EDGE_DROP
        return [start, (start[0], drop_y), (end[0], drop_y), end]
    start = (sx + sw, sy + sh / 2.0)
    end = (tx, ty + th / 2.0)
    if abs(start[1] - end[1]) < 1.0:
        return [start, end]
    # Orthogonal 90-degree routing (Manhattan staircase) for forward edges across different levels:
    mid_x = (start[0] + end[0]) / 2.0
    return [start, (mid_x, start[1]), (mid_x, end[1]), end]


def compute_diagram(process_el):
    """Compute a <bpmndi:BPMNDiagram> element for one <bpmn:process>."""
    process_id = process_el.get("id")
    nodes, edges, _issues = build_graph(process_el)

    diagram = ET.Element(f"{{{BPMNDI_NS}}}BPMNDiagram", {"id": f"BPMNDiagram_{process_id}"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI_NS}}}BPMNPlane",
                           {"id": f"BPMNPlane_{process_id}", "bpmnElement": process_id})

    if not nodes:
        return diagram

    order, pred, succ = _topo_order(nodes)
    col = _assign_columns(order, pred)
    starts = [nid for nid in order if nodes[nid]["tag"] == "startEvent"]
    raw_row = _assign_raw_rows(nodes, order, starts)

    lane_of, lanes = _build_lane_index(process_el)
    final_row = {}
    if lane_of is not None:
        half_span = (LANE_SLOTS - 1) / 2.0
        for nid in nodes:
            r = max(-half_span, min(half_span, raw_row.get(nid, 0.0)))
            lane_idx = lane_of.get(nid, 0)
            final_row[nid] = lane_idx * LANE_SLOTS + half_span + r
    else:
        final_row = dict(raw_row)

    positions = _resolve_collisions(order, col, final_row)

    bounds = {}
    for nid, (c, r) in positions.items():
        w, h = SIZES.get(nodes[nid]["tag"], DEFAULT_SIZE)
        x = BASE_X + c * COL_SPACING
        y = BASE_Y + r * ROW_SPACING - h / 2.0
        bounds[nid] = (x, y, w, h)

    if lane_of is not None:
        max_col = max((c for c, _ in positions.values()), default=0)
        diagram_width = BASE_X + (max_col + 1) * COL_SPACING + LANE_PADDING
        lane_height = LANE_SLOTS * ROW_SPACING
        for i, lane in enumerate(lanes):
            band_top = BASE_Y - ROW_SPACING / 2.0 + i * lane_height
            lane_shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", {
                "id": f"{lane.get('id')}_di",
                "bpmnElement": lane.get("id"),
                "isHorizontal": "true",
            })
            ET.SubElement(lane_shape, f"{{{DC_NS}}}Bounds", {
                "x": "0", "y": str(int(band_top)),
                "width": str(int(diagram_width)), "height": str(int(lane_height)),
            })

    for nid, (x, y, w, h) in bounds.items():
        shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                               {"id": f"{nid}_di", "bpmnElement": nid})
        ET.SubElement(shape, f"{{{DC_NS}}}Bounds",
                      {"x": str(int(x)), "y": str(int(y)), "width": str(w), "height": str(h)})

    for fid, src, tgt in edges:
        if src not in bounds or tgt not in bounds:
            continue  # dangling ref; `validate` will already have flagged this
        edge = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge",
                              {"id": f"{fid}_di", "bpmnElement": fid})
        for (wx, wy) in _edge_waypoints(bounds[src], bounds[tgt], col[src], col[tgt]):
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(wx)), "y": str(int(wy))})

    return diagram


def copy_editor_if_needed(target_dir, bpmn_path=None):
    """
    Copy editor.html from the skill root to the project directory, configuring it to
    point by default to the generated BPMN diagram. Under no circumstances may it
    point to an example diagram from the skill repository.
    """
    root_dir = Path(__file__).resolve().parent.parent
    source_editor = root_dir / "editor.html"
    if not source_editor.exists():
        return None

    target_dir = Path(target_dir).resolve()
    # Skip if target_dir is the root of the skill or internal test/reference directories
    internal_dirs = {
        root_dir.resolve(),
        (root_dir / "tests").resolve(),
        (root_dir / "references").resolve(),
    }
    if target_dir in internal_dirs:
        return None

    target_editor = target_dir / "editor.html"

    # If bpmn_path is not specified, discover if there is a .bpmn file in target_dir
    if bpmn_path is None:
        bpmn_candidates = list(target_dir.glob("*.bpmn"))
        if len(bpmn_candidates) == 1:
            bpmn_path = bpmn_candidates[0]
        elif len(bpmn_candidates) > 1:
            bpmn_path = max(bpmn_candidates, key=lambda f: f.stat().st_mtime)

    content = source_editor.read_text(encoding="utf-8")
    diagram_name = None

    if bpmn_path:
        bpmn_file = Path(bpmn_path).resolve()
        if bpmn_file.exists():
            diagram_name = bpmn_file.name
            diagram_xml = bpmn_file.read_text(encoding="utf-8")

            name_json = json.dumps(diagram_name, ensure_ascii=False)
            xml_json = re.sub(
                r'</script', r'<\\/script',
                json.dumps(diagram_xml, ensure_ascii=False),
                flags=re.IGNORECASE
            )

            # 1. Configura diagrama padrão embutido
            content = content.replace('let DEFAULT_DIAGRAM_NAME = "";', f'let DEFAULT_DIAGRAM_NAME = {name_json};')
            content = content.replace('let DEFAULT_DIAGRAM_XML = null;', f'let DEFAULT_DIAGRAM_XML = {xml_json};')

            # 2. Atualiza estado e título visual
            content = content.replace('let currentFileName = "diagrama.bpmn";', f'let currentFileName = {name_json};')
            content = content.replace('<span id="current-filename">diagrama.bpmn</span>', f'<span id="current-filename">{diagram_name}</span>')
            content = content.replace('<title>BPMN Editor Central</title>', f'<title>BPMN Editor — {diagram_name}</title>')

            # 3. Presets limpos: contém estritamente o diagrama gerado e blank, eliminando exemplos da skill
            presets_replacement = json.dumps({"_blank": BLANK_TEMPLATE, diagram_name: diagram_xml}, ensure_ascii=False)
            presets_replacement = re.sub(r'</script', r'<\\/script', presets_replacement, flags=re.IGNORECASE)
            content = re.sub(
                r'/\*PRESETS_START\*/.*?/\*PRESETS_END\*/',
                f'/*PRESETS_START*/\n  const PRESETS = {presets_replacement};\n  /*PRESETS_END*/',
                content,
                flags=re.DOTALL
            )

            new_select = f'''<select id="preset-select" title="Diagramas">
      <option value="{diagram_name}" selected>{diagram_name} (Padrão)</option>
      <option value="_blank">+ Novo Diagrama (Em branco)</option>
    </select>'''
            content = re.sub(
                r'<!--PRESET_SELECT_START-->.*?<!--PRESET_SELECT_END-->',
                f'<!--PRESET_SELECT_START-->\n    {new_select}\n    <!--PRESET_SELECT_END-->',
                content,
                flags=re.DOTALL
            )

    if not diagram_name:
        # Se nenhum diagrama foi especificado, remove qualquer preset de exemplo da skill
        presets_replacement = json.dumps({"_blank": BLANK_TEMPLATE}, ensure_ascii=False)
        content = re.sub(
            r'/\*PRESETS_START\*/.*?/\*PRESETS_END\*/',
            f'/*PRESETS_START*/\n  const PRESETS = {presets_replacement};\n  /*PRESETS_END*/',
            content,
            flags=re.DOTALL
        )
        new_select = '''<select id="preset-select" title="Diagramas">
      <option value="_blank" selected>+ Novo Diagrama (Em branco)</option>
    </select>'''
        content = re.sub(
            r'<!--PRESET_SELECT_START-->.*?<!--PRESET_SELECT_END-->',
            f'<!--PRESET_SELECT_START-->\n    {new_select}\n    <!--PRESET_SELECT_END-->',
            content,
            flags=re.DOTALL
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    target_editor.write_text(content, encoding="utf-8")
    if diagram_name:
        print(f"[OK] Copied and configured editor in project: {target_editor} (default: {diagram_name})")
    else:
        print(f"[OK] Copied central editor to project directory: {target_editor}")
    return target_editor


def run_layout(input_path, output_path=None, copy_editor=True):
    tree = _parse_or_die(input_path)
    root = tree.getroot()
    for diagram in root.findall(f"{{{BPMNDI_NS}}}BPMNDiagram"):
        root.remove(diagram)
    processes = _process_elements(root)
    if not processes:
        print("[FAIL] No <bpmn:process> element found in the input file.", file=sys.stderr)
        sys.exit(1)
    for process_el in processes:
        root.append(compute_diagram(process_el))
    out_path = output_path or input_path
    out_file = Path(out_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)
    print(f"[OK] Wrote layout for {len(processes)} process(es) to {out_path}")
    if copy_editor:
        copy_editor_if_needed(out_file.parent, bpmn_path=out_file)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def _parse_or_die(path):
    try:
        return ET.parse(path)
    except ET.ParseError as e:
        print(f"[FAIL] Stage 1 (well-formedness): {e}", file=sys.stderr)
        sys.exit(1)


def _di_index(root):
    diagrams = root.findall(f"{{{BPMNDI_NS}}}BPMNDiagram")
    shape_ids = set()
    edge_ids = set()
    edge_waypoints = {}
    plane_elements = []
    for diagram in diagrams:
        for plane in diagram.findall(f"{{{BPMNDI_NS}}}BPMNPlane"):
            plane_elements.append(plane.get("bpmnElement"))
            for shape in plane.findall(f"{{{BPMNDI_NS}}}BPMNShape"):
                be = shape.get("bpmnElement")
                if be:
                    shape_ids.add(be)
            for edge in plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge"):
                be = edge.get("bpmnElement")
                if be:
                    edge_ids.add(be)
                    edge_waypoints[be] = len(edge.findall(f"{{{DI_NS}}}waypoint"))
    return {
        "has_diagram": bool(diagrams),
        "shape_ids": shape_ids,
        "edge_ids": edge_ids,
        "edge_waypoints": edge_waypoints,
        "plane_elements": plane_elements,
    }


def stage2_lint(tree):
    root = tree.getroot()
    problems = []
    warnings = []

    # Duplicate ids anywhere in the document are a total-failure case:
    # bpmn-js's importXML hard-fails on them before the user sees anything.
    all_ids = [el.get("id") for el in root.iter() if el.get("id")]
    counts = {}
    for eid in all_ids:
        counts[eid] = counts.get(eid, 0) + 1
    for eid in sorted(eid for eid, c in counts.items() if c > 1):
        problems.append(f"duplicate element id '{eid}' used {counts[eid]} times "
                         f"(bpmn-js will refuse to import this)")

    di = _di_index(root)
    if not di["has_diagram"]:
        problems.append("no <bpmndi:BPMNDiagram> found -- the file will open as a "
                         "completely empty canvas in bpmn-js")

    processes = _process_elements(root)
    if not processes:
        problems.append("no <bpmn:process> element found")

    for process in processes:
        pid = process.get("id", "<unnamed process>")
        nodes, edges, issues = build_graph(process)
        for issue in issues:
            problems.append(f"[{pid}] {issue}")

        for fid, src, tgt in edges:
            if src not in nodes:
                problems.append(f"[{pid}] sequenceFlow '{fid}' has sourceRef '{src}' with no matching node")
            if tgt not in nodes:
                problems.append(f"[{pid}] sequenceFlow '{fid}' has targetRef '{tgt}' with no matching node")

        if di["has_diagram"]:
            if pid not in di["plane_elements"]:
                problems.append(f"[{pid}] no BPMNPlane found with bpmnElement=\"{pid}\"")
            for nid in nodes:
                if nid not in di["shape_ids"]:
                    problems.append(f"[{pid}] flow node '{nid}' has no matching BPMNShape")
            for fid, _, _ in edges:
                if fid not in di["edge_ids"]:
                    problems.append(f"[{pid}] sequenceFlow '{fid}' has no matching BPMNEdge")
                elif di["edge_waypoints"].get(fid, 0) < 2:
                    problems.append(f"[{pid}] BPMNEdge for sequenceFlow '{fid}' has fewer than 2 waypoints")

        starts = [nid for nid, n in nodes.items() if n["tag"] == "startEvent"]
        ends = [nid for nid, n in nodes.items() if n["tag"] == "endEvent"]
        if not starts:
            problems.append(f"[{pid}] no startEvent found")
        if not ends:
            problems.append(f"[{pid}] no endEvent found")

        # boundaryEvents attach via attachedToRef, not a sequenceFlow -- index
        # that relationship once so the incoming-flow and reachability checks
        # below can special-case them.
        attached_boundary = {}
        for nid, n in nodes.items():
            if n["tag"] == "boundaryEvent" and n.get("attachedToRef"):
                attached_boundary.setdefault(n["attachedToRef"], []).append(nid)
                if n["attachedToRef"] not in nodes:
                    problems.append(f"[{pid}] boundaryEvent '{nid}' has attachedToRef "
                                     f"'{n['attachedToRef']}' with no matching node")

        for nid, n in nodes.items():
            tag = n["tag"]
            in_count = len(n["in_edges"])
            out_count = len(n["out_edges"])
            if tag == "boundaryEvent":
                pass  # no incoming sequenceFlow is normal for these
            elif tag != "startEvent" and in_count == 0:
                problems.append(f"[{pid}] node '{nid}' ({tag}) is unreachable (no incoming flow)")
            if tag != "endEvent" and out_count == 0:
                problems.append(f"[{pid}] node '{nid}' ({tag}) is a dead end (no outgoing flow)")

        node_ids = set(nodes.keys())
        if starts:
            seen = set()
            stack = list(starts)
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                for _, t in nodes.get(cur, {}).get("out_edges", []):
                    stack.append(t)
                for bnid in attached_boundary.get(cur, []):
                    stack.append(bnid)
            for nid in sorted(node_ids - seen):
                problems.append(f"[{pid}] node '{nid}' is not reachable from any startEvent")

        # Parallel split/join balance: for each gateway that actually splits
        # (2+ outgoing FLOWS, not 2+ distinct targets -- two flows can share a
        # target), search forward for a parallel-join gateway (2+ incoming
        # flows) reachable downstream. An unrelated join elsewhere in the
        # process, or one upstream of the split, no longer counts.
        for nid, n in nodes.items():
            if n["tag"] == "parallelGateway" and len(n["out_edges"]) >= 2:
                seen2 = set()
                stack = [t for _, t in n["out_edges"]]
                found_join = False
                while stack:
                    cur = stack.pop()
                    if cur in seen2:
                        continue
                    seen2.add(cur)
                    other = nodes.get(cur)
                    if other is None:
                        continue
                    if other["tag"] == "parallelGateway" and len(other["in_edges"]) >= 2:
                        found_join = True
                        break
                    stack.extend(t for _, t in other["out_edges"])
                    stack.extend(attached_boundary.get(cur, []))
                if not found_join:
                    warnings.append(
                        f"[{pid}] parallelGateway '{nid}' splits into {len(n['out_edges'])} branches "
                        f"with no parallel join reachable downstream -- confirm independent "
                        f"parallel outcomes are intentional"
                    )

    return problems, warnings


def validate(path):
    tree = _parse_or_die(path)
    problems, warnings = stage2_lint(tree)
    if problems:
        print(f"[FAIL] Stage 2 (control-flow lint): {len(problems)} problem(s)", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        for w in warnings:
            print(f"  [warn] {w}", file=sys.stderr)
        return False
    for w in warnings:
        print(f"[WARN] {w}")
    print("[OK] All checks passed.")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="bpmn_tool.py",
        description="Layout and validate BPMN 2.0 .bpmn files (pure stdlib, no XSD).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_layout = sub.add_parser("layout", help="Compute BPMNDiagram DI for a .bpmn file's process(es).")
    p_layout.add_argument("input", help="Path to the .bpmn file to lay out.")
    p_layout.add_argument("-o", "--output", help="Output path (default: overwrite the input file).")
    p_layout.add_argument("--no-copy-editor", dest="copy_editor", action="store_false", default=True,
                           help="Do not copy editor.html to the project directory.")

    p_validate = sub.add_parser("validate", help="Run well-formedness + control-flow lint on a .bpmn file.")
    p_validate.add_argument("file", help="Path to the .bpmn file to validate.")

    p_copy = sub.add_parser("copy-editor", help="Copy editor.html to a project directory and configure default diagram.")
    p_copy.add_argument("target_dir", help="Target project directory.")
    p_copy.add_argument("bpmn_file", nargs="?", default=None, help="Optional BPMN diagram to configure as default.")

    args = parser.parse_args()

    if args.command == "layout":
        run_layout(args.input, args.output, copy_editor=args.copy_editor)
    elif args.command == "validate":
        sys.exit(0 if validate(args.file) else 1)
    elif args.command == "copy-editor":
        copied = copy_editor_if_needed(args.target_dir, bpmn_path=args.bpmn_file)
        sys.exit(0 if copied else 1)


if __name__ == "__main__":
    main()
