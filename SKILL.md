---
name: bpmn-process-generator
description: Generates valid BPMN 2.0 process diagrams (.bpmn XML) from a natural-language description of a business process, and packages them with a standalone HTML editor that embeds the bpmn-js Modeler (via CDN) so the diagram opens ready-to-edit in any browser, no server or install required. Use this skill whenever the user describes a business process, workflow, or procedure and wants it turned into a diagram, a BPMN file, a flowchart they can edit, or asks to "map", "model", or "diagram" a process — even if they don't say "BPMN" explicitly. Also use when the user has an existing .bpmn file and wants it validated, fixed, or wrapped in an openable editor. For a quick, informal flowchart with no real BPMN semantics (no gateways, swimlanes, or formal process semantics involved), a simpler diagram is usually a better answer than this skill.
---

# BPMN Process Generator

## What this skill produces

The skill produces:

1. `<process-name>.bpmn` — valid BPMN 2.0 XML, validated (well-formedness + control-flow lint), with layout (`BPMNDiagram`/`BPMNPlane` DI) computed so it renders sensibly on first open.
2. Direct access through the **centralized editor** `editor.html` (located in the skill root directory), which opens any `.bpmn` file with drag-and-drop, a file picker, preset examples, and direct disk saving (`Ctrl+S`) via File System Access API.
3. *(Optional)* `<process-name>.html` — a standalone single self-contained HTML file (via `python scripts/build_editor.py <file>.bpmn`) for portability when sharing a single file with external users who don't have access to the skill folder.

`<process-name>` must be a filesystem-safe slug (lowercase, hyphens or underscores in place of spaces, no special characters).

## Workflow

Follow these steps in order. Don't skip validation or lint even for "simple" processes — a diagram that opens but deadlocks or has unreachable steps is worse than an error, because it looks done.

If the user supplies an existing `.bpmn` file instead of a natural-language description, skip step 1 (extraction) and step 2 (XML generation) — go straight to step 3 to validate and fix what they gave you, then step 4 (wrap it in the HTML editor) and step 5 (report).

### 1. Extract process structure from the description

Read the user's description and identify, in order:

- **Trigger / start**: what kicks the process off (message arrival, timer, manual start, condition). Maps to a `startEvent`, typed if the trigger is specific (`messageEventDefinition`, `timerEventDefinition`, etc.) or plain if it's just "someone begins the process."
- **Steps**: discrete pieces of work. Map each to a `task` (or a typed subtype — `userTask` for human steps, `serviceTask` for automated/system steps, `sendTask`/`receiveTask` for messaging — pick the type that matches what the description actually says the step *is*, don't default everything to plain `task`).
- **Decisions / branches**: anywhere the process forks based on a condition ("if approved... otherwise..."). Maps to an `exclusiveGateway` (XOR) for either/or branches, `parallelGateway` (AND) for "do both at the same time," `inclusiveGateway` (OR) only if the description genuinely implies "one or more of these paths, not necessarily all."
- **Actors / swimlanes**: if the description names more than one role or department doing distinct parts (e.g. "the customer submits... then the finance team reviews..."), use `laneSet`/`lane` inside the process to separate them. Don't force lanes onto a single-actor process — it adds visual noise without adding information.
- **End(s)**: every path through the process must terminate at an `endEvent`. A process can have multiple end events (e.g. "approved" vs "rejected" outcomes) — that's normal and often clearer than merging paths artificially.

If the description is ambiguous about branch conditions, actor boundaries, or what happens on a failure path, ask the user rather than guessing — a wrong gateway condition silently produces a diagram that looks right but models the wrong process.

### 2. Generate the BPMN 2.0 XML

Read `references/bpmn-xml-structure.md` for the element reference, ID conventions, and worked examples (linear process, branching process, multi-lane process, parallel split/join) before writing XML by hand. Key non-negotiables:

- Every element needs a unique `id` (stable, readable — e.g. `Task_ReviewApplication`, not `Task_1`). Sequence flows reference these ids via `sourceRef`/`targetRef`.
- The `<bpmndi:BPMNDiagram>` section is not optional decoration — without it, bpmn-js has nothing to lay out and renders an empty canvas. Compute simple auto-layout: lay the main flow left-to-right at a fixed row, offset gateway branches vertically (above/below the main row) by a fixed spacing, and give every node explicit `x`/`y`/`width`/`height` in `BPMNShape`, plus `waypoint` points for every `BPMNEdge`. Run the `layout` operation in `scripts/bpmn_tool.py` to compute this — don't hand-place coordinates for anything beyond a trivial 3-node process. (The script is plain Python 3 standard library — no extra packages to install.)
- Use the standard BPMN 2.0 namespaces and schema location exactly as in the reference examples — a wrong namespace URI is the single most common cause of "valid-looking XML that Camunda rejects."

### 3. Validate — do not skip this even if generation "looked right"

Run the `validate` operation in `scripts/bpmn_tool.py <file>.bpmn`. It performs two checks, in order, and stops at the first failure:

1. **Well-formedness**: valid XML syntax. Catches unclosed tags, bad escaping.
2. **Control-flow lint**: BPMN's schema doesn't and can't enforce that the *graph* (or the DI) makes sense. The lint checks, per process:
   - **DI completeness**: every flow node has a corresponding `BPMNShape`, and every sequence flow has a `BPMNEdge` with real (non-degenerate) waypoints. A file that's structurally plausible but has no DI renders as a blank canvas in bpmn-js — this is arguably the single most important thing to catch, since it's the failure mode that looks fine right up until the user opens the HTML.
   - **Duplicate element ids**: bpmn-js hard-fails import the moment it sees a repeated id, so this must be caught before handoff, not discovered by the user.
   - Exactly the start/end events the process needs exist and are reachable — no process with zero start events, no dangling reachable path that never hits an end event.
   - No unreachable nodes (something with no incoming sequence flow that isn't a start event).
   - No dead ends (something with no outgoing sequence flow that isn't an end event).
   - Every gateway that splits (2+ outgoing flows) either has a matching converging gateway of a compatible type downstream, or its branches each terminate independently at their own end event — flag (don't necessarily block) a parallel split with no join, since that's sometimes intentional but often a mistake.
   - No orphaned `sequenceFlow` elements referencing a `sourceRef`/`targetRef` id that doesn't exist in the process.

There is no separate XSD schema-validation stage — bpmn-js's own import in the HTML editor (step 4) is the real acceptance test for structural validity, and it rejects a structurally invalid document the moment the user opens the file. If validation or lint fails, fix the XML and re-run — don't hand the user a file that fails its own checks with a note saying "there might be issues." Iterate until clean, or until you've identified a genuine ambiguity in the source description that only the user can resolve (in which case, ask).

### 4. Review and edit in the central editor (or build a standalone HTML)
 
- **Centralized Editor**: Open `editor.html` in the root of the skill. Click "📂 Abrir .bpmn", drag and drop the `.bpmn` file into the canvas, or select it from the preset dropdown. Edits can be saved directly back to disk with `Ctrl+S` or "💾 Salvar".
- **Optional Standalone HTML**: If a portable single-file deliverable is required, run `python scripts/build_editor.py <process-name>.bpmn -o <process-name>.html -s <process-name>`.

### 5. Report to the user
 
State plainly: what the process looks like (short bullet walkthrough of the flow you modeled), which validation/lint checks passed, and any ambiguity you resolved by assumption (name the assumption so they can correct it). Point them to `editor.html` and the generated `.bpmn` file.
