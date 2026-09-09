#!/usr/bin/env python3
"""
lint_rules.py - the rule engine behind `bpmn_tool.py validate`.

Each check is a named rule with its own severity, registered by a decorator:

    @register("dead-end", "error")
    def _dead_end(document):
        ...
        yield Finding(...)

Why this shape rather than one long function: a finding can then say WHICH rule
fired and how badly it matters ("error" blocks delivery, "warn" is modelling
advice, "info" is style), the assistant can read the findings as JSON and repair
what is mechanically fixable, and adding a check is a new function plus its test
rather than another branch in a growing block.

The rules run against a `Document` context built once per file, so every rule
sees the same graph, the same DI index and the same boundary-event index instead
of rebuilding them.
"""
from xml.etree import ElementTree as ET

SEVERITIES = ("error", "warn", "info")


class Finding:
    """One problem found in one file."""

    __slots__ = ("rule", "severity", "element", "message", "fixable")

    def __init__(self, rule, severity, message, element=None, fixable=False):
        self.rule = rule
        self.severity = severity
        self.message = message
        self.element = element
        self.fixable = fixable

    def to_dict(self):
        return {
            "rule": self.rule,
            "severity": self.severity,
            "element": self.element,
            "message": self.message,
            "fixable": self.fixable,
        }

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<Finding {self.severity} {self.rule} {self.element}: {self.message}>"


class Rule:
    __slots__ = ("name", "severity", "fixable", "check")

    def __init__(self, name, severity, fixable, check):
        self.name = name
        self.severity = severity
        self.fixable = fixable
        self.check = check


RULES = []


def register(name, severity, fixable=False):
    """Register a rule. Rules run in registration order, so errors come first."""
    if severity not in SEVERITIES:
        raise ValueError(f"rule '{name}' has unknown severity '{severity}' "
                         f"(expected one of {', '.join(SEVERITIES)})")
    if any(rule.name == name for rule in RULES):
        raise ValueError(f"rule '{name}' is already registered")

    def decorator(func):
        RULES.append(Rule(name, severity, fixable, func))
        return func

    return decorator


# ---------------------------------------------------------------------------
# Context shared by every rule
# ---------------------------------------------------------------------------

class Process:
    """One <bpmn:process> with its graph already built."""

    def __init__(self, element, nodes, edges, issues, attached_boundary):
        self.element = element
        self.id = element.get("id", "<unnamed process>")
        self.nodes = nodes
        self.edges = edges
        self.issues = issues
        self.attached_boundary = attached_boundary
        self.elements = {child.get("id"): child for child in element if child.get("id")}

    def element_of(self, node_id):
        return self.elements.get(node_id)

    def reaches_an_end_event(self):
        """
        Ids from which SOME path arrives at an endEvent.

        Walks backwards from the end events (following incoming flows, and the
        host of every boundary event), which is the only way to see a loop where
        every node has an outgoing flow yet the process can never finish.
        """
        reaching = set()
        stack = [nid for nid, node in self.nodes.items() if node["tag"] == "endEvent"]
        while stack:
            current = stack.pop()
            if current in reaching:
                continue
            reaching.add(current)
            node = self.nodes.get(current)
            if node is None:
                continue
            for _flow_id, source in node["in_edges"]:
                stack.append(source)
            if node["tag"] == "boundaryEvent" and node.get("attachedToRef"):
                stack.append(node["attachedToRef"])
        return reaching


class Document:
    """One .bpmn file: its processes, its DI index, and the raw tree."""

    def __init__(self, tree):
        # Imported here rather than at module scope: bpmn_tool imports this
        # module, so a top-level import would be circular.
        from bpmn_tool import _build_lane_index, _di_index, _process_elements, build_graph

        self.tree = tree
        self.root = tree.getroot()
        self.di = _di_index(self.root)
        self.processes = []
        for process_el in _process_elements(self.root):
            nodes, edges, issues = build_graph(process_el)
            attached_boundary = {}
            for nid, node in nodes.items():
                if node["tag"] == "boundaryEvent" and node.get("attachedToRef"):
                    attached_boundary.setdefault(node["attachedToRef"], []).append(nid)
            self.processes.append(Process(process_el, nodes, edges, issues, attached_boundary))
        self.lane_index = {
            process.id: _build_lane_index(process.element) for process in self.processes
        }

    def reachable_from_starts(self, process):
        starts = [nid for nid, n in process.nodes.items() if n["tag"] == "startEvent"]
        seen = set()
        stack = list(starts)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for _flow_id, target in process.nodes.get(current, {}).get("out_edges", []):
                stack.append(target)
            for boundary_id in process.attached_boundary.get(current, []):
                stack.append(boundary_id)
        return seen


def run_rules(tree):
    """Run every registered rule over a parsed .bpmn and return the findings."""
    document = Document(tree)
    findings = []
    for rule in RULES:
        for finding in rule.check(document) or []:
            findings.append(finding)
    return findings


def errors(findings):
    return [f for f in findings if f.severity == "error"]


def warnings(findings):
    return [f for f in findings if f.severity == "warn"]


def infos(findings):
    return [f for f in findings if f.severity == "info"]


def _finding(rule, document_or_process, message, element=None, fixable=False):
    """Prefix the message with the process id, so multi-process files stay readable."""
    severity = next(r.severity for r in RULES if r.name == rule)
    if isinstance(document_or_process, Process):
        message = f"[{document_or_process.id}] {message}"
    return Finding(rule, severity, message, element=element, fixable=fixable)


# ---------------------------------------------------------------------------
# Document-level rules
# ---------------------------------------------------------------------------

@register("duplicate-id", "error")
def _duplicate_id(document):
    counts = {}
    for element in document.root.iter():
        eid = element.get("id")
        if eid:
            counts[eid] = counts.get(eid, 0) + 1
    for eid in sorted(eid for eid, count in counts.items() if count > 1):
        yield _finding(
            "duplicate-id", document,
            f"duplicate element id '{eid}' used {counts[eid]} times "
            f"(bpmn-js will refuse to import this)",
            element=eid,
        )


@register("missing-diagram", "error")
def _missing_diagram(document):
    if not document.di["has_diagram"]:
        yield _finding(
            "missing-diagram", document,
            "no <bpmndi:BPMNDiagram> found -- the file will open as a "
            "completely empty canvas in bpmn-js",
        )


@register("missing-process", "error")
def _missing_process(document):
    if not document.processes:
        yield _finding("missing-process", document, "no <bpmn:process> element found")


# ---------------------------------------------------------------------------
# Structural rules, per process
# ---------------------------------------------------------------------------

@register("malformed-element", "error")
def _malformed_element(document):
    for process in document.processes:
        for issue in process.issues:
            yield _finding("malformed-element", process, issue)


@register("dangling-flow-ref", "error")
def _dangling_flow_ref(document):
    for process in document.processes:
        for flow_id, src, tgt in process.edges:
            if src not in process.nodes:
                yield _finding("dangling-flow-ref", process,
                               f"sequenceFlow '{flow_id}' has sourceRef '{src}' with no matching node",
                               element=flow_id)
            if tgt not in process.nodes:
                yield _finding("dangling-flow-ref", process,
                               f"sequenceFlow '{flow_id}' has targetRef '{tgt}' with no matching node",
                               element=flow_id)


@register("missing-plane", "error")
def _missing_plane(document):
    if not document.di["has_diagram"]:
        return
    for process in document.processes:
        if process.id not in document.di["plane_elements"]:
            yield _finding("missing-plane", process,
                           f'no BPMNPlane found with bpmnElement="{process.id}"',
                           element=process.id)


@register("missing-shape", "error")
def _missing_shape(document):
    if not document.di["has_diagram"]:
        return
    for process in document.processes:
        for nid in process.nodes:
            if nid not in document.di["shape_ids"]:
                yield _finding("missing-shape", process,
                               f"flow node '{nid}' has no matching BPMNShape",
                               element=nid, fixable=True)


@register("missing-edge", "error")
def _missing_edge(document):
    if not document.di["has_diagram"]:
        return
    for process in document.processes:
        for flow_id, _src, _tgt in process.edges:
            if flow_id not in document.di["edge_ids"]:
                yield _finding("missing-edge", process,
                               f"sequenceFlow '{flow_id}' has no matching BPMNEdge",
                               element=flow_id, fixable=True)


@register("edge-waypoints", "error")
def _edge_waypoints(document):
    if not document.di["has_diagram"]:
        return
    for process in document.processes:
        for flow_id, _src, _tgt in process.edges:
            if flow_id not in document.di["edge_ids"]:
                continue
            if document.di["edge_waypoints"].get(flow_id, 0) < 2:
                yield _finding("edge-waypoints", process,
                               f"BPMNEdge for sequenceFlow '{flow_id}' has fewer than 2 waypoints",
                               element=flow_id, fixable=True)


@register("missing-start-event", "error")
def _missing_start_event(document):
    for process in document.processes:
        if not any(n["tag"] == "startEvent" for n in process.nodes.values()):
            yield _finding("missing-start-event", process, "no startEvent found")


@register("missing-end-event", "error")
def _missing_end_event(document):
    for process in document.processes:
        if not any(n["tag"] == "endEvent" for n in process.nodes.values()):
            yield _finding("missing-end-event", process, "no endEvent found")


@register("boundary-host-missing", "error")
def _boundary_host_missing(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            host = node.get("attachedToRef")
            if node["tag"] == "boundaryEvent" and host and host not in process.nodes:
                yield _finding("boundary-host-missing", process,
                               f"boundaryEvent '{nid}' has attachedToRef '{host}' with no matching node",
                               element=nid)


@register("unreachable-node", "error")
def _unreachable_node(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            tag = node["tag"]
            if tag in ("boundaryEvent", "startEvent"):
                continue  # boundary events hang off an activity, starts begin the flow
            if not node["in_edges"]:
                yield _finding("unreachable-node", process,
                               f"node '{nid}' ({tag}) is unreachable (no incoming flow)",
                               element=nid)


@register("dead-end", "error")
def _dead_end(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] != "endEvent" and not node["out_edges"]:
                yield _finding("dead-end", process,
                               f"node '{nid}' ({node['tag']}) is a dead end (no outgoing flow)",
                               element=nid)


@register("not-reachable-from-start", "error")
def _not_reachable_from_start(document):
    for process in document.processes:
        if not any(n["tag"] == "startEvent" for n in process.nodes.values()):
            continue
        seen = document.reachable_from_starts(process)
        for nid in sorted(set(process.nodes) - seen):
            yield _finding("not-reachable-from-start", process,
                           f"node '{nid}' is not reachable from any startEvent",
                           element=nid)


@register("flow-refs-mismatch", "error", fixable=True)
def _flow_refs_mismatch(document):
    """
    The <bpmn:incoming>/<bpmn:outgoing> children must list exactly the flows
    that actually point at (or leave) the node.

    This is the failure mode of hand-written BPMN: nothing in the file objects,
    bpmn-js renders from sourceRef/targetRef, and other tools read the child
    elements -- so the two disagree about what the process is. `bpmn_build.py`
    derives these children from the flows precisely so they cannot drift.
    """
    from bpmn_tool import _tag

    for process in document.processes:
        for nid, node in process.nodes.items():
            element = process.element_of(nid)
            if element is None:
                continue
            declared_in = [c.text.strip() for c in element if _tag(c) == "incoming" and c.text]
            declared_out = [c.text.strip() for c in element if _tag(c) == "outgoing" and c.text]
            real_in = [flow_id for flow_id, _src in node["in_edges"]]
            real_out = [flow_id for flow_id, _tgt in node["out_edges"]]
            if sorted(declared_in) != sorted(real_in):
                yield _finding(
                    "flow-refs-mismatch", process,
                    f"node '{nid}' declares incoming {sorted(declared_in) or '[]'} but the "
                    f"sequenceFlows say {sorted(real_in) or '[]'}",
                    element=nid, fixable=True,
                )
            if sorted(declared_out) != sorted(real_out):
                yield _finding(
                    "flow-refs-mismatch", process,
                    f"node '{nid}' declares outgoing {sorted(declared_out) or '[]'} but the "
                    f"sequenceFlows say {sorted(real_out) or '[]'}",
                    element=nid, fixable=True,
                )


@register("start-has-incoming", "error")
def _start_has_incoming(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] == "startEvent" and node["in_edges"]:
                yield _finding("start-has-incoming", process,
                               f"startEvent '{nid}' has an incoming flow -- a start event begins "
                               f"the process; loop back to a task or gateway instead",
                               element=nid)


@register("end-has-outgoing", "error")
def _end_has_outgoing(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] == "endEvent" and node["out_edges"]:
                yield _finding("end-has-outgoing", process,
                               f"endEvent '{nid}' has an outgoing flow -- nothing happens after "
                               f"an end event",
                               element=nid)


@register("default-flow-invalid", "error")
def _default_flow_invalid(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            element = process.element_of(nid)
            if element is None:
                continue
            default = element.get("default")
            if not default:
                continue
            if default not in [flow_id for flow_id, _tgt in node["out_edges"]]:
                yield _finding("default-flow-invalid", process,
                               f"'{nid}' names '{default}' as its default flow, but that flow "
                               f"does not leave it",
                               element=nid)


@register("boundary-invalid", "error")
def _boundary_invalid(document):
    activities = {
        "task", "userTask", "serviceTask", "sendTask", "receiveTask",
        "manualTask", "scriptTask", "businessRuleTask",
        "subProcess", "callActivity", "transaction", "adHocSubProcess",
    }
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] != "boundaryEvent":
                continue
            host = node.get("attachedToRef")
            if not host:
                yield _finding("boundary-invalid", process,
                               f"boundaryEvent '{nid}' has no attachedToRef -- it is not attached "
                               f"to anything and bpmn-js cannot place it",
                               element=nid)
                continue
            host_node = process.nodes.get(host)
            if host_node and host_node["tag"] not in activities:
                yield _finding("boundary-invalid", process,
                               f"boundaryEvent '{nid}' is attached to '{host}', which is a "
                               f"{host_node['tag']} -- boundary events only attach to activities",
                               element=nid)


@register("no-path-to-end", "error")
def _no_path_to_end(document):
    for process in document.processes:
        if not any(n["tag"] == "endEvent" for n in process.nodes.values()):
            continue  # missing-end-event already covers this
        reaching = process.reaches_an_end_event()
        reachable = document.reachable_from_starts(process)
        for nid in sorted(set(process.nodes) - reaching):
            if nid not in reachable:
                continue  # not-reachable-from-start already covers this
            if not process.nodes[nid]["out_edges"]:
                continue  # dead-end already covers this
            yield _finding("no-path-to-end", process,
                           f"node '{nid}' can never reach an endEvent -- every path out of it "
                           f"loops forever",
                           element=nid)


@register("lane-coverage-duplicate", "error")
def _lane_coverage_duplicate(document):
    from bpmn_tool import NS

    for process in document.processes:
        lane_set = process.element.find("bpmn:laneSet", NS)
        if lane_set is None:
            continue
        seen = {}
        for lane in lane_set.findall("bpmn:lane", NS):
            lane_id = lane.get("id", "<unnamed lane>")
            for ref in lane.findall("bpmn:flowNodeRef", NS):
                if not ref.text:
                    continue
                node_id = ref.text.strip()
                if node_id in seen:
                    yield _finding("lane-coverage-duplicate", process,
                                   f"node '{node_id}' is listed in lane '{seen[node_id]}' and "
                                   f"lane '{lane_id}' -- a node belongs to exactly one lane",
                                   element=node_id)
                else:
                    seen[node_id] = lane_id


GATEWAY_TAGS = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway",
}


@register("implicit-split", "warn")
def _implicit_split(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] in GATEWAY_TAGS:
                continue
            if len(node["out_edges"]) > 1:
                yield _finding(
                    "implicit-split", process,
                    f"'{nid}' ({node['tag']}) has {len(node['out_edges'])} outgoing flows without "
                    f"a gateway -- readers cannot tell whether the branches are alternatives (XOR) "
                    f"or parallel (AND)",
                    element=nid,
                )


@register("implicit-merge", "warn")
def _implicit_merge(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] in GATEWAY_TAGS or node["tag"] == "endEvent":
                continue
            if len(node["in_edges"]) > 1:
                yield _finding(
                    "implicit-merge", process,
                    f"'{nid}' ({node['tag']}) receives {len(node['in_edges'])} flows without a "
                    f"gateway -- readers cannot tell whether it waits for all of them or runs "
                    f"on the first",
                    element=nid,
                )


@register("gateway-without-condition", "warn")
def _gateway_without_condition(document):
    """A data-based split must say what decides each branch."""
    from bpmn_tool import NS

    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] not in ("exclusiveGateway", "inclusiveGateway"):
                continue
            if len(node["out_edges"]) < 2:
                continue
            element = process.element_of(nid)
            default = element.get("default") if element is not None else None
            unconditioned = []
            for flow_id, _target in node["out_edges"]:
                if flow_id == default:
                    continue
                flow_el = process.element_of(flow_id)
                if flow_el is None:
                    continue
                condition = flow_el.find("bpmn:conditionExpression", NS)
                if condition is None or not (condition.text or "").strip():
                    unconditioned.append(flow_id)
            if unconditioned:
                yield _finding(
                    "gateway-without-condition", process,
                    f"{node['tag']} '{nid}' splits without a condition on "
                    f"{', '.join(sorted(unconditioned))} and without a default flow -- the "
                    f"criterion of the decision is not written down",
                    element=nid,
                )


@register("mixed-gateway", "warn")
def _mixed_gateway(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] not in GATEWAY_TAGS:
                continue
            if len(node["in_edges"]) > 1 and len(node["out_edges"]) > 1:
                yield _finding(
                    "mixed-gateway", process,
                    f"gateway '{nid}' merges {len(node['in_edges'])} flows and splits into "
                    f"{len(node['out_edges'])} at once -- split the merge and the branch into "
                    f"two gateways so the diagram reads in one direction",
                    element=nid,
                )


@register("parallel-join-without-split", "warn")
def _parallel_join_without_split(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] != "parallelGateway" or len(node["in_edges"]) < 2:
                continue
            seen = set()
            stack = [source for _flow_id, source in node["in_edges"]]
            found_split = False
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                other = process.nodes.get(current)
                if other is None:
                    continue
                if other["tag"] == "parallelGateway" and len(other["out_edges"]) >= 2:
                    found_split = True
                    break
                stack.extend(source for _flow_id, source in other["in_edges"])
            if not found_split:
                yield _finding(
                    "parallel-join-without-split", process,
                    f"parallelGateway '{nid}' waits for {len(node['in_edges'])} flows with no "
                    f"parallel split upstream -- it will block forever unless every branch "
                    f"really is started",
                    element=nid,
                )


@register("unnamed-element", "warn")
def _unnamed_element(document):
    interesting = GATEWAY_TAGS | {
        "task", "userTask", "serviceTask", "sendTask", "receiveTask",
        "manualTask", "scriptTask", "businessRuleTask", "subProcess", "callActivity",
        "startEvent", "endEvent",
    }
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] not in interesting:
                continue
            element = process.element_of(nid)
            if element is None or (element.get("name") or "").strip():
                continue
            yield _finding("unnamed-element", process,
                           f"'{nid}' ({node['tag']}) has no name -- it renders as an empty box",
                           element=nid)


@register("duplicate-flow", "warn")
def _duplicate_flow(document):
    """
    Two flows saying the same thing between the same pair of nodes.

    Label and condition count as part of what a flow says: two gateway branches
    reaching the same task under different criteria are two different rules of
    the process, not a duplicate.
    """
    from bpmn_tool import NS

    for process in document.processes:
        seen = {}
        for flow_id, src, tgt in process.edges:
            if src == tgt:
                continue  # self-loop reports it
            element = process.element_of(flow_id)
            label, condition_text = "", ""
            if element is not None:
                label = (element.get("name") or "").strip()
                condition = element.find("bpmn:conditionExpression", NS)
                condition_text = (condition.text or "").strip() if condition is not None else ""
            signature = (src, tgt, label, condition_text)
            if signature in seen:
                yield _finding("duplicate-flow", process,
                               f"'{flow_id}' repeats the connection {src} -> {tgt} already made by "
                               f"'{seen[signature]}', with the same label and condition",
                               element=flow_id, fixable=True)
            else:
                seen[signature] = flow_id


@register("self-loop", "warn")
def _self_loop(document):
    for process in document.processes:
        for flow_id, src, tgt in process.edges:
            if src == tgt:
                yield _finding("self-loop", process,
                               f"'{flow_id}' connects '{src}' to itself -- model the rework as a "
                               f"gateway back to an earlier step instead",
                               element=flow_id)


@register("lane-coverage-missing", "warn")
def _lane_coverage_missing(document):
    from bpmn_tool import NS

    for process in document.processes:
        lane_set = process.element.find("bpmn:laneSet", NS)
        if lane_set is None:
            continue
        covered = set()
        for lane in lane_set.findall("bpmn:lane", NS):
            for ref in lane.findall("bpmn:flowNodeRef", NS):
                if ref.text:
                    covered.add(ref.text.strip())
        for nid in sorted(set(process.nodes) - covered):
            yield _finding("lane-coverage-missing", process,
                           f"'{nid}' is in no lane -- it will render outside the pool",
                           element=nid)


@register("di-overlap", "warn")
def _di_overlap(document):
    """
    Two flow-node shapes sitting on top of each other. Lane bands are skipped:
    a band legitimately contains every node it owns.
    """
    from bpmn_tool import BPMNDI_NS, DC_NS

    node_ids = set()
    for process in document.processes:
        node_ids.update(process.nodes)

    boxes = []
    for diagram in document.root.findall(f"{{{BPMNDI_NS}}}BPMNDiagram"):
        for plane in diagram.findall(f"{{{BPMNDI_NS}}}BPMNPlane"):
            for shape in plane.findall(f"{{{BPMNDI_NS}}}BPMNShape"):
                element_id = shape.get("bpmnElement")
                if element_id not in node_ids:
                    continue
                bounds = shape.find(f"{{{DC_NS}}}Bounds")
                if bounds is None:
                    continue
                try:
                    box = (float(bounds.get("x", 0)), float(bounds.get("y", 0)),
                           float(bounds.get("width", 0)), float(bounds.get("height", 0)))
                except ValueError:
                    continue
                boxes.append((element_id, box))

    process_for_message = document.processes[0] if document.processes else document
    for i, (id_a, (ax, ay, aw, ah)) in enumerate(boxes):
        for id_b, (bx, by, bw, bh) in boxes[i + 1:]:
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                yield _finding("di-overlap", process_for_message,
                               f"shapes of '{id_a}' and '{id_b}' overlap on the canvas -- one of "
                               f"them is hidden behind the other",
                               element=id_a)


@register("useless-gateway", "info")
def _useless_gateway(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] not in GATEWAY_TAGS:
                continue
            if len(node["in_edges"]) <= 1 and len(node["out_edges"]) <= 1:
                yield _finding("useless-gateway", process,
                               f"gateway '{nid}' neither splits nor merges -- it adds a decision "
                               f"symbol to a straight line",
                               element=nid)


@register("id-convention", "info")
def _id_convention(document):
    """Readable ids (`Task_ReviewApplication`) make every other message readable."""
    import re

    pattern = re.compile(r"^[A-Z][A-Za-z0-9]*_[A-Za-z0-9]+$")
    for process in document.processes:
        for nid in sorted(process.nodes):
            if not pattern.match(nid):
                yield _finding("id-convention", process,
                               f"id '{nid}' is off the '<Type>_<Description>' convention, which "
                               f"makes every lint message about it harder to place",
                               element=nid)


@register("name-too-long", "info")
def _name_too_long(document):
    limit = 60
    for process in document.processes:
        for nid in sorted(process.nodes):
            element = process.element_of(nid)
            name = (element.get("name") or "") if element is not None else ""
            if len(name) > limit:
                yield _finding("name-too-long", process,
                               f"the name of '{nid}' is {len(name)} characters long -- over ~{limit} "
                               f"it stops fitting the shape and gets clipped in exports",
                               element=nid)


@register("parallel-split-without-join", "warn")
def _parallel_split_without_join(document):
    for process in document.processes:
        for nid, node in process.nodes.items():
            if node["tag"] != "parallelGateway" or len(node["out_edges"]) < 2:
                continue
            seen = set()
            stack = [target for _flow_id, target in node["out_edges"]]
            found_join = False
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                other = process.nodes.get(current)
                if other is None:
                    continue
                if other["tag"] == "parallelGateway" and len(other["in_edges"]) >= 2:
                    found_join = True
                    break
                stack.extend(target for _flow_id, target in other["out_edges"])
                stack.extend(process.attached_boundary.get(current, []))
            if not found_join:
                yield _finding(
                    "parallel-split-without-join", process,
                    f"parallelGateway '{nid}' splits into {len(node['out_edges'])} branches "
                    f"with no parallel join reachable downstream -- confirm independent "
                    f"parallel outcomes are intentional",
                    element=nid,
                )
