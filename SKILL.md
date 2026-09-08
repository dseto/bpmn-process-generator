---
name: bpmn-process-generator
description: Generates valid BPMN 2.0 process diagrams (.bpmn XML) from natural-language business process descriptions, computes visual layout (Diagram Interchange DI), validates graph integrity and control flow, automatically copies the interactive web editor (editor.html) to the requesting project directory, and provides diagram typography formatting (font size, bold, italic), direct disk saving (Ctrl+S), drag-and-drop, and orthogonal routing. Use this skill whenever the user describes a business process, workflow, or procedure to map, diagram, or model, or has an existing .bpmn file to validate, repair, layout, or edit.
---

# BPMN Process Generator

## 1. O que esta Skill produz

O objetivo primário da skill é produzir especificações e diagramas BPMN 2.0 válidos, visualizáveis e editáveis diretamente no ambiente do projeto solicitante:

1. **`<process-name>.bpmn` (Entregável Primário)**:
   * Arquivo XML em conformidade estrita com o padrão BPMN 2.0 da OMG.
   * Diagram Interchange (DI) completo calculado via algoritmo topológico (`BPMNDiagram`, `BPMNPlane`, `BPMNShape`, `BPMNEdge` com waypoints).
   * Validado contra erros sintáticos e linter de fluxo de controle (ausência de deadlocks, nós inalcançáveis, IDs duplicados e desbalanceamento de gateways).
2. **`editor.html` (Editor Web Distribuído no Projeto)**:
   * Aplicação web autossuficiente baseada no `bpmn-js@17.0.0` (Modeler build).
   * **Cópia Automática para o Projeto**: Ao gerar o diagrama, o arquivo `editor.html` é copiado para o diretório do projeto que solicitou o diagrama (se ainda não existir lá).
   * **Diretório Padrão de Trabalho**: O diretório onde o `editor.html` foi copiado passa a ser o diretório padrão para abertura, visualização e salvamento dos diagramas do projeto.
   * **Formatação Tipográfica por Elemento**: Permite alterar o tamanho da fonte (`9px` a `20px`) e o estilo (**Negrito** e *Itálico*, com atalhos `Ctrl+B` e `Ctrl+I`) especificamente nos elementos selecionados (shapes e rótulos, em vez de alterar o diagrama inteiro), refletindo no canvas e nas exportações vetoriais (SVG) e rasterizadas (PNG).
   * **Salvamento Direto no Disco**: Em navegadores Chromium (Chrome, Edge, Opera), utiliza a *File System Access API* para gravar alterações diretamente no arquivo aberto no disco ao pressionar `Ctrl+S` ou clicar em "💾 Salvar", sem passar pela pasta de Downloads.

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
│   ├── bpmn-xml-structure.md       # Dicionário de tags, namespaces e exemplos XML
│   ├── example-complete.bpmn       # Exemplo canônico de referência com layout
│   └── example-broken.bpmn         # Exemplo com erros intencionais para teste de lint
└── scripts/
    ├── bpmn_tool.py                # CLI para layout automático e validação de grafo
    ├── build_editor.py             # Script para empacotar .bpmn em HTML avulso
    └── generate_editor_html.py     # Script gerador/atualizador do editor.html central
```

---

## 3. Workflow Operacional

Siga rigorosamente as etapas abaixo ao executar a skill. Nunca entregue um diagrama sem validar.

### Passo 1: Extrair a estrutura do processo da descrição
Analise o texto do usuário e identifique:
* **Gatilho / Início (`startEvent`)**: Evento disparador do fluxo (mensagem, temporizador, manual).
* **Atividades (`task`, `userTask`, `serviceTask`)**: Passos discretos de trabalho. Use o tipo correto conforme o executor (humano = `userTask`, sistema automatizado = `serviceTask`).
* **Decisões e Bifurcações**:
  * `exclusiveGateway` (XOR): Escolha exclusiva (apenas um caminho tomado).
  * `parallelGateway` (AND): Execução simultânea e sincronização de ramos.
  * `inclusiveGateway` (OR): Um ou mais caminhos possíveis (usar apenas quando explicitamente indicado).
* **Atores e Raias (`laneSet` / `lane`)**: Se houver mais de um papel, setor ou sistema realizando etapas distintas, isole-os em raias horizontais.
* **Finais (`endEvent`)**: Todo caminho deve convergir para um evento de encerramento. Múltiplos finais independentes (ex: "Aprovado" vs. "Rejeitado") são incentivados para clareza.

### Passo 2: Gerar o XML BPMN 2.0
Consulte [`references/bpmn-xml-structure.md`](file:///c:/Projetos/bpmn-process-generator/references/bpmn-xml-structure.md) para a estrutura base.
* Namespaces canônicos obrigatórios: `bpmn`, `bpmndi`, `omgdc`, `omgdi`, `xsi`.
* IDs legíveis e únicos com convenção PascalCase: `<Tipo>_<DescricaoCurta>` (ex: `Task_ReviewApplication`, `Gateway_Approved`, `Flow_1`).
* `isExecutable="false"` por padrão para diagramas de modelagem e documentação de processos.

### Passo 3: Calcular Layout e Validar (Obrigatório)
Execute os subcomandos do utilitário nativo em Python:

```powershell
# 1. Calcular coordenadas visuais, waypoints ortogonais e copiar editor.html para o projeto
python scripts/bpmn_tool.py layout <caminho>/<processo>.bpmn

# 2. Executar linter de 2 estágios (sintaxe XML + fluxo de controle)
python scripts/bpmn_tool.py validate <caminho>/<processo>.bpmn
```

> **Nota**: O comando `layout` copia automaticamente o `editor.html` da skill para `<caminho>/editor.html` (caso ainda não exista no projeto solicitante).

O linter verifica automaticamente:
* Bem-formação do XML.
* Integridade de DI (presença de `BPMNShape` para cada nó e `BPMNEdge` com waypoints válidos para cada fluxo).
* Ausência de IDs duplicados.
* Alcance a partir do `startEvent` (sem nós inalcançáveis) e inexistência de becos sem saída (*dead ends*).
* Balanceamento de bifurcações paralelas (`parallelGateway` split deve possuir join compatível a jusante ou encerramento independente).

### Passo 4: Visualizar e Editar no `editor.html` Local
* O usuário abre o `editor.html` **local** que foi copiado para a pasta do projeto (`file:///<caminho-do-projeto>/editor.html?file=<processo>.bpmn`).
* O diretório padrão para abertura e salvamento é o próprio diretório do projeto onde o `editor.html` foi copiado.
* Recursos avançados de edição disponíveis:
  * **Tipografia e Estilo de Fonte por Elemento**: Dropdown de tamanho da fonte (`9px` a `20px`) e alternância de **Negrito** (`Ctrl+B`) e *Itálico* (`Ctrl+I`) específicos para os elementos selecionados (com detecção visual no canvas e feedback caso nenhum elemento esteja selecionado). Reflete imediatamente no canvas e é preservado fielmente nas exportações SVG e PNG.
  * **Redimensionamento de Tarefas**: Arrastar alças de canto para ajustar tamanho de caixas de atividades.
  * **Roteamento 90°**: Botão **"📐 Curva 90°"** para ortogonalizar conexões diagonais selecionadas ou de todo o processo.
  * **Alinhamento e Grade**: Encaixe magnético de nós e conexões na grade de 10 px.
  * **Paleta de Cores**: Personalização de caixas e raias via paleta rápida de cores.
  * **Histórico e Busca**: `Ctrl+Z` (desfazer), `Ctrl+Y` (refazer) e `Ctrl+F` (localizar nós no diagrama).
  * **Exportação Gráfica**: Geração de imagens vetoriais (SVG) e rasterizadas em alta resolução (PNG 2x) com formatação tipográfica intacta.
* Ajustes manuais são gravados diretamente no disco com **`Ctrl+S`**.

### Passo 5: Relatar ao Usuário
Apresente um resumo executivo do fluxo modelado, os caminhos alternativos mapeados, o resultado das validações aprovadas e os links diretos para:
1. O arquivo `.bpmn` gerado: `[<processo>.bpmn](file:///<caminho-do-projeto>/<processo>.bpmn)`
2. O editor web copiado no próprio projeto: `[editor.html](file:///<caminho-do-projeto>/editor.html?file=<processo>.bpmn)`

> [!CAUTION]
> **Proibições Estritas**:
> - **NUNCA** gere arquivo HTML com o nome do diagrama (como `<processo>.html`).
> - **NUNCA** aponte para o arquivo `editor.html` na raiz da pasta da skill (`c:/Projetos/bpmn-process-generator/editor.html`). O link fornecido ao usuário DEVE sempre apontar para o `editor.html` copiado no projeto solicitante.

---

## 4. Referência dos Scripts Utilitários

Todos os scripts operam com a biblioteca padrão do Python 3 (sem necessidade de `pip install`):

| Script | Finalidade | Exemplo de Comando |
|---|---|---|
| [`scripts/bpmn_tool.py`](file:///c:/Projetos/bpmn-process-generator/scripts/bpmn_tool.py) | Calcula layout gráfico (DI) e valida integridade semântica do grafo. | `python scripts/bpmn_tool.py layout proc.bpmn`<br>`python scripts/bpmn_tool.py validate proc.bpmn` |
| [`scripts/build_editor.py`](file:///c:/Projetos/bpmn-process-generator/scripts/build_editor.py) | Empacota um `.bpmn` dentro do template HTML avulso usando dupla codificação JSON segura. | `python scripts/build_editor.py proc.bpmn -o proc.html` |
| [`scripts/generate_editor_html.py`](file:///c:/Projetos/bpmn-process-generator/scripts/generate_editor_html.py) | Regenera o [`editor.html`](file:///c:/Projetos/bpmn-process-generator/editor.html) central embutindo os presets mais recentes. | `python scripts/generate_editor_html.py` |
| [`scripts/verify_tests.py`](file:///c:/Projetos/bpmn-process-generator/scripts/verify_tests.py) | Suíte CLI de validação dos processos BPMN de teste e integridade de DI/HTML. | `python scripts/verify_tests.py` |

---

## 5. Testes e Garantia de Qualidade

A suíte de testes pode ser executada via **pytest** a partir da raiz do repositório:

```powershell
# Executar todos os testes automatizados com saída detalhada
pytest -v

# Ou executar o verificador direto
python scripts/verify_tests.py
```

A suíte cobre:
1. Validação estrutural de grafo e sintaxe XML de todos os 6 modelos de teste (`tests/01` a `tests/06`).
2. Integridade de Diagram Interchange (BPMNDI) e limites de nós/arestas.
3. Empacotamento HTML, dupla decodificação JSON caractere a caractere e contrato contra injeção de script tags.
4. Linter e cálculo de layout do `bpmn_tool.py`, incluindo validações de casos canônicos quebrados e completos.

---

## 6. Governança e Controle de Versão

O repositório adota política rígida de controle com Git através do [`.gitignore`](file:///c:/Projetos/bpmn-process-generator/.gitignore):
* O código-fonte da skill, os scripts utilitários, os exemplos canônicos e a suíte de testes (`tests/`) são versionados.
* Arquivos HTML gerados dinamicamente (`tests/*.html`, `test-output*.html`), caches Python (`__pycache__`, `.pytest_cache`), arquivos do harness (`.harness/scratch/`) e configurações locais (`.claude/`) são automaticamente ignorados.
