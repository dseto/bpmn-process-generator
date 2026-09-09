---
name: bpmn-process-generator
description: Generates valid BPMN 2.0 process diagrams (.bpmn XML) from natural-language business process descriptions via a JSON process spec, computes visual layout (Diagram Interchange DI), validates graph integrity and control flow with severity-ranked rules (JSON output and automatic repair of mechanical problems), automatically copies the interactive web editor (editor.html) to the requesting project directory, and provides diagram typography formatting (font size, bold, italic), direct disk saving (Ctrl+S), drag-and-drop, and orthogonal routing. Use this skill whenever the user describes a business process, workflow, or procedure to map, diagram, or model, or has an existing .bpmn file to validate, repair, layout, or edit.
---

# BPMN Process Generator

## 1. O que esta Skill produz

O objetivo primário da skill é produzir especificações e diagramas BPMN 2.0 válidos, visualizáveis e editáveis diretamente no ambiente do projeto solicitante:

1. **`<process-name>.bpmn` (Entregável Primário)**:
   * Arquivo XML em conformidade estrita com o padrão BPMN 2.0 da OMG.
   * Gerado a partir de um **spec JSON** (`scripts/bpmn_build.py`), nunca escrito à mão: ids legíveis e únicos, `<bpmn:incoming>`/`<bpmn:outgoing>` sempre coerentes com os `sequenceFlow`, condições e fluxo default nos gateways, raias com cobertura completa.
   * Diagram Interchange (DI) completo calculado via algoritmo topológico (`BPMNDiagram`, `BPMNPlane`, `BPMNShape`, `BPMNEdge` com waypoints).
   * Validado por um linter de regras com severidade (erro / aviso / informação), com saída legível ou em JSON.
2. **`editor.html` (Editor Web Distribuído no Projeto)**:
   * Aplicação web autossuficiente baseada no `bpmn-js@17.0.0` (Modeler build).
   * **Cópia Automática para o Projeto**: ao gerar o diagrama, o `editor.html` é copiado para o diretório do projeto solicitante e configurado para abrir o diagrama gerado por padrão.
   * **Diretório Padrão de Trabalho**: o diretório onde o `editor.html` foi copiado passa a ser o diretório padrão para abertura, visualização e salvamento dos diagramas do projeto.
   * **Formatação Tipográfica por Elemento**: tamanho da fonte (`9px` a `20px`) e estilo (**Negrito** `Ctrl+B`, *Itálico* `Ctrl+I`) nos elementos selecionados, refletindo no canvas e nas exportações SVG e PNG.
   * **Salvamento Direto no Disco**: em navegadores Chromium (Chrome, Edge, Opera), usa a *File System Access API* para gravar direto no arquivo aberto com `Ctrl+S`.

> [!IMPORTANT]
> **Regras Mandatórias de Entrega:**
> - **NÃO crie arquivo com o nome do diagrama** (ex: proibido criar `<process-name>.html`).
> - **NÃO aponte para o arquivo original na raiz da skill** (proibido fornecer links para `bpmn-process-generator/editor.html`).
> - **SEMPRE aponte para o `editor.html` local copiado no projeto solicitante** (`file:///<caminho-do-projeto>/editor.html?file=<processo>.bpmn`).

---

## 2. Estrutura do Repositório

```
bpmn-process-generator/
├── .gitignore                      # Regras para versionar apenas o essencial
├── AGENTS.md                       # Diretrizes de governança para agentes
├── editor.html                     # Editor central interativo com gravação direta
├── SKILL.md                        # Esta documentação de referência e workflow
├── assets/
│   └── bpmn-editor-template.html   # Template base para exportações HTML avulsas
├── references/
│   ├── process-spec.md             # Contrato do spec JSON (formato de entrada)
│   ├── example-spec.json           # Spec canônico de exemplo
│   ├── bpmn-xml-structure.md       # Dicionário de tags, namespaces e exemplos XML
│   ├── example-complete.bpmn       # Exemplo canônico de referência com layout
│   └── example-broken.bpmn         # Exemplo com erros intencionais para teste de lint
└── scripts/
    ├── bpmn_build.py               # Spec JSON -> BPMN (build + layout + validate)
    ├── bpmn_tool.py                # CLI: layout, validate, fix, extract, copy-editor
    ├── lint_rules.py               # Regras de validação com severidade
    ├── build_editor.py             # Empacota .bpmn em HTML avulso
    └── generate_editor_html.py     # Gerador/atualizador do editor.html central
```

---

## 3. Workflow Operacional

Siga rigorosamente as etapas abaixo. Nunca entregue um diagrama sem validar.

### Passo 0: Esclarecer o que falta (antes de modelar)

Um diagrama fiel depende de informação que a descrição quase sempre omite. Antes de escrever o spec, percorra a lista abaixo e **pergunte apenas o que estiver ausente e for estrutural**:

| O que checar | Por que importa |
|---|---|
| **Atores** — quem executa cada etapa (setor, papel, sistema) | Define as raias; sem isso o diagrama vira uma fila sem responsáveis |
| **Gatilho** — o que inicia o processo (pedido, prazo, mensagem, decisão) | Define o tipo do evento inicial |
| **Exceções** — o que acontece quando dá errado, é rejeitado ou falta informação | Sem isso só existe o caminho feliz |
| **Retrabalho** — algum passo volta para trás? | Define os laços de correção |
| **Prazos** — há SLA, espera ou timeout? | Vira evento de borda (`timer`) |
| **Critério de cada decisão** — o que decide cada saída de gateway | Vira `condition` e fluxo default |
| **Fins** — onde e como o processo termina (quantos desfechos) | Define os eventos de fim |

Regras do Passo 0: no máximo **3 perguntas** por vez; se o usuário não responder, modele o caminho feliz e **declare explicitamente as lacunas** no relato final, em vez de inventar etapas.

### Passo 1: Escrever o spec do processo (JSON)

Traduza a descrição para o spec documentado em `references/process-spec.md`, tomando `references/example-spec.json` como modelo:

* **Nós** (`nodes`): `start` / `end` (com `event` quando o gatilho for específico: `message`, `timer`, `error`, `signal`, `terminate`), `userTask` (pessoa), `serviceTask` (sistema), `task` (executor não informado), `xor` (escolha exclusiva), `and` (paralelo), `or` (um ou mais), `boundary` (prazo ou erro anexado a uma atividade).
* **Fluxos** (`flows`): `from`/`to`, com `label` e `condition` nas saídas de decisão e `default: true` no ramo "nenhuma condição bateu".
* **Raias** (`lanes`): uma por ator, na ordem de cima para baixo.

**Convenções de nomenclatura** (o que faz o diagrama ser lido sem legenda):

| Elemento | Convenção | Exemplo |
|---|---|---|
| Tarefa | verbo no **infinitivo** + objeto | "Conferir nota fiscal" |
| Gateway | pergunta terminada em "?" | "Aprovado?" |
| Evento | particípio (fato consumado) | "Despesa paga" |
| Fluxo de decisão | a resposta, curta | "Sim", "Acima de R$ 5.000" |

Idioma do diagrama = idioma do usuário. Nomes com mais de ~60 caracteres são cortados na caixa: encurte.

> Escrever XML BPMN à mão não é o caminho desta skill — é a origem dos erros que o gerador elimina. `references/bpmn-xml-structure.md` permanece como material de consulta e depuração de arquivos existentes.

### Passo 2: Gerar o diagrama a partir do spec

```powershell
python scripts/bpmn_build.py <caminho>/<processo>-spec.json -o <caminho-do-projeto>/<processo>.bpmn
```

Um único comando faz tudo: constrói o XML, calcula o layout (DI), roda o linter e copia o `editor.html` já apontando para o diagrama gerado. Sai com código diferente de zero se o linter reprovar.

### Passo 3: Validar e reparar (obrigatório)

```powershell
# Relatório legível
python scripts/bpmn_tool.py validate <caminho>/<processo>.bpmn

# Relatório em JSON, para decidir o reparo programaticamente
python scripts/bpmn_tool.py validate <caminho>/<processo>.bpmn --json

# Padrão de qualidade da skill: avisos de modelagem também reprovam
python scripts/bpmn_tool.py validate <caminho>/<processo>.bpmn --json --strict

# Reparo automático do que é mecânico (com prévia)
python scripts/bpmn_tool.py fix <caminho>/<processo>.bpmn --dry-run
python scripts/bpmn_tool.py fix <caminho>/<processo>.bpmn
```

**Severidades:**

* **erro** — reprova a entrega: XML malformado, id duplicado, DI faltando, nó inalcançável, beco sem saída, `incoming`/`outgoing` divergindo dos fluxos, fluxo apontando para nó inexistente, evento de borda sem atividade, ciclo que nunca alcança um fim, nó em duas raias.
* **aviso** — qualidade de modelagem: divisão ou junção implícita (sem gateway), decisão sem critério escrito, gateway que divide e une ao mesmo tempo, divisão paralela sem junção, elemento sem nome, fluxo duplicado, laço sobre si mesmo, nó fora das raias, caixas sobrepostas.
* **informação** — estilo: gateway inútil, id fora da convenção, nome longo demais.

**Ciclo de auto-reparo**: se houver `severity: error`, rode `fix` e valide de novo. No máximo **2 ciclos** — o `fix` corrige apenas a contabilidade do arquivo (referências de fluxo, fluxos duplicados, ids duplicados, DI); ele **nunca** inventa tarefa, condição ou nome. O que sobrar é decisão de modelagem: corrija o spec e gere de novo, ou pergunte ao usuário.

### Passo 3b: Alterar um diagrama que já existe

Para editar por descrição um `.bpmn` existente (inclusive um que foi ajustado à mão no editor), extraia o spec, altere o spec e regere:

```powershell
python scripts/bpmn_tool.py extract <caminho>/<processo>.bpmn -o <caminho>/<processo>-spec.json
python scripts/bpmn_build.py <caminho>/<processo>-spec.json -o <caminho>/<processo>.bpmn
```

### Passo 4: Visualizar e Editar no `editor.html` Local

* O usuário abre o `editor.html` **local** copiado para a pasta do projeto (`file:///<caminho-do-projeto>/editor.html?file=<processo>.bpmn`).
* O diretório padrão para abertura e salvamento é o próprio diretório do projeto.
* Recursos de edição disponíveis:
  * **Painel de Propriedades** (botão **"🧾 Propriedades"**): edita nome, documentação e tipo do elemento (converte entre tarefa de pessoa/sistema e entre gateways) e, ao selecionar uma conexão, a **condição da decisão** e a marcação de **fluxo padrão**. Tudo entra no histórico — `Ctrl+Z` desfaz.
  * **Painel de Validação** (botão **"✅ Validar diagrama"**): checa as mesmas regras do linter (mesmos `rule` ids) e lista os achados; clicar num achado seleciona o elemento com defeito no canvas.
  * **Tipografia por elemento**: tamanho da fonte (`9px`–`20px`), **Negrito** (`Ctrl+B`) e *Itálico* (`Ctrl+I`) nos elementos selecionados, preservados em SVG e PNG.
  * **Redimensionamento de Tarefas**: alças de canto nas atividades.
  * **Roteamento 90°**: botão **"📐 Curva 90°"** para ortogonalizar conexões selecionadas ou todo o processo.
  * **Alinhar, Centralizar e Distribuir**: arruma a seleção (alinhar exige 2+ elementos; distribuir, 3+, porque reposiciona os do meio).
  * **Grade**: encaixe magnético na grade de 10 px.
  * **Paleta de Cores**, **Histórico** (`Ctrl+Z` / `Ctrl+Y`) e **Busca** (`Ctrl+F`).
  * **Exportação Gráfica**: SVG e PNG 2x com a tipografia intacta, e **🖨️ PDF** (abre a impressão do navegador com folha de estilo dedicada — escolha "Salvar como PDF").
* **Modo offline (opcional)**: por padrão o editor carrega o bpmn-js do CDN. Colocando os arquivos da biblioteca em `assets/vendor/` e rodando `python scripts/generate_editor_html.py`, tudo passa a ser embutido no `editor.html` e ele abre sem internet — instruções em `assets/vendor/README.md`. O editor gerado declara em qual modo foi construído (`<meta name="bpmn-editor-assets">`).
* **Atualização da cópia do projeto**: o editor entregue carrega versão; quando a skill evolui, uma cópia intacta é atualizada sozinha, e uma cópia com ajustes locais é preservada (o comando avisa como sobrescrever com `--force`).
* Ajustes manuais são gravados diretamente no disco com **`Ctrl+S`**.

### Passo 5: Relatar ao Usuário

Apresente um resumo executivo do fluxo modelado, os caminhos alternativos mapeados, o resultado das validações, **as lacunas que ficaram em aberto do Passo 0** e os links diretos para:
1. O arquivo `.bpmn` gerado: `[<processo>.bpmn](file:///<caminho-do-projeto>/<processo>.bpmn)`
2. O editor web copiado no próprio projeto: `[editor.html](file:///<caminho-do-projeto>/editor.html?file=<processo>.bpmn)`

> [!CAUTION]
> **Proibições Estritas**:
> - **NUNCA** gere arquivo HTML com o nome do diagrama (como `<processo>.html`).
> - **NUNCA** aponte para o `editor.html` na raiz da pasta da skill. O link fornecido ao usuário DEVE apontar para o `editor.html` copiado no projeto solicitante.

---

## 4. Referência dos Scripts Utilitários

Todos os scripts operam com a biblioteca padrão do Python 3 (sem necessidade de `pip install`):

| Script | Finalidade | Exemplo de Comando |
|---|---|---|
| `scripts/bpmn_build.py` | Spec JSON → BPMN: constrói, calcula layout, valida e distribui o editor. | `python scripts/bpmn_build.py proc-spec.json -o proc.bpmn` |
| `scripts/bpmn_tool.py` | Layout, validação (`--json`, `--strict`), reparo (`fix`) e extração inversa (`extract`). | `python scripts/bpmn_tool.py validate proc.bpmn --json --strict`<br>`python scripts/bpmn_tool.py fix proc.bpmn`<br>`python scripts/bpmn_tool.py extract proc.bpmn` |
| `scripts/lint_rules.py` | Regras de validação com severidade — uma regra por função, usada por `validate`. | — |
| `scripts/build_editor.py` | Empacota um `.bpmn` dentro do template HTML avulso com dupla codificação JSON segura. | `python scripts/build_editor.py proc.bpmn -o proc.html` |
| `scripts/generate_editor_html.py` | Regenera o `editor.html` central embutindo os presets mais recentes. | `python scripts/generate_editor_html.py` |
| `scripts/verify_tests.py` | Suíte CLI de validação dos processos BPMN de teste e integridade de DI/HTML. | `python scripts/verify_tests.py` |

---

## 5. Testes e Garantia de Qualidade

A suíte de testes pode ser executada via **pytest** a partir da raiz do repositório:

```powershell
pytest -v
```

A suíte cobre:
1. Geração a partir do spec: ids determinísticos, referências de fluxo coerentes, eventos tipados, eventos de borda, condições, fluxo default e raias.
2. Round-trip `extract` → `build` sem perda do processo.
3. Cada regra do linter isoladamente (caso positivo e negativo), com o exemplo canônico quebrado exercitando as regras de erro.
4. `validate --json/--strict` e o subcomando `fix`, inclusive o que ele deve se recusar a fazer.
5. Validação estrutural, integridade de DI e modo estrito dos 6 diagramas de exemplo (`tests/01-user-onboarding.bpmn` a `tests/06-bus-boarding-process.bpmn`).
6. Empacotamento HTML, dupla decodificação JSON caractere a caractere e contrato contra injeção de script tags.

---

## 6. Governança e Controle de Versão

O repositório adota política rígida de controle com Git através do `.gitignore`:
* O código-fonte da skill, os scripts utilitários, os exemplos canônicos e a suíte de testes (`tests/`) são versionados.
* Arquivos HTML gerados dinamicamente (`tests/*.html`, `test-output*.html`), caches Python (`__pycache__`, `.pytest_cache`), arquivos do harness (`.harness/scratch/`) e configurações locais (`.claude/`) são automaticamente ignorados.
