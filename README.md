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
* **Editor Web Interativo (`editor.html`)**:
  * Aplicação web embarcada baseada em [bpmn-js@17.0.0](https://bpmn.io/toolkit/bpmn-js/).
  * **Distribuição Automática para Projetos**: Copiado automaticamente para a pasta do projeto que solicitou o diagrama, tornando a própria pasta do projeto o diretório padrão.
  * **Tipografia e Estilo de Fonte por Elemento**: Seletor de tamanho (`9px` a `20px`) e botões/atalhos para **Negrito** (`Ctrl+B`) e *Itálico* (`Ctrl+I`) específicos para os elementos selecionados (shapes e rótulos), preservados fielmente em exportações gráficas.
  * **Redimensionamento de Tarefas**: Alças nos 4 cantos de qualquer tarefa (*UserTask*, *ServiceTask*, etc.) com controle de dimensão mínima de segurança (80×60 px).
  * **Curvas e Trajetórias em 90°**: Botão de rota ortogonal rápida (`📐 Curva 90°`) para converter conexões retas/diagonais em ângulos retos perfeitos de 90° (Manhattan routing), aplicável a conexões selecionadas ou ao diagrama completo.
  * **Alinhamento Magnético (Grid Snapping)**: Encaixe automático em grade de 10 px para alinhamento preciso de nós e linhas.
  * **Histórico Visual e Atalhos**: Botões de Desfazer (`Ctrl+Z`) e Refazer (`Ctrl+Y`), com controle de estado do `commandStack`.
  * **Paleta de Cores Integrada**: Atribuição rápida de cores de destaque (*fill* e *stroke*) em tarefas, eventos e raias compatíveis com o padrão BPMNDI.
  * **Busca no Diagrama**: Ferramenta de localização de nós e fluxos integrada (`Ctrl+F`).
  * **Controles de Zoom e Enquadramento**: Zoom in, Zoom out, reset 100% (1:1) e enquadramento automático à janela (*fit-viewport*).
  * **Exportação Gráfica (SVG e PNG 2x)**: Download imediato do diagrama em vetor SVG e em imagem rasterizada de alta resolução PNG com a tipografia intacta.
  * **Salvamento Direto no Disco**: Utiliza a *File System Access API* no Chrome e Edge para gravar alterações diretamente no arquivo aberto (`Ctrl+S`), sem necessidade de download manual.
  * **Drag & Drop e URL Query**: Arraste qualquer `.bpmn` para o canvas ou abra com `editor.html?file=meu-processo.bpmn`.
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
3. Edite elementos com total liberdade gráfica:
   * **Redimensionamento**: Clique em qualquer tarefa e puxe uma das 4 alças nos cantos para ajustar sua largura e altura.
   * **Curvas em 90°**: Selecione conexões diagonais e clique em **"📐 Curva 90°"** para recalculá-las em rota ortogonal com cantos retos (ou clique sem seleção para alinhar todas).
   * **Grade Magnética**: Mova caixas ou arraste os pontos médios das linhas (*bendpoints*) com travamento automático na grade de 10 px.
   * **Paleta de Cores**: Selecione caixas ou fluxos e clique numa das opções de cores para destacá-los visualmente.
   * **Histórico e Busca**: Use **`Ctrl+Z`** (desfazer), **`Ctrl+Y`** (refazer) e **`Ctrl+F`** (busca no processo).
   * **Exportação Gráfica**: Baixe cópias prontas para relatórios clicando em **"🖼️ SVG"** ou **"📷 PNG"**.
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

#### Executar a Suíte de Testes:
Executa a validação completa de todos os diagramas BPMN de teste e utilitários via pytest ou script:
```bash
# Executar suíte pytest
pytest -v

# Ou executar o verificador direto
python scripts/verify_tests.py
```

---

## 🤖 Uso como Skill para Agentes de IA

Esta pasta pode ser adicionada como uma **Skill** no Claude Code ou no Google Antigravity. O assistente é capaz de:
1. Ler uma descrição de processo corporativo enviada pelo usuário.
2. Identificar atores, tarefas humanas/sistemas, bifurcações condicionais e eventos.
3. Gerar o arquivo `.bpmn` correspondente na pasta do projeto solicitante.
4. Aplicar o layout automático e validar o grafo com `bpmn_tool.py` (que copia automaticamente o `editor.html` para a pasta do projeto se não existir).
5. Disponibilizar o link para o `editor.html` local copiado no projeto (`editor.html?file=<processo>.bpmn`), configurado para apontar por padrão para o diagrama gerado (sem nunca carregar exemplos da pasta da skill), sem criar arquivos HTML com o nome do diagrama e sem apontar para a pasta da skill.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença [MIT](LICENSE).
