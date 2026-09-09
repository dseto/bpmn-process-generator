# Process spec (JSON) — o formato de entrada do gerador

Este é o formato que se escreve para gerar um diagrama. **Não escreva XML BPMN à mão**: descreva o processo aqui e deixe `scripts/bpmn_build.py` emitir o `.bpmn`. O gerador garante, por construção, o que um XML escrito à mão erra — ids legíveis e únicos, `<bpmn:incoming>`/`<bpmn:outgoing>` sempre coerentes com os `sequenceFlow`, e referências resolvidas.

Exemplo canônico pronto para copiar: [`references/example-spec.json`](example-spec.json).

---

## 1. Esqueleto

```json
{
  "id": "Process_AtendimentoSuporte",
  "name": "Atendimento de suporte",
  "executable": false,
  "nodes": [
    { "id": "chamado_aberto", "type": "start",    "name": "Chamado aberto" },
    { "id": "triar",          "type": "userTask", "name": "Triar chamado" },
    { "id": "encerrado",      "type": "end",      "name": "Chamado encerrado" }
  ],
  "flows": [
    { "from": "chamado_aberto", "to": "triar" },
    { "from": "triar",          "to": "encerrado" }
  ]
}
```

| Campo raiz | Obrigatório | Significado |
|---|---|---|
| `id` | não | Id do `<bpmn:process>`. Sem o prefixo `Process_`, ele é acrescentado. Ausente, deriva de `name`. |
| `name` | não | Nome do processo (vai para o atributo `name`). |
| `executable` | não | `true` só quando o diagrama for para execução em engine (Camunda/Flowable). Default `false`. |
| `nodes` | **sim** | Lista de nós do fluxo, na ordem de leitura do processo. |
| `flows` | **sim** | Conexões entre nós. |

## 2. Nós (`nodes[]`)

| Campo | Obrigatório | Significado |
|---|---|---|
| `id` | **sim** | Identificador **interno do spec** (curto, minúsculo, `snake_case`). É só a chave usada em `flows`; não aparece no XML. |
| `type` | **sim** | Um dos aliases da tabela abaixo. |
| `name` | recomendado | Rótulo que aparece no diagrama. Acentos são preservados no rótulo e removidos do id gerado. |
| `event` | não | Tipo do gatilho, só em eventos (`start`, `end`, `catch`, `throw`, `boundary`) — ver §2.2. |
| `attachedTo` | **sim** para `boundary` | `id` (do spec) da atividade à qual o evento de borda está anexado. |
| `interrupting` | não | Só em `boundary`. `false` gera `cancelActivity="false"` (o evento dispara sem cancelar a atividade). Default: interrompe. |
| `lane` | não | `id` (do spec) da raia que executa o nó — ver §5. |

### Aliases de `type`

| Alias curto | Elemento BPMN | Quando usar |
|---|---|---|
| `start` | `startEvent` | Gatilho do processo |
| `end` | `endEvent` | Encerramento de um caminho |
| `task` | `task` | Passo cujo executor a descrição não revela |
| `userTask` | `userTask` | Passo executado por pessoa |
| `serviceTask` | `serviceTask` | Passo executado por sistema |
| `sendTask` | `sendTask` | Envio de mensagem |
| `receiveTask` | `receiveTask` | Espera por mensagem |
| `manualTask` | `manualTask` | Trabalho manual fora de sistema |
| `scriptTask` | `scriptTask` | Rotina/script automatizado |
| `businessRuleTask` | `businessRuleTask` | Aplicação de regra de negócio/decisão tabelada |
| `xor` | `exclusiveGateway` | Decisão exclusiva (um caminho só) |
| `and` | `parallelGateway` | Divisão/junção paralela (todos os caminhos) |
| `or` | `inclusiveGateway` | Um ou mais caminhos (usar só quando explícito) |
| `eventGateway` | `eventBasedGateway` | Decisão por qual evento chegar primeiro |
| `catch` | `intermediateCatchEvent` | Espera por evento no meio do fluxo |
| `throw` | `intermediateThrowEvent` | Disparo de evento no meio do fluxo |
| `boundary` | `boundaryEvent` | Evento anexado a uma atividade (prazo, erro) |
| `subProcess` | `subProcess` | Subprocesso |
| `callActivity` | `callActivity` | Chamada de processo externo |

Os nomes canônicos do BPMN também são aceitos como `type`, o que faz um spec extraído de um `.bpmn` existente voltar a gerar o mesmo arquivo sem tradução: `startEvent`, `endEvent`, `exclusiveGateway`, `parallelGateway`, `inclusiveGateway`, `eventBasedGateway`, `intermediateCatchEvent`, `intermediateThrowEvent`, `boundaryEvent`.

### 2.2. Tipos de evento (`event`)

Vira o `<bpmn:*EventDefinition>` correspondente dentro do evento. Só é aceito em `start`, `end`, `catch`, `throw` e `boundary` — pôr `event` numa tarefa é erro de spec.

| `event` | Elemento gerado | Uso típico |
|---|---|---|
| `message` | `messageEventDefinition` | Chegada/envio de mensagem, pedido, e-mail |
| `timer` | `timerEventDefinition` | Prazo, agendamento, espera |
| `error` | `errorEventDefinition` | Falha de negócio tratada |
| `signal` | `signalEventDefinition` | Broadcast para outros processos |
| `escalation` | `escalationEventDefinition` | Escalonamento hierárquico |
| `conditional` | `conditionalEventDefinition` | Disparo por condição de dado |
| `compensate` | `compensateEventDefinition` | Compensação/estorno |
| `link` | `linkEventDefinition` | Costura de trechos do mesmo diagrama |
| `terminate` | `terminateEventDefinition` | Encerra o processo inteiro, não só o caminho |

**Eventos de borda** (`boundary`) anexam um evento a uma atividade — o caso mais comum é prazo:

```json
{ "id": "prazo_triagem", "type": "boundary", "name": "Prazo de 4h",
  "event": "timer", "attachedTo": "triar" }
```

O `attachedTo` precisa apontar para uma **atividade** (tarefa, subprocesso ou `callActivity`); anexar a evento ou gateway é erro de spec. Eventos de borda não têm fluxo de entrada — só de saída, para o caminho de exceção.

## 3. Fluxos (`flows[]`)

| Campo | Obrigatório | Significado |
|---|---|---|
| `from` | **sim** | `id` (do spec) do nó de origem |
| `to` | **sim** | `id` (do spec) do nó de destino |
| `label` | não | Rótulo da conexão no diagrama (ex.: `"Sim"`, `"Não"`, `"Acima de R$ 5.000"`) |
| `condition` | não | Critério da ramificação; vira `conditionExpression` formal. Use nas saídas de `xor`/`or`. |
| `default` | não | `true` marca este ramo como o default do gateway de origem (o caminho quando nenhuma condição bateu). |

Os `sequenceFlow` recebem ids sequenciais (`Flow_1`, `Flow_2`, ...) na ordem em que aparecem.

Regras que o gerador impõe: `default` só vale em fluxo que **sai de um gateway**, e um fluxo default **não pode ter `condition`** — ele é justamente o ramo do "nenhuma condição bateu".

```json
{ "from": "resolvivel", "to": "responder", "label": "Sim", "condition": "resolvivelNoPrimeiroNivel == true" },
{ "from": "resolvivel", "to": "escalar",   "label": "Não", "default": true }
```

## 4. Ids gerados

O id do spec é interno; o id que vai para o XML é derivado do `name` (ou do id do spec, quando não há nome), sempre em PascalCase sem acentos, com prefixo pelo tipo:

| Tipo | Prefixo | Exemplo |
|---|---|---|
| `startEvent` | `Start_` | `Start_ChamadoAberto` |
| `endEvent` | `End_` | `End_ChamadoEncerrado` |
| tarefas (todas) | `Task_` | `Task_TriarChamado` |
| gateways (todos) | `Gateway_` | `Gateway_Resolvivel` |
| eventos intermediários e de borda | `Event_` | `Event_Prazo48h` |
| `subProcess` | `SubProcess_` | `SubProcess_Cobranca` |
| `callActivity` | `Activity_` | `Activity_AnaliseCredito` |

Dois nós com o mesmo nome não colidem: o segundo recebe sufixo numérico (`Task_NotificarCliente_2`). A geração é determinística — o mesmo spec produz sempre o mesmo XML, byte a byte.

## 5. Raias (`lanes[]`)

Quando o processo tem mais de um ator (setor, papel, sistema), declare as raias e aponte cada nó para a sua:

```json
"lanes": [
  { "id": "suporte",    "name": "Suporte N1" },
  { "id": "engenharia", "name": "Engenharia" }
]
```

| Campo | Obrigatório | Significado |
|---|---|---|
| `id` | **sim** (ou `name`) | Chave usada no campo `lane` dos nós |
| `name` | recomendado | Rótulo da raia no diagrama |

A ordem das raias no spec é a ordem das faixas no diagrama, de cima para baixo. **Todo nó entra em exatamente uma raia**: um nó sem `lane` cai na primeira raia declarada, de modo que a cobertura de `flowNodeRef` fica sempre completa (nó sem raia é o que faz o bpmn-js desenhar um elemento solto fora do pool). Apontar para uma raia que não existe é erro de spec. Sem `lanes`, nenhum `laneSet` é emitido.

As posições das faixas são calculadas pelo `bpmn_tool.py layout` — nunca escreva bounds de raia à mão.

## 6. Erros de spec

O gerador **falha alto** (`SpecError`) em vez de emitir um diagrama quebrado quando:

- falta `id` ou `type` num nó, o `type` é desconhecido, ou há `id` de nó repetido;
- um fluxo não tem `from`/`to`, ou aponta para um nó que não existe;
- o `event` é desconhecido, ou está num elemento que não é evento;
- um `boundary` está sem `attachedTo`, anexado a nó inexistente, ou anexado a algo que não é atividade;
- um fluxo `default` não sai de gateway, ou acumula `default` e `condition`;
- um nó aponta para uma raia que não existe.

## 7. Depois de gerar

O spec produz o `.bpmn` **sem** a seção de layout (DI). Quem calcula posições e waypoints é o `bpmn_tool.py` — ver [`bpmn-xml-structure.md`](bpmn-xml-structure.md) para a estrutura do XML gerado e para depurar um arquivo existente.
