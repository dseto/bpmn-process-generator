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
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from xml.etree import ElementTree as ET

import lint_rules

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


EDITOR_VERSION_META = '<meta name="bpmn-editor-version"'
_VERSION_RE = re.compile(r'<meta\s+name="bpmn-editor-version"\s+content="([^"]*)"')
_HASH_RE = re.compile(r'(<meta\s+name="bpmn-editor-hash"\s+content=")([^"]*)(")')


def editor_version_of(html):
    """Read the version stamped in an editor.html, or None if it has none."""
    match = _VERSION_RE.search(html)
    return match.group(1) if match else None


def _version_tuple(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except (AttributeError, ValueError):
        return ()


def _hashable_body(html):
    """
    The editor's body for integrity purposes: everything except the two meta
    tags that describe it.

    The version tag is excluded on purpose -- the hash answers "did somebody
    edit this editor?", the version answers "which generation is it?". Folding
    the version into the hash would make every refresh look like a local edit.
    """
    without_hash = _HASH_RE.sub(lambda m: m.group(1) + m.group(3), html)
    return _VERSION_RE.sub('<meta name="bpmn-editor-version" content=""', without_hash)


def _stamp_hash(html):
    """Fill in the integrity hash of the editor being written to a project."""
    digest = hashlib.sha256(_hashable_body(html).encode("utf-8")).hexdigest()
    return _HASH_RE.sub(lambda m: m.group(1) + digest + m.group(3), html)


def was_edited_locally(html):
    """
    True when the project's editor.html no longer matches the hash it was
    delivered with -- i.e. somebody adjusted it by hand and an automatic
    refresh would throw that work away.
    """
    match = _HASH_RE.search(html)
    if not match or not match.group(2):
        return False  # delivered before hashing existed: treat as untouched
    return hashlib.sha256(_hashable_body(html).encode("utf-8")).hexdigest() != match.group(2)


def copy_editor_if_needed(target_dir, bpmn_path=None, force=False):
    """
    Copy editor.html from the skill root to the project directory, configuring it to
    point by default to the generated BPMN diagram. Under no circumstances may it
    point to an example diagram from the skill repository.

    A copy already in the project is refreshed so the project follows the skill
    as it improves -- unless it carries local edits, which are preserved and
    reported instead (`force=True` overwrites them on purpose).
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

    if target_editor.exists() and not force:
        existing = target_editor.read_text(encoding="utf-8")
        if was_edited_locally(existing):
            local_version = editor_version_of(existing)
            skill_version = editor_version_of(source_editor.read_text(encoding="utf-8"))
            outdated = _version_tuple(local_version) < _version_tuple(skill_version)
            print(f"[KEEP] {target_editor} has local edits and was not overwritten"
                  + (f" (it is on {local_version}, the skill ships {skill_version})" if outdated else "")
                  + " -- rerun with --force to replace it with the current editor.")
            return target_editor

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
            xml_json = json.dumps(diagram_xml, ensure_ascii=False).replace('</script', r'<\/script').replace('</SCRIPT', r'<\/SCRIPT')

            # 1. Configura diagrama padrão embutido
            content = re.sub(r'let DEFAULT_DIAGRAM_NAME = .*?;', lambda _: f'let DEFAULT_DIAGRAM_NAME = {name_json};', content)
            content = re.sub(r'let DEFAULT_DIAGRAM_XML = .*?;', lambda _: f'let DEFAULT_DIAGRAM_XML = {xml_json};', content)

            # 2. Atualiza estado e título visual
            content = re.sub(r'let currentFileName = .*?;', lambda _: f'let currentFileName = {name_json};', content)
            content = re.sub(r'<span id="current-filename">.*?</span>', lambda _: f'<span id="current-filename">{diagram_name}</span>', content)
            content = re.sub(r'<title>.*?</title>', lambda _: f'<title>BPMN Editor — {diagram_name}</title>', content)

            # 3. Presets limpos: contém estritamente o diagrama gerado e blank, eliminando exemplos da skill
            presets_replacement = json.dumps({"_blank": BLANK_TEMPLATE, diagram_name: diagram_xml}, ensure_ascii=False)
            presets_replacement = presets_replacement.replace('</script', r'<\/script').replace('</SCRIPT', r'<\/SCRIPT')
            content = re.sub(
                r'/\*PRESETS_START\*/.*?/\*PRESETS_END\*/',
                lambda _: f'/*PRESETS_START*/\n  const PRESETS = {presets_replacement};\n  /*PRESETS_END*/',
                content,
                flags=re.DOTALL
            )

            new_select = f'''<select id="preset-select" title="Diagramas">
      <option value="{diagram_name}" selected>{diagram_name} (Padrão)</option>
      <option value="_blank">+ Novo Diagrama (Em branco)</option>
    </select>'''
            content = re.sub(
                r'<!--PRESET_SELECT_START-->.*?<!--PRESET_SELECT_END-->',
                lambda _: f'<!--PRESET_SELECT_START-->\n    {new_select}\n    <!--PRESET_SELECT_END-->',
                content,
                flags=re.DOTALL
            )

    if not diagram_name:
        # Se nenhum diagrama foi especificado, remove qualquer preset de exemplo da skill
        presets_replacement = json.dumps({"_blank": BLANK_TEMPLATE}, ensure_ascii=False)
        presets_replacement = presets_replacement.replace('</script', r'<\/script').replace('</SCRIPT', r'<\/SCRIPT')
        content = re.sub(
            r'/\*PRESETS_START\*/.*?/\*PRESETS_END\*/',
            lambda _: f'/*PRESETS_START*/\n  const PRESETS = {presets_replacement};\n  /*PRESETS_END*/',
            content,
            flags=re.DOTALL
        )
        new_select = '''<select id="preset-select" title="Diagramas">
      <option value="_blank" selected>+ Novo Diagrama (Em branco)</option>
    </select>'''
        content = re.sub(
            r'<!--PRESET_SELECT_START-->.*?<!--PRESET_SELECT_END-->',
            lambda _: f'<!--PRESET_SELECT_START-->\n    {new_select}\n    <!--PRESET_SELECT_END-->',
            content,
            flags=re.DOTALL
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    target_editor.write_text(_stamp_hash(content), encoding="utf-8")
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
# extract (.bpmn -> process spec, the inverse of bpmn_build.py)
# ---------------------------------------------------------------------------

class ExtractError(Exception):
    """The file cannot be read back as a process spec."""


# An extracted spec is meant to be edited by hand, so it comes out in the short
# aliases `references/process-spec.md` recommends. Tags absent from this map
# extract as themselves (`userTask`, `serviceTask`, ...), which is already the
# short form. Every value here must be a key of bpmn_build.TYPE_ALIASES mapping
# back to the same tag -- test_spec_roundtrip.py holds that contract.
PREFERRED_TYPE_ALIAS = {
    "startEvent": "start",
    "endEvent": "end",
    "exclusiveGateway": "xor",
    "parallelGateway": "and",
    "inclusiveGateway": "or",
    "eventBasedGateway": "eventGateway",
    "intermediateCatchEvent": "catch",
    "intermediateThrowEvent": "throw",
    "boundaryEvent": "boundary",
}


def _event_kind(node_el):
    """<bpmn:timerEventDefinition/> -> 'timer'. Works for any event definition."""
    for child in node_el:
        tag = _tag(child)
        if tag.endswith("EventDefinition"):
            return tag[: -len("EventDefinition")]
    return None


def extract_spec(source):
    """
    Read an existing .bpmn back into the JSON spec that `bpmn_build.py` consumes.

    This closes the loop for "change this process by describing the change":
    extract the spec from the diagram on disk (hand edits in the editor
    included), edit the spec, rebuild. Element ids are reused as the spec's
    internal ids, so a diagram this skill generated rebuilds byte-identical.

    `source` is a path or an already-parsed ElementTree.
    """
    if isinstance(source, ET.ElementTree):
        tree = source
    else:
        try:
            tree = ET.parse(source)
        except ET.ParseError as e:
            raise ExtractError(f"'{source}' is not well-formed XML: {e}") from e
        except OSError as e:
            raise ExtractError(f"cannot read '{source}': {e}") from e

    root = tree.getroot()
    processes = _process_elements(root)
    if not processes:
        raise ExtractError("no <bpmn:process> element found")
    process_el = processes[0]

    # Pools and expanded subprocesses are out of scope for the spec format, and
    # dropping them silently would hand back a spec that rebuilds a SMALLER
    # process than the one on disk. Say so instead.
    if len(processes) > 1:
        print(f"[WARN] the file has {len(processes)} processes (pools); only "
              f"'{process_el.get('id')}' was extracted -- the others would be lost on a rebuild",
              file=sys.stderr)
    nested = [child for child in process_el
              if _tag(child) in ("subProcess", "transaction", "adHocSubProcess")
              and any(_tag(inner) in FLOW_NODE_TAGS for inner in child)]
    if nested:
        print(f"[WARN] expanded subprocess(es) {', '.join(n.get('id', '?') for n in nested)} keep "
              f"their inner flow, which the spec format does not carry -- rebuilding from this "
              f"spec would empty them", file=sys.stderr)

    spec = {"id": process_el.get("id") or "Process_1"}
    if process_el.get("name"):
        spec["name"] = process_el.get("name")
    spec["executable"] = process_el.get("isExecutable") == "true"

    lane_of, lanes = _build_lane_index(process_el)
    if lanes:
        spec["lanes"] = [
            {"id": lane.get("id"), "name": lane.get("name") or lane.get("id")}
            for lane in lanes
        ]

    default_flows = set()
    nodes = []
    for child in process_el:
        tag = _tag(child)
        if tag not in FLOW_NODE_TAGS:
            continue
        nid = child.get("id")
        if not nid:
            continue
        node = {"id": nid, "type": PREFERRED_TYPE_ALIAS.get(tag, tag)}
        if child.get("name"):
            node["name"] = child.get("name")
        kind = _event_kind(child)
        if kind:
            node["event"] = kind
        if tag == "boundaryEvent":
            if child.get("attachedToRef"):
                node["attachedTo"] = child.get("attachedToRef")
            if child.get("cancelActivity") == "false":
                node["interrupting"] = False
        if lanes and nid in lane_of:
            node["lane"] = lanes[lane_of[nid]].get("id")
        if child.get("default"):
            default_flows.add(child.get("default"))
        nodes.append(node)
    spec["nodes"] = nodes

    flows = []
    for flow_el in process_el.findall("bpmn:sequenceFlow", NS):
        flow = {"from": flow_el.get("sourceRef"), "to": flow_el.get("targetRef")}
        if flow_el.get("name"):
            flow["label"] = flow_el.get("name")
        condition = flow_el.find("bpmn:conditionExpression", NS)
        if condition is not None and condition.text:
            flow["condition"] = condition.text.strip()
        if flow_el.get("id") in default_flows:
            flow["default"] = True
            flow.pop("condition", None)  # a default branch is the "nothing matched" one
        flows.append(flow)
    spec["flows"] = flows

    return spec


def run_extract(input_path, output_path=None):
    """Write the extracted spec next to the diagram (or where asked)."""
    spec = extract_spec(input_path)
    out_path = Path(output_path) if output_path else Path(input_path).with_name(
        f"{Path(input_path).stem}-spec.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Wrote spec for {len(spec['nodes'])} node(s) to {out_path}")
    return out_path


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
    """
    Run the rule engine and return (problems, warnings) as plain message lists.

    Kept as the historical entry point: `validate`, `scripts/verify_tests.py`
    and the test suite all speak in terms of these two lists. Callers that need
    the rule id, the offending element or the severity of each finding should
    use `lint_rules.run_rules(tree)` directly -- every check now lives there as
    a named, individually testable rule.
    """
    findings = lint_rules.run_rules(tree)
    return ([f.message for f in lint_rules.errors(findings)],
            [f.message for f in lint_rules.warnings(findings)])


def validate(path, strict=False, as_json=False):
    """
    Validate a .bpmn file. Returns True when it is deliverable.

    `strict` promotes modelling warnings to failures (the gate used in CI and in
    the test suite); style-level `info` findings never fail anything. `as_json`
    prints one machine-readable object instead of the human report, which is how
    the assistant reads the findings and repairs what is mechanical.
    """
    if as_json:
        return _validate_json(path, strict)

    tree = _parse_or_die(path)
    findings = lint_rules.run_rules(tree)
    problems = [f.message for f in lint_rules.errors(findings)]
    warnings = [f.message for f in lint_rules.warnings(findings)]
    infos = [f.message for f in lint_rules.infos(findings)]

    if problems:
        print(f"[FAIL] Stage 2 (control-flow lint): {len(problems)} problem(s)", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        for w in warnings:
            print(f"  [warn] {w}", file=sys.stderr)
        return False

    for w in warnings:
        print(f"[WARN] {w}")
    for i in infos:
        print(f"[INFO] {i}")
    if strict and warnings:
        print(f"[FAIL] --strict: {len(warnings)} warning(s) treated as failures", file=sys.stderr)
        return False
    print("[OK] All checks passed.")
    return True


def _validate_json(path, strict):
    """The --json report. Always prints one JSON object, even for broken XML."""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        payload = {
            "file": str(path),
            "ok": False,
            "strict": strict,
            "counts": {"error": 1, "warn": 0, "info": 0},
            "findings": [{
                "rule": "malformed-xml",
                "severity": "error",
                "element": None,
                "message": f"stage 1 (well-formedness): {e}",
                "fixable": False,
            }],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return False

    findings = lint_rules.run_rules(tree)
    counts = {
        "error": len(lint_rules.errors(findings)),
        "warn": len(lint_rules.warnings(findings)),
        "info": len(lint_rules.infos(findings)),
    }
    ok = counts["error"] == 0 and not (strict and counts["warn"])
    payload = {
        "file": str(path),
        "ok": ok,
        "strict": strict,
        "counts": counts,
        "findings": [f.to_dict() for f in findings],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return ok


# ---------------------------------------------------------------------------
# fix (mechanical repairs only)
# ---------------------------------------------------------------------------

class FixReport:
    """What `run_fix` changed, and what it deliberately left alone."""

    def __init__(self, output, changes, remaining_problems):
        self.output = output
        self.changes = changes
        self.remaining_problems = remaining_problems


def _rebuild_flow_refs(process_el):
    """Make every <bpmn:incoming>/<bpmn:outgoing> agree with the sequenceFlows."""
    changes = []
    nodes, _edges, _issues = build_graph(process_el)
    for child in process_el:
        nid = child.get("id")
        if nid not in nodes:
            continue
        declared_in = [c for c in child if _tag(c) == "incoming"]
        declared_out = [c for c in child if _tag(c) == "outgoing"]
        real_in = [flow_id for flow_id, _src in nodes[nid]["in_edges"]]
        real_out = [flow_id for flow_id, _tgt in nodes[nid]["out_edges"]]
        if (sorted(c.text.strip() for c in declared_in if c.text) == sorted(real_in)
                and sorted(c.text.strip() for c in declared_out if c.text) == sorted(real_out)):
            continue

        for element in declared_in + declared_out:
            child.remove(element)
        # Re-insert ahead of any event definition, which must stay last.
        insert_at = 0
        for flow_id in real_in:
            element = ET.Element(f"{{{BPMN_NS}}}incoming")
            element.text = flow_id
            child.insert(insert_at, element)
            insert_at += 1
        for flow_id in real_out:
            element = ET.Element(f"{{{BPMN_NS}}}outgoing")
            element.text = flow_id
            child.insert(insert_at, element)
            insert_at += 1
        changes.append(f"flow-refs-mismatch: rebuilt incoming/outgoing of '{nid}' from the sequenceFlows")
    return changes


def _flow_signature(flow_el):
    """
    What makes two flows the same CONNECTION rather than the same pair of nodes.

    Label and condition are part of it on purpose: two branches of a gateway can
    legitimately reach the same task under different criteria ("Valor alto" and
    "Cliente novo"), and those are two different statements about the process.
    Collapsing them would delete a decision rule -- exactly what `fix` promises
    never to do.
    """
    condition = flow_el.find("bpmn:conditionExpression", NS)
    return (
        flow_el.get("sourceRef"),
        flow_el.get("targetRef"),
        (flow_el.get("name") or "").strip(),
        (condition.text or "").strip() if condition is not None else "",
    )


def _drop_duplicate_flows(process_el):
    """Remove a sequenceFlow that says exactly what an earlier one already says."""
    changes = []
    seen = {}
    for flow in list(process_el.findall("bpmn:sequenceFlow", NS)):
        src, tgt = flow.get("sourceRef"), flow.get("targetRef")
        if not src or not tgt or src == tgt:
            continue
        signature = _flow_signature(flow)
        if signature not in seen:
            seen[signature] = flow.get("id")
            continue

        removed_id, survivor_id = flow.get("id"), seen[signature]
        process_el.remove(flow)
        changes.append(
            f"duplicate-flow: removed '{removed_id}' ({src} -> {tgt}), identical to "
            f"'{survivor_id}' down to its label and condition")
        # A gateway pointing at the flow we just removed would be left naming a
        # branch that no longer leaves it -- turning a clean file into a broken
        # one. Move the marker to the flow that survived, which is the same
        # branch by every property that defines it.
        for node in process_el:
            if node.get("default") == removed_id:
                node.set("default", survivor_id)
                changes.append(
                    f"default-flow-invalid: '{node.get('id')}' pointed at the removed "
                    f"'{removed_id}'; its default flow is now '{survivor_id}'")
    return changes


def _rename_duplicate_ids(root):
    """
    Give every element its own id, so bpmn-js can import the file at all.

    Only the SECOND and later occurrences are renamed, and references are left
    pointing at the first -- which is what any parser already assumed. The rename
    is reported so a human can confirm that was the intent.
    """
    changes = []
    taken = {el.get("id") for el in root.iter() if el.get("id")}
    seen = set()
    for element in root.iter():
        eid = element.get("id")
        if not eid:
            continue
        if eid not in seen:
            seen.add(eid)
            continue
        n = 2
        while f"{eid}_{n}" in taken:
            n += 1
        new_id = f"{eid}_{n}"
        element.set("id", new_id)
        taken.add(new_id)
        seen.add(new_id)
        changes.append(
            f"duplicate-id: renamed the second <{_tag(element)}> carrying id '{eid}' to '{new_id}' "
            f"-- references still point at the first one; confirm that is what you meant")
    return changes


def run_fix(input_path, output_path=None, dry_run=False):
    """
    Repair what is bookkeeping and leave process decisions to a human.

    Fixes: incoming/outgoing that disagree with the flows, exactly duplicated
    connections, duplicate ids, and missing or degenerate DI. Never adds a node,
    a flow, a condition or a name -- those say what the process IS, and guessing
    them produces a diagram that lints clean and describes the wrong business.
    """
    tree = _parse_or_die(input_path)
    root = tree.getroot()

    changes = _rename_duplicate_ids(root)
    for process_el in _process_elements(root):
        changes.extend(_drop_duplicate_flows(process_el))
        changes.extend(_rebuild_flow_refs(process_el))

    # Recompute the DI whenever it is missing or no longer describes the graph.
    di_findings = [f for f in lint_rules.run_rules(tree)
                   if f.rule in ("missing-diagram", "missing-plane", "missing-shape",
                                  "missing-edge", "edge-waypoints")]
    if di_findings:
        for diagram in root.findall(f"{{{BPMNDI_NS}}}BPMNDiagram"):
            root.remove(diagram)
        for process_el in _process_elements(root):
            root.append(compute_diagram(process_el))
        changes.append(f"layout: recomputed the BPMNDiagram ({len(di_findings)} DI finding(s) "
                        f"including {di_findings[0].rule})")

    out_path = Path(output_path) if output_path else Path(input_path)
    if not dry_run and (changes or out_path != Path(input_path)):
        ET.indent(tree, space="  ")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(out_path, encoding="UTF-8", xml_declaration=True)

    remaining, _warnings = stage2_lint(tree)
    return FixReport(out_path, changes, remaining)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
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
    p_validate.add_argument("--json", dest="as_json", action="store_true",
                             help="Print the findings as one JSON object (rule, severity, element, fixable).")
    p_validate.add_argument("--strict", action="store_true",
                             help="Treat modelling warnings as failures (info-level findings never fail).")

    p_copy = sub.add_parser("copy-editor", help="Copy editor.html to a project directory and configure default diagram.")
    p_copy.add_argument("target_dir", help="Target project directory.")
    p_copy.add_argument("bpmn_file", nargs="?", default=None, help="Optional BPMN diagram to configure as default.")
    p_copy.add_argument("--force", action="store_true",
                         help="Overwrite the project's editor.html even if it carries local edits.")

    p_fix = sub.add_parser("fix", help="Repair mechanical problems (flow refs, duplicate flows/ids, DI).")
    p_fix.add_argument("input", help="Path to the .bpmn file to repair.")
    p_fix.add_argument("-o", "--output", help="Output path (default: repair the file in place).")
    p_fix.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Report what would change without writing anything.")

    p_extract = sub.add_parser("extract", help="Read a .bpmn back into the JSON process spec (inverse of bpmn_build.py).")
    p_extract.add_argument("input", help="Path to the .bpmn file to extract.")
    p_extract.add_argument("-o", "--output",
                            help="Output path (default: <input>-spec.json next to the diagram).")

    args = parser.parse_args(argv)

    if args.command == "layout":
        run_layout(args.input, args.output, copy_editor=args.copy_editor)
    elif args.command == "validate":
        sys.exit(0 if validate(args.file, strict=args.strict, as_json=args.as_json) else 1)
    elif args.command == "copy-editor":
        copied = copy_editor_if_needed(args.target_dir, bpmn_path=args.bpmn_file, force=args.force)
        sys.exit(0 if copied else 1)
    elif args.command == "fix":
        report = run_fix(args.input, args.output, dry_run=args.dry_run)
        prefix = "[DRY-RUN] would apply" if args.dry_run else "[OK] applied"
        if report.changes:
            print(f"{prefix} {len(report.changes)} repair(s) to {report.output}")
            for change in report.changes:
                print(f"  - {change}")
        else:
            print(f"[OK] nothing to repair in {report.output}")
        if report.remaining_problems:
            print(f"[FAIL] {len(report.remaining_problems)} problem(s) need a human decision:",
                  file=sys.stderr)
            for problem in report.remaining_problems:
                print(f"  - {problem}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    elif args.command == "extract":
        try:
            run_extract(args.input, args.output)
        except ExtractError as e:
            print(f"[FAIL] cannot extract a spec: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()
