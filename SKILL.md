---
name: bpmn-process-generator
description: Generates valid BPMN 2.0 process diagrams (.bpmn XML) from natural-language business process descriptions, computes visual layout (Diagram Interchange DI), validates graph integrity and control flow, and provides a central interactive web editor (editor.html) with direct disk saving (Ctrl+S), drag-and-drop, file selection, and optional standalone HTML packaging. Use this skill whenever the user describes a business process, workflow, or procedure to map, diagram, or model, or has an existing .bpmn file to validate, repair, layout, or edit.
---

# BPMN Process Generator

## 1. O que esta Skill produz

O objetivo primário da skill é produzir especificações e diagramas BPMN 2.0 válidos, visualizáveis e editáveis:

1. **`<process-name>.bpmn` (Entregável Primário)**:
   * Arquivo XML em conformidade estrita com o padrão BPMN 2.0 da OMG.
   * Diagram Interchange (DI) completo calculado via algoritmo topológico (`BPMNDiagram`, `BPMNPlane`, `BPMNShape`, `BPMNEdge` com waypoints).
   * Validado contra erros sintáticos e linter de fluxo de controle (ausência de deadlocks, nós inalcançáveis, IDs duplicados e desbalanceamento de gateways).
2. **`editor.html` (Editor Web Centralizado)**:
   * Aplicação web autossuficiente localizada na raiz da skill baseada no `bpmn-js@17.0.0` (Modeler build).
   * Permite carregar qualquer `.bpmn` via seletor nativo de arquivos ("📂 Abrir .bpmn" ou `Ctrl+O`), arrastar e soltar (*Drag & Drop*) ou menu de exemplos rápidos (*Presets*).
   * **Salvamento Direto no Disco**: Em navegadores Chromium (Chrome, Edge, Opera), utiliza a *File System Access API* para gravar alterações diretamente no arquivo aberto no disco ao pressionar `Ctrl+S` ou clicar em "💾 Salvar", sem passar pela pasta de Downloads.
3. **`<process-name>.html` (Exportação Avulsa Opcional)**:
   * Pacote HTML estático independente gerado via `python scripts/build_editor.py <file>.bpmn`. Útil quando o usuário precisa enviar um único arquivo autônomo para terceiros que não possuem a pasta da skill.

> **Convenção de Slug**: `<process-name>` deve ser um identificador seguro para sistemas de arquivos (letras minúsculas, números e hifens/underscores, sem espaços ou caracteres especiais).

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
# 1. Calcular coordenadas visuais e waypoints ortogonais
python scripts/bpmn_tool.py layout <caminho>/<processo>.bpmn

# 2. Executar linter de 2 estágios (sintaxe XML + fluxo de controle)
python scripts/bpmn_tool.py validate <caminho>/<processo>.bpmn
```

O linter verifica automaticamente:
* Bem-formação do XML.
* Integridade de DI (presença de `BPMNShape` para cada nó e `BPMNEdge` com waypoints válidos para cada fluxo).
* Ausência de IDs duplicados.
* Alcance a partir do `startEvent` (sem nós inalcançáveis) e inexistência de becos sem saída (*dead ends*).
* Balanceamento de bifurcações paralelas (`parallelGateway` split deve possuir join compatível a jusante ou encerramento independente).

### Passo 4: Visualizar e Editar no `editor.html`
* O usuário abre o [`editor.html`](file:///c:/Projetos/bpmn-process-generator/editor.html) na raiz da skill.
* Carrega o arquivo gerado via botão **"📂 Abrir .bpmn"** ou arrastando o arquivo para a janela.
* Ajustes manuais de posicionamento ou rótulos podem ser feitos na tela e salvos diretamente no mesmo arquivo com **`Ctrl+S`**.
* *(Opcional)* Se for solicitada a exportação de um HTML avulso autocontido:
  ```powershell
  python scripts/build_editor.py <caminho>/<processo>.bpmn -o <caminho>/<processo>.html -s <processo>
  ```

### Passo 5: Relatar ao Usuário
Apresente um resumo executivo do fluxo modelado, os caminhos alternativos mapeados, o resultado das validações aprovadas e os links diretos para o arquivo `.bpmn` e o [`editor.html`](file:///c:/Projetos/bpmn-process-generator/editor.html).

---

## 4. Referência dos Scripts Utilitários

Todos os scripts operam com a biblioteca padrão do Python 3 (sem necessidade de `pip install`):

| Script | Finalidade | Exemplo de Comando |
|---|---|---|
| [`scripts/bpmn_tool.py`](file:///c:/Projetos/bpmn-process-generator/scripts/bpmn_tool.py) | Calcula layout gráfico (DI) e valida integridade semântica do grafo. | `python scripts/bpmn_tool.py layout proc.bpmn`<br>`python scripts/bpmn_tool.py validate proc.bpmn` |
| [`scripts/build_editor.py`](file:///c:/Projetos/bpmn-process-generator/scripts/build_editor.py) | Empacota um `.bpmn` dentro do template HTML avulso usando dupla codificação JSON segura. | `python scripts/build_editor.py proc.bpmn -o proc.html` |
| [`scripts/generate_editor_html.py`](file:///c:/Projetos/bpmn-process-generator/scripts/generate_editor_html.py) | Regenera o [`editor.html`](file:///c:/Projetos/bpmn-process-generator/editor.html) central embutindo os presets mais recentes. | `python scripts/generate_editor_html.py` |

---

## 5. Governança e Controle de Versão

O repositório adota política rígida de controle com Git através do [`.gitignore`](file:///c:/Projetos/bpmn-process-generator/.gitignore):
* Apenas o código-fonte da skill e seus exemplos canônicos são rastreados.
* Pastas de testes locais (`tests/`), scripts de verificação interna (`scripts/verify_tests.py`), caches Python (`__pycache__`), arquivos do harness (`.harness/scratch/`) e configurações locais (`.claude/`) são automaticamente ignorados.
