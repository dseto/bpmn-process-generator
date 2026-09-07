# BPMN Process Generator & Editor

Gerador automatizado de diagramas de processo **BPMN 2.0** a partir de linguagem natural e editor visual interativo integrado com suporte a gravação direta no disco.

Projetado como uma **Agent Skill** para assistentes de IA (Claude Code, Antigravity) e utilizável como ferramenta CLI e web independente, com **zero dependências externas** (opera 100% com a biblioteca padrão do Python 3 e CDN).

---

## 🚀 Principais Recursos

* **Modelagem Semântica Automatizada**: Converte descrições em linguagem natural em arquivos `.bpmn` aderentes ao padrão oficial BPMN 2.0 da OMG.
* **Layout Automático (DI Completo)**: Calcula automaticamente coordenadas visuais cartesianas (`BPMNShape`, `BPMNEdge` e `waypoint`) e distribui elementos horizontalmente com base no algoritmo de caminho mais longo e ordenação topológica tolerante a ciclos de retrabalho.
* **Suporte a Raias (*Swimlanes*)**: Mapeia atores e departamentos distintos em raias horizontais (`laneSet`/`lane`), calculando faixas e conexões ortogonais entre raias.
* **Validação Estrita de Grafo (Linter em 2 Estágios)**:
  1. *Sintaxe*: Verificação de bem-formação estrutural do XML.
  2. *Controle de Fluxo*: Checagem de nós inalcançáveis (*unreachable*), becos sem saída (*dead ends*), duplicidade de identificadores, integridade de referências e balanceamento de bifurcações paralelas.
* **Editor Web Centralizado (`editor.html`)**:
  * Aplicação web embarcada baseada em [bpmn-js@17.0.0](https://bpmn.io/toolkit/bpmn-js/).
  * **Salvamento Direto no Disco**: Utiliza a *File System Access API* no Chrome e Edge para gravar alterações diretamente no arquivo aberto (`Ctrl+S`), sem necessidade de download manual.
  * **Drag & Drop**: Arraste qualquer arquivo `.bpmn` ou `.xml` para a janela do navegador para visualizá-lo e editá-lo instantaneamente.
  * **Exemplos Integrados (*Presets*)**: Seletor com diagramas pré-carregados que funcionam 100% offline e sem restrições de CORS via protocolo `file://`.
* **Exportação Portátil Avulsa**: Capacidade de empacotar qualquer `.bpmn` em um único arquivo `.html` autossuficiente para envio a clientes e partes interessadas.

---

## 📁 Estrutura do Repositório

```
bpmn-process-generator/
├── editor.html                     # Editor web centralizado e interativo
├── SKILL.md                        # Definição e instruções operacionais da Skill
├── README.md                       # Documentação geral do projeto
├── .gitignore                      # Exclusões para controle de versão mínimo
├── AGENTS.md                       # Governança para execução por agentes
├── assets/
│   └── bpmn-editor-template.html   # Template base para geração de HTMLs avulsos
├── references/
│   ├── bpmn-xml-structure.md       # Especificação técnica e dicionário de tags
│   ├── example-complete.bpmn       # Exemplo canônico com layout DI completo
│   └── example-broken.bpmn         # Exemplo com erros propositais para teste de lint
└── scripts/
    ├── bpmn_tool.py                # Motor CLI: cálculo de layout e linter
    ├── build_editor.py             # Empacotador de .bpmn para HTML autônomo
    └── generate_editor_html.py     # Gerador do editor.html com presets embutidos
```

---

## 🛠️ Requisitos e Instalação

* **Python 3.8+** (apenas a biblioteca padrão; nenhum pacote `pip` é necessário).
* **Navegador Web Moderno** (Google Chrome, Microsoft Edge, Firefox, Brave).
  * *Dica*: Navegadores baseados em Chromium fornecem suporte completo à *File System Access API* para salvamento direto no disco com `Ctrl+S`.

Clone o repositório:
```bash
git clone https://github.com/dseto/bpmn-process-generator.git
cd bpmn-process-generator
```

---

## 📖 Como Utilizar

### 1. Utilizando o Editor Centralizado (`editor.html`)

1. Dê um duplo clique em `editor.html` para abri-lo no navegador.
2. Utilize as opções da barra superior:
   * **📂 Abrir .bpmn (`Ctrl+O`)**: Escolha um arquivo do seu computador.
   * **Drag & Drop**: Arraste um arquivo `.bpmn` para dentro do canvas.
   * **Seletor de Exemplos**: Escolha um dos diagramas prontos no menu suspenso.
3. Edite elementos arrastando, renomeando ou adicionando novas etapas.
4. Pressione **`Ctrl+S`** ou clique em **"💾 Salvar"** para regravar as alterações diretamente no arquivo no disco.

---

### 2. Linha de Comando (Scripts CLI)

#### Calcular Layout de um Arquivo BPMN:
Gera ou recalcula as posições cartesianas e conexões de um processo:
```bash
python scripts/bpmn_tool.py layout meu-processo.bpmn [-o processo-com-layout.bpmn]
```

#### Validar Sintaxe e Fluxo de Controle:
Executa o linter semântico:
```bash
python scripts/bpmn_tool.py validate meu-processo.bpmn
```
*Retorna código `0` em caso de sucesso ou `1` com a lista detalhada de problemas encontrados.*

#### Gerar um HTML Avulso Autocontido:
Empacota o XML dentro de um HTML independente para envio externo:
```bash
python scripts/build_editor.py meu-processo.bpmn -o meu-processo.html -s meu-processo
```

#### Atualizar o Editor Central com Novos Exemplos:
Reconstrói o `editor.html` atualizando a lista de presets embutidos:
```bash
python scripts/generate_editor_html.py
```

---

## 🤖 Uso como Skill para Agentes de IA

Esta pasta pode ser adicionada como uma **Skill** no Claude Code ou no Google Antigravity. O assistente é capaz de:
1. Ler uma descrição de processo corporativo enviada pelo usuário.
2. Identificar atores, tarefas humanas/sistemas, bifurcações condicionais e eventos.
3. Gerar o arquivo `.bpmn` correspondente.
4. Aplicar o layout automático e validar o grafo com `bpmn_tool.py`.
5. Disponibilizar o arquivo para abertura e refinamento imediato no `editor.html`.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença [MIT](LICENSE).
