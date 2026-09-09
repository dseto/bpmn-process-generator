#!/usr/bin/env python3
"""
bpmn_build.py - build a BPMN 2.0 document from a compact JSON process spec.

Writing BPMN XML by hand is where diagram generation goes wrong: ids drift,
`<bpmn:incoming>`/`<bpmn:outgoing>` children stop matching the actual
`sequenceFlow` `sourceRef`/`targetRef` (nothing in the file itself complains),
and gateway branches lose their conditions. This module removes that whole
class of error by making the spec the only thing anyone writes:

    {
      "id": "Process_Suporte",
      "name": "Atendimento de suporte",
      "nodes": [
        {"id": "inicio",  "type": "start",    "name": "Chamado aberto"},
        {"id": "revisar", "type": "userTask", "name": "Revisar chamado"},
        {"id": "fim",     "type": "end",      "name": "Chamado encerrado"}
      ],
      "flows": [
        {"from": "inicio",  "to": "revisar"},
        {"from": "revisar", "to": "fim"}
      ]
    }

Ids in the output are derived from the spec (readable, PascalCase, accent-free,
prefixed by element kind) and the incoming/outgoing children are DERIVED from
the flow list rather than typed a second time, so they cannot disagree with it.

The spec contract is documented in `references/process-spec.md`; the canonical
example lives in `references/example-spec.json`.

Layout (DI) is not this module's job: feed the result to
`bpmn_tool.compute_diagram`, exactly as `bpmn_tool.py layout` does.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

# Importing bpmn_tool also registers the five canonical namespace prefixes
# process-globally, which is what keeps ET from emitting ns0: prefixes here.
from bpmn_tool import BPMN_NS, BPMNDI_NS, DC_NS, DI_NS, XSI_NS


class SpecError(Exception):
    """The spec is malformed. Raised instead of emitting a broken diagram."""


# Short aliases first (what a spec should normally use), then the canonical
# BPMN tag names, accepted so a spec extracted back out of a .bpmn file round
# trips without translation.
TYPE_ALIASES = {
    "start": "startEvent",
    "end": "endEvent",
    "task": "task",
    "userTask": "userTask",
    "serviceTask": "serviceTask",
    "sendTask": "sendTask",
    "receiveTask": "receiveTask",
    "manualTask": "manualTask",
    "scriptTask": "scriptTask",
    "businessRuleTask": "businessRuleTask",
    "xor": "exclusiveGateway",
    "and": "parallelGateway",
    "or": "inclusiveGateway",
    "eventGateway": "eventBasedGateway",
    "catch": "intermediateCatchEvent",
    "throw": "intermediateThrowEvent",
    "boundary": "boundaryEvent",
    "subProcess": "subProcess",
    "callActivity": "callActivity",
    "startEvent": "startEvent",
    "endEvent": "endEvent",
    "exclusiveGateway": "exclusiveGateway",
    "parallelGateway": "parallelGateway",
    "inclusiveGateway": "inclusiveGateway",
    "eventBasedGateway": "eventBasedGateway",
    "intermediateCatchEvent": "intermediateCatchEvent",
    "intermediateThrowEvent": "intermediateThrowEvent",
    "boundaryEvent": "boundaryEvent",
}

# `event` on a node: which <bpmn:*EventDefinition> child to add.
EVENT_DEFINITIONS = {
    "message": "messageEventDefinition",
    "timer": "timerEventDefinition",
    "error": "errorEventDefinition",
    "signal": "signalEventDefinition",
    "escalation": "escalationEventDefinition",
    "conditional": "conditionalEventDefinition",
    "compensate": "compensateEventDefinition",
    "link": "linkEventDefinition",
    "terminate": "terminateEventDefinition",
}

EVENT_TAGS = {
    "startEvent", "endEvent", "boundaryEvent",
    "intermediateCatchEvent", "intermediateThrowEvent",
}

# What a boundaryEvent may be attached to.
ACTIVITY_TAGS = {
    "task", "userTask", "serviceTask", "sendTask", "receiveTask",
    "manualTask", "scriptTask", "businessRuleTask",
    "subProcess", "callActivity",
}

GATEWAY_TAGS = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway",
}

ID_PREFIXES = {
    "startEvent": "Start",
    "endEvent": "End",
    "exclusiveGateway": "Gateway",
    "parallelGateway": "Gateway",
    "inclusiveGateway": "Gateway",
    "eventBasedGateway": "Gateway",
    "intermediateCatchEvent": "Event",
    "intermediateThrowEvent": "Event",
    "boundaryEvent": "Event",
    "subProcess": "SubProcess",
    "callActivity": "Activity",
}
DEFAULT_ID_PREFIX = "Task"  # every task flavour


def _bpmn(tag):
    return f"{{{BPMN_NS}}}{tag}"


# ---------------------------------------------------------------------------
# Id derivation
# ---------------------------------------------------------------------------

def strip_accents(text):
    """'Aprovação' -> 'Aprovacao'. Ids stay ASCII; names keep their accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def pascal_case(text):
    """
    'Conferir nota fiscal' -> 'ConferirNotaFiscal', 'Resolvível?' -> 'Resolvivel'.

    Only the first letter of each token is forced upper: an already-capitalised
    acronym in the middle of a name ('Emitir NFe') survives as written.
    """
    tokens = [t for t in re.split(r"[^0-9A-Za-z]+", strip_accents(text)) if t]
    return "".join(t[0].upper() + t[1:] for t in tokens)


def _unique(candidate, taken):
    """Append _2, _3, ... until the id is free. Keeps generation deterministic."""
    if candidate not in taken:
        taken.add(candidate)
        return candidate
    n = 2
    while f"{candidate}_{n}" in taken:
        n += 1
    unique = f"{candidate}_{n}"
    taken.add(unique)
    return unique


# ---------------------------------------------------------------------------
# Spec normalisation
# ---------------------------------------------------------------------------

def load_spec(path):
    """Read a spec from disk, failing with SpecError on anything unusable."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise SpecError(f"cannot read spec file '{path}': {e}") from e
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SpecError(f"spec '{path}' is not valid JSON: {e}") from e
    if not isinstance(spec, dict):
        raise SpecError(f"spec '{path}' must be a JSON object, got {type(spec).__name__}")
    return spec


def _normalise_nodes(spec):
    """
    Resolve every spec node to (spec_id, bpmn_tag, generated_id, node_dict).

    Ids are generated in spec order, so the same spec always yields the same
    document.
    """
    nodes = spec.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise SpecError("spec must have a non-empty 'nodes' list")

    taken = set()
    resolved = []
    seen_spec_ids = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise SpecError(f"each node must be an object, got {type(node).__name__}")
        spec_id = node.get("id")
        if not spec_id or not isinstance(spec_id, str):
            raise SpecError(f"node without a usable 'id': {node!r}")
        if spec_id in seen_spec_ids:
            raise SpecError(f"duplicate node id '{spec_id}' in the spec")
        seen_spec_ids.add(spec_id)

        alias = node.get("type")
        if alias not in TYPE_ALIASES:
            raise SpecError(
                f"node '{spec_id}' has unknown type '{alias}' "
                f"(known types: {', '.join(sorted(TYPE_ALIASES))})"
            )
        tag = TYPE_ALIASES[alias]

        event = node.get("event")
        if event is not None:
            if event not in EVENT_DEFINITIONS:
                raise SpecError(
                    f"node '{spec_id}' has unknown event '{event}' "
                    f"(known events: {', '.join(sorted(EVENT_DEFINITIONS))})"
                )
            if tag not in EVENT_TAGS:
                raise SpecError(
                    f"node '{spec_id}' is a '{alias}', which cannot carry an event "
                    f"definition -- 'event' only applies to start/end/catch/throw/boundary"
                )

        label = node.get("name") or spec_id
        prefix = ID_PREFIXES.get(tag, DEFAULT_ID_PREFIX)
        generated = _unique(f"{prefix}_{pascal_case(label)}", taken)
        resolved.append((spec_id, tag, generated, node))

    _check_boundary_hosts(resolved)
    return resolved


def _check_boundary_hosts(resolved_nodes):
    """A boundaryEvent must hang off an activity that exists in the same spec."""
    tag_of_spec_id = {spec_id: tag for spec_id, tag, _generated, _node in resolved_nodes}
    for spec_id, tag, _generated, node in resolved_nodes:
        if tag != "boundaryEvent":
            continue
        host = node.get("attachedTo")
        if not host:
            raise SpecError(f"boundary event '{spec_id}' needs 'attachedTo' naming its activity")
        if host not in tag_of_spec_id:
            raise SpecError(f"boundary event '{spec_id}' is attached to unknown node '{host}'")
        if tag_of_spec_id[host] not in ACTIVITY_TAGS:
            raise SpecError(
                f"boundary event '{spec_id}' is attached to '{host}', which is a "
                f"'{tag_of_spec_id[host]}' -- boundary events only attach to activities"
            )


def _normalise_flows(spec, id_of, tag_of_spec_id):
    """Resolve every flow to (flow_id, source_id, target_id, flow_dict)."""
    flows = spec.get("flows")
    if flows is None:
        flows = []
    if not isinstance(flows, list):
        raise SpecError("'flows' must be a list")

    resolved = []
    for i, flow in enumerate(flows, start=1):
        if not isinstance(flow, dict):
            raise SpecError(f"flow #{i} must be an object, got {type(flow).__name__}")
        src = flow.get("from")
        tgt = flow.get("to")
        if not src or not tgt:
            raise SpecError(f"flow #{i} needs both 'from' and 'to': {flow!r}")
        if src not in id_of:
            raise SpecError(f"flow #{i} starts at unknown node '{src}'")
        if tgt not in id_of:
            raise SpecError(f"flow #{i} ends at unknown node '{tgt}'")
        if flow.get("default"):
            # The default flow is the branch taken when no condition matched,
            # so it is a gateway concept and it cannot itself be conditioned.
            if tag_of_spec_id[src] not in GATEWAY_TAGS:
                raise SpecError(
                    f"flow #{i} is marked as default but leaves '{src}', which is a "
                    f"'{tag_of_spec_id[src]}' -- only gateways have a default flow"
                )
            if flow.get("condition"):
                raise SpecError(
                    f"flow #{i} is marked as default AND carries a condition -- the "
                    f"default branch is the one taken when no condition matched"
                )
        resolved.append((f"Flow_{i}", id_of[src], id_of[tgt], flow))
    return resolved


def _normalise_lanes(spec, resolved_nodes):
    """
    Resolve the laneSet to [(lane_id, lane_name, [node ids]), ...].

    Every flow node lands in exactly one lane: a node without `lane` falls into
    the first declared lane, which keeps `flowNodeRef` coverage complete (an
    uncovered node is what makes bpmn-js render a node floating outside the
    pool).
    """
    lanes = spec.get("lanes")
    if not lanes:
        return []
    if not isinstance(lanes, list):
        raise SpecError("'lanes' must be a list")

    lane_ids = []
    members = {}
    taken = set()
    for i, lane in enumerate(lanes, start=1):
        if not isinstance(lane, dict):
            raise SpecError(f"lane #{i} must be an object, got {type(lane).__name__}")
        spec_lane_id = lane.get("id") or lane.get("name")
        if not spec_lane_id:
            raise SpecError(f"lane #{i} needs an 'id' or a 'name'")
        if spec_lane_id in members:
            raise SpecError(f"duplicate lane id '{spec_lane_id}' in the spec")
        label = lane.get("name") or spec_lane_id
        lane_ids.append((spec_lane_id, _unique(f"Lane_{pascal_case(label)}", taken), label))
        members[spec_lane_id] = []

    default_lane = lane_ids[0][0]
    for spec_id, _tag, generated, node in resolved_nodes:
        lane_ref = node.get("lane") or default_lane
        if lane_ref not in members:
            raise SpecError(f"node '{spec_id}' points at unknown lane '{lane_ref}'")
        members[lane_ref].append(generated)

    return [(generated_id, label, members[spec_lane_id])
            for spec_lane_id, generated_id, label in lane_ids]


# ---------------------------------------------------------------------------
# Document building
# ---------------------------------------------------------------------------

def _process_id(spec):
    raw = spec.get("id") or spec.get("name") or "Process"
    if isinstance(raw, str) and raw.startswith("Process_"):
        return raw
    return f"Process_{pascal_case(str(raw))}"


def build_tree(spec):
    """Build the <bpmn:definitions> document for a spec (no DI section)."""
    resolved_nodes = _normalise_nodes(spec)
    id_of = {spec_id: generated for spec_id, _tag, generated, _node in resolved_nodes}
    tag_of_spec_id = {spec_id: tag for spec_id, tag, _generated, _node in resolved_nodes}
    resolved_flows = _normalise_flows(spec, id_of, tag_of_spec_id)
    resolved_lanes = _normalise_lanes(spec, resolved_nodes)

    incoming = {generated: [] for _s, _t, generated, _n in resolved_nodes}
    outgoing = {generated: [] for _s, _t, generated, _n in resolved_nodes}
    default_of = {}
    for flow_id, src, tgt, flow in resolved_flows:
        outgoing[src].append(flow_id)
        incoming[tgt].append(flow_id)
        if flow.get("default"):
            default_of[src] = flow_id

    process_id = _process_id(spec)
    root = ET.Element(_bpmn("definitions"), {
        "id": f"Definitions_{process_id.split('_', 1)[-1]}",
        "targetNamespace": "http://bpmn.io/schema/bpmn",
    })
    process_attrs = {"id": process_id, "isExecutable": "true" if spec.get("executable") else "false"}
    if spec.get("name"):
        process_attrs["name"] = spec["name"]
    process = ET.SubElement(root, _bpmn("process"), process_attrs)

    # The XSD wants the laneSet ahead of the flow elements it references.
    if resolved_lanes:
        lane_set = ET.SubElement(process, _bpmn("laneSet"), {"id": f"LaneSet_{process_id.split('_', 1)[-1]}"})
        for lane_id, label, member_ids in resolved_lanes:
            lane = ET.SubElement(lane_set, _bpmn("lane"), {"id": lane_id, "name": label})
            for member in member_ids:
                ET.SubElement(lane, _bpmn("flowNodeRef")).text = member

    for _spec_id, tag, generated, node in resolved_nodes:
        attrs = {"id": generated}
        if node.get("name"):
            attrs["name"] = node["name"]
        if tag == "boundaryEvent":
            attrs["attachedToRef"] = id_of[node["attachedTo"]]
            attrs["cancelActivity"] = "false" if node.get("interrupting") is False else "true"
        if generated in default_of:
            attrs["default"] = default_of[generated]
        el = ET.SubElement(process, _bpmn(tag), attrs)
        for flow_id in incoming[generated]:
            ET.SubElement(el, _bpmn("incoming")).text = flow_id
        for flow_id in outgoing[generated]:
            ET.SubElement(el, _bpmn("outgoing")).text = flow_id
        if node.get("event"):
            ET.SubElement(el, _bpmn(EVENT_DEFINITIONS[node["event"]]))

    for flow_id, src, tgt, flow in resolved_flows:
        attrs = {"id": flow_id}
        if flow.get("label"):
            attrs["name"] = flow["label"]
        attrs["sourceRef"] = src
        attrs["targetRef"] = tgt
        flow_el = ET.SubElement(process, _bpmn("sequenceFlow"), attrs)
        if flow.get("condition"):
            condition = ET.SubElement(flow_el, _bpmn("conditionExpression"),
                                       {f"{{{XSI_NS}}}type": "bpmn:tFormalExpression"})
            condition.text = flow["condition"]

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    return tree


CANONICAL_NAMESPACES = {
    "bpmn": BPMN_NS,
    "bpmndi": BPMNDI_NS,
    "omgdc": DC_NS,
    "omgdi": DI_NS,
    "xsi": XSI_NS,
}


def _declare_canonical_namespaces(xml):
    """
    Add the canonical prefixes ElementTree left out of <bpmn:definitions>.

    ET only declares a namespace it actually used, so a spec with no gateway
    conditions and no DI section comes out declaring `bpmn:` alone. Every BPMN
    tool (and `references/bpmn-xml-structure.md`) expects all five prefixes on
    the root element, and the file is readable on its own before
    `bpmn_tool layout` adds the DI, so fill the gap here.
    """
    open_tag_end = xml.index(">", xml.index("<bpmn:definitions"))
    head, tail = xml[:open_tag_end], xml[open_tag_end:]
    missing = [
        f' xmlns:{prefix}="{uri}"'
        for prefix, uri in CANONICAL_NAMESPACES.items()
        if f'xmlns:{prefix}="' not in head
    ]
    return head + "".join(missing) + tail


def _serialise(tree):
    xml = ET.tostring(tree.getroot(), encoding="UTF-8", xml_declaration=True).decode("utf-8")
    return _declare_canonical_namespaces(xml)


def build_xml(spec):
    """Serialise the spec to a BPMN 2.0 XML string (UTF-8 declaration included)."""
    return _serialise(build_tree(spec))


# ---------------------------------------------------------------------------
# One command: generate + lay out + validate + hand over the editor
# ---------------------------------------------------------------------------

class BuildResult:
    """
    What one `run_build` produced: where the file landed, whether the linter
    accepted it, and where the editor for it is.

    `problems` empty means the diagram is deliverable. It is a return value
    rather than an exception because the file is written either way -- a
    diagram the linter rejects is still the fastest thing to open and fix.
    """

    def __init__(self, output, problems, warnings, editor=None):
        self.output = output
        self.problems = problems
        self.warnings = warnings
        self.editor = editor


def _default_output(spec_path):
    """references/example-spec.json -> references/example-spec.bpmn"""
    return Path(spec_path).with_suffix(".bpmn")


def run_build(spec_path, output_path=None, copy_editor=True):
    """
    Spec file -> laid-out, validated .bpmn on disk, with the editor beside it.

    Deliberately mirrors what `bpmn_tool.py layout` does after generation, so
    there is exactly one layout engine and one linter in the skill.
    """
    from bpmn_tool import compute_diagram, copy_editor_if_needed, stage2_lint

    spec = load_spec(spec_path)
    tree = build_tree(spec)
    root = tree.getroot()
    for process in root.findall(f"{{{BPMN_NS}}}process"):
        root.append(compute_diagram(process))
    ET.indent(tree, space="  ")

    out_file = Path(output_path) if output_path else _default_output(spec_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(_serialise(tree), encoding="utf-8")

    problems, warnings = stage2_lint(ET.parse(out_file))
    # Pass the file explicitly so the editor opens THIS diagram, instead of
    # letting copy_editor_if_needed guess by mtime among the project's .bpmn files.
    editor = copy_editor_if_needed(out_file.parent, out_file) if copy_editor else None
    return BuildResult(out_file, problems, warnings, editor)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="bpmn_build.py",
        description="Build a laid-out, validated BPMN 2.0 diagram from a JSON process spec.",
    )
    parser.add_argument("spec", help="Path to the .json process spec (see references/process-spec.md).")
    parser.add_argument("-o", "--output",
                        help="Where to write the .bpmn (default: the spec path with a .bpmn extension).")
    parser.add_argument("--no-copy-editor", dest="copy_editor", action="store_false", default=True,
                        help="Do not copy editor.html next to the generated diagram.")
    args = parser.parse_args(argv)

    try:
        result = run_build(args.spec, args.output, copy_editor=args.copy_editor)
    except SpecError as e:
        print(f"[FAIL] spec rejected: {e}", file=sys.stderr)
        return 1

    print(f"[OK] Wrote {result.output}")
    if result.editor:
        print(f"[OK] Editor available at {result.editor}")
    for warning in result.warnings:
        print(f"[WARN] {warning}")
    if result.problems:
        print(f"[FAIL] Stage 2 (control-flow lint): {len(result.problems)} problem(s)", file=sys.stderr)
        for problem in result.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("[OK] All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
