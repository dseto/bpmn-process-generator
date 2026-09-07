# BPMN 2.0 XML structure reference

Read this before hand-writing any BPMN XML. It covers the skeleton every file needs, ID conventions, the DI (diagram interchange) rules that make bpmn-js actually render something, and four worked examples to copy patterns from.

---

## 1. Root skeleton and namespaces

Every file starts with exactly this root element and namespace set (copy verbatim — a wrong URI is the #1 cause of tools rejecting an otherwise-valid file):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <!-- flow elements go here -->
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <!-- BPMNShape / BPMNEdge go here -->
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
```

`isExecutable="false"` is correct for diagrams meant to be read/edited, not run on an engine. Set `true` only if the user explicitly wants this deployed to Camunda/Flowable and has given enough detail (task assignments, service task implementations) to make execution meaningful.

## 2. Start from a complete example

See `references/example-complete.bpmn` for a full, valid, ready-to-copy file — a start event, a task, an exclusive gateway with a conditioned branch, two distinct task-then-end-event paths, and a complete DI section with real coordinates. Start here and adapt it to the new process rather than assembling a document purely from the rules below; copying a known-good file and mutating it is far less error-prone than building one from scratch.

## 3. Element cheatsheet

| Concept | Element | Notes |
|---|---|---|
| Start | `<bpmn:startEvent id="...">` | Add `<bpmn:messageEventDefinition/>` etc. inside if the trigger is specific |
| Human step | `<bpmn:userTask id="...">` | |
| Automated step | `<bpmn:serviceTask id="...">` | |
| Generic/unspecified step | `<bpmn:task id="...">` | Only when the description genuinely doesn't say who/what performs it |
| Send/receive | `<bpmn:sendTask>` / `<bpmn:receiveTask>` | |
| Either/or branch | `<bpmn:exclusiveGateway id="...">` | XOR — exactly one outgoing path taken |
| Both-at-once branch | `<bpmn:parallelGateway id="...">` | AND — all outgoing paths taken |
| One-or-more branch | `<bpmn:inclusiveGateway id="...">` | OR — rare, only if description implies it |
| End | `<bpmn:endEvent id="...">` | Multiple allowed per process |
| Connector | `<bpmn:sequenceFlow id="..." sourceRef="..." targetRef="...">` | On a gateway's outgoing flow, add `<bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">...</bpmn:conditionExpression>` to name the branch condition |
| Actor grouping | `<bpmn:laneSet><bpmn:lane id="..." name="...">...<bpmn:flowNodeRef>NodeId</bpmn:flowNodeRef>...</bpmn:lane></bpmn:laneSet>` | Every flow node id must be listed under exactly one lane |

ID convention: `<ElementType>_<ShortPascalCaseDescription>`, e.g. `Task_ReviewApplication`, `Gateway_ApprovedOrRejected`, `Flow_ApprovedToShip`, `End_OrderShipped`. Readable ids make the lint script's error messages (and later human edits) far easier to follow than `Task_1`, `Task_2`.

## 4. DI / layout rules

Every flow node needs a `BPMNShape`, every sequence flow needs a `BPMNEdge`, inside `BPMNPlane`:

```xml
<bpmndi:BPMNShape id="Task_ReviewApplication_di" bpmnElement="Task_ReviewApplication">
  <omgdc:Bounds x="240" y="80" width="100" height="80" />
</bpmndi:BPMNShape>

<bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
  <omgdi:waypoint x="152" y="120" />
  <omgdi:waypoint x="240" y="120" />
</bpmndi:BPMNEdge>
```

Standard sizes: events (start/end) are 36x36, tasks are 100x80, gateways are 50x50. Lay the main flow along `y=80` (task top) / `y=98` (event vertical-center-equivalent), advance `x` by ~150 per element. When a gateway branches, offset one branch's row by ±120 in `y` and route its waypoints accordingly. Use the `layout` command in `scripts/bpmn_tool.py` to compute this automatically rather than hand-deriving coordinates beyond a 3-4 node example.

## 5. Worked example: linear process

"Customer submits a request, support reviews it, support responds."

```xml
<bpmn:process id="Process_Support" isExecutable="false">
  <bpmn:startEvent id="Start_RequestSubmitted" name="Request submitted">
    <bpmn:outgoing>Flow_1</bpmn:outgoing>
  </bpmn:startEvent>
  <bpmn:userTask id="Task_ReviewRequest" name="Review request">
    <bpmn:incoming>Flow_1</bpmn:incoming>
    <bpmn:outgoing>Flow_2</bpmn:outgoing>
  </bpmn:userTask>
  <bpmn:userTask id="Task_RespondToCustomer" name="Respond to customer">
    <bpmn:incoming>Flow_2</bpmn:incoming>
    <bpmn:outgoing>Flow_3</bpmn:outgoing>
  </bpmn:userTask>
  <bpmn:endEvent id="End_RequestClosed" name="Request closed">
    <bpmn:incoming>Flow_3</bpmn:incoming>
  </bpmn:endEvent>
  <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_RequestSubmitted" targetRef="Task_ReviewRequest" />
  <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_ReviewRequest" targetRef="Task_RespondToCustomer" />
  <bpmn:sequenceFlow id="Flow_3" sourceRef="Task_RespondToCustomer" targetRef="End_RequestClosed" />
</bpmn:process>
```

Note every flow node lists its own `incoming`/`outgoing` flow ids — this is conventional (every mainstream BPMN tool, including bpmn.io, emits it) and worth doing for readability, even though the XSD itself doesn't strictly require it.

## 6. Worked example: exclusive branch (if/else)

"...support decides: if resolvable, respond and close; if not, escalate to engineering."

Add after `Task_ReviewRequest`, replacing the single `Flow_2`:

```xml
<bpmn:exclusiveGateway id="Gateway_Resolvable" name="Resolvable?">
  <bpmn:incoming>Flow_2</bpmn:incoming>
  <bpmn:outgoing>Flow_Yes</bpmn:outgoing>
  <bpmn:outgoing>Flow_No</bpmn:outgoing>
</bpmn:exclusiveGateway>
...
<bpmn:sequenceFlow id="Flow_Yes" name="Yes" sourceRef="Gateway_Resolvable" targetRef="Task_RespondToCustomer">
  <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">resolvable == true</bpmn:conditionExpression>
</bpmn:sequenceFlow>
<bpmn:sequenceFlow id="Flow_No" name="No" sourceRef="Gateway_Resolvable" targetRef="Task_EscalateToEngineering">
  <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">resolvable == false</bpmn:conditionExpression>
</bpmn:sequenceFlow>
```

Both branches must eventually reach an end event — either independently, or by reconverging (they don't have to reconverge for exclusive gateways; each can go straight to its own end event).

## 7. Worked example: parallel split/join

"...once approved, notify the customer AND update inventory at the same time; once both are done, the order ships."

```xml
<bpmn:parallelGateway id="Gateway_SplitAfterApproval">
  <bpmn:incoming>Flow_Approved</bpmn:incoming>
  <bpmn:outgoing>Flow_ToNotify</bpmn:outgoing>
  <bpmn:outgoing>Flow_ToInventory</bpmn:outgoing>
</bpmn:parallelGateway>
<bpmn:serviceTask id="Task_NotifyCustomer" name="Notify customer">
  <bpmn:incoming>Flow_ToNotify</bpmn:incoming>
  <bpmn:outgoing>Flow_NotifyDone</bpmn:outgoing>
</bpmn:serviceTask>
<bpmn:serviceTask id="Task_UpdateInventory" name="Update inventory">
  <bpmn:incoming>Flow_ToInventory</bpmn:incoming>
  <bpmn:outgoing>Flow_InventoryDone</bpmn:outgoing>
</bpmn:serviceTask>
<bpmn:parallelGateway id="Gateway_JoinBeforeShip">
  <bpmn:incoming>Flow_NotifyDone</bpmn:incoming>
  <bpmn:incoming>Flow_InventoryDone</bpmn:incoming>
  <bpmn:outgoing>Flow_ToShip</bpmn:outgoing>
</bpmn:parallelGateway>
```

A parallel split (`Gateway_SplitAfterApproval`) must be matched by a parallel join (`Gateway_JoinBeforeShip`) with one incoming flow per branch — this is exactly what the control-flow lint checks for.

## 8. Worked example: multi-lane (multi-actor)

"The customer submits an order; the warehouse picks it; the courier delivers it."

```xml
<bpmn:process id="Process_Order" isExecutable="false">
  <bpmn:laneSet id="LaneSet_1">
    <bpmn:lane id="Lane_Customer" name="Customer">
      <bpmn:flowNodeRef>Start_OrderSubmitted</bpmn:flowNodeRef>
    </bpmn:lane>
    <bpmn:lane id="Lane_Warehouse" name="Warehouse">
      <bpmn:flowNodeRef>Task_PickOrder</bpmn:flowNodeRef>
    </bpmn:lane>
    <bpmn:lane id="Lane_Courier" name="Courier">
      <bpmn:flowNodeRef>Task_DeliverOrder</bpmn:flowNodeRef>
      <bpmn:flowNodeRef>End_OrderDelivered</bpmn:flowNodeRef>
    </bpmn:lane>
  </bpmn:laneSet>
  <!-- flow node + sequenceFlow definitions as usual -->
</bpmn:process>
```

Lanes need their own `BPMNShape` in the DI section too (a wide horizontal or vertical band with `isHorizontal="true"`), sized to contain all the shapes of the nodes listed in `flowNodeRef`. The `layout` command in `scripts/bpmn_tool.py` handles lane banding automatically when it detects a `laneSet` in the input structure — don't hand-place lane bounds.
