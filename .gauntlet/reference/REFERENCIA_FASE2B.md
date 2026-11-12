# Referencia Gauntlet - Editor BPMN, Fase 2 (mais intuitivo)

Origem: `PLANO_MELHORIAS_EDITOR.md` (secao 3, Fase 2; secao 4 restricoes). Referencia congelada do loop. Escopo: **F2.1 a F2.15 + carry-over G1**. A Fase 3 esta FORA de escopo. A Fase 1 ja foi entregue (atalhos respeitam foco, fonte no DI via `element.setFontStyle`, banners de rascunho/disco, `EDITOR_VERSION` 1.2.0) e NAO pode regredir.

## Fonte unica do editor

O editor vive em `scripts/generate_editor_html.py` (f-string Python; JS com chaves duplicadas `{{ }}`) e e gerado para `editor.html`. Toda mudanca vai no gerador; `editor.html` deve ser regenerado e coerente com o gerador. Incrementar `EDITOR_VERSION` (1.2.0 -> 1.3.0) e atualizar os testes de versao. `assets/bpmn-editor-template.html` nao e o alvo desta fase, mas nao deve quebrar.

## Itens e criterios de aceite

### 2.1 Barra de ferramentas e navegacao
- **F2.1** Reorganizar a barra em grupos com menus: **Arquivo** (abrir, salvar, salvar como, novo, exportar), **Editar** (desfazer, refazer, buscar), **Exibir** (zoom, minimapa, ajuda). Na barra ficam so as acoes mais usadas (ex.: salvar, desfazer, refazer, zoom). Menus abrem por clique e teclado (Enter/Espaco/Setas/Esc) e fecham ao clicar fora. Todas as funcoes atuais continuam acessiveis (nenhuma perdida) e os atalhos existentes continuam funcionando.
- **F2.2** Barra contextual que aparece SOMENTE com selecao: cor, fonte, alinhamento e tipo. Some quando nao ha selecao. A selecao multipla mostra o alinhamento.
- **F2.3** Rodape com porcentagem de zoom (atualizada ao vivo) e botao "ajustar a selecao" (zoom para caber a selecao; sem selecao, ajusta ao diagrama).
- **F2.4** Todo controle da barra/menus/cores tem nome acessivel (`aria-label` ou texto visivel) e e operavel por teclado. As cores deixam de ser `div` puros (`button`/`role=button` com `tabindex` e `aria-label` com o nome da cor, `aria-pressed` quando aplicavel). Meta: 100% dos controles da barra com rotulo acessivel (verificavel por teste).
- **F2.5** Layout responsivo sem quebra em 3 linhas nas larguras 1440, 1024 e 800 px (medir altura da barra por teste).

### 2.2 Idioma
- **F2.6** Traduzir para pt-BR a paleta de criacao, menus de contexto e rotulos do bpmn-js ("Create task", "Activate lasso tool" etc.) via modulo de traducao customizado (`translate` do bpmn-js injetado como modulo adicional). Termos nao mapeados caem no original sem erro. Funciona nos modos CDN e offline.

### 2.3 Alinhamento
- **F2.7** Adicionar alinhar pelo topo, base, direita e centro vertical (alem de esquerda e centro horizontal ja existentes).
- **F2.8** Adicionar distribuir vertical (alem do horizontal, se existir).
- **F2.9** Renomear "Centralizar" para deixar o eixo claro (ex.: "Centro horizontal" / "Centro vertical"). Tooltips descritivos.
- Todas as operacoes de alinhamento passam pelo `commandStack` (um Ctrl+Z desfaz a operacao inteira).

### 2.4 Painel de propriedades
- **F2.10** Nome e documentacao aplicados enquanto o usuario digita (debounce curto, ~250-400 ms), sem exigir sair do campo; sem poluir o historico com um comando por tecla (agrupar/coalescer) e sem perder o foco/cursor.
- **F2.11** Campos especificos por tipo: evento de tempo (timer: tipo e valor), evento de mensagem (nome da mensagem), evento de erro (codigo), tarefa com responsavel (atribuido/lane), raia com nome. Os valores sao gravados no XML BPMN valido (definicoes de evento padrao) e sobrevivem a salvar/reabrir; `bpmn_tool.py validate` continua passando.
- **F2.12** Sem selecao, o painel mostra propriedades do processo (id, nome, versao/documentacao quando aplicavel) e permite editar o nome do processo.

### 2.5 Descoberta e primeiro uso
- **F2.13** Tecla `?` (fora de campos de texto) abre a lista de atalhos; Esc fecha; tambem acessivel pelo menu Exibir/Ajuda.
- **F2.14** Tela inicial/novo diagrama oferece modelos prontos: linear, com decisao, com raias, com laco. Cada modelo gera BPMN valido (sem erros no validador embutido e em `bpmn_tool.py validate`).
- **F2.15** Diagrama grande abre com zoom que cabe a tela e legivel (nao 18%: definir zoom minimo de abertura razoavel e ajuste por area util, com rolagem/centralizacao no inicio do fluxo quando nao der para ler tudo) e minimapa para navegar. Se `bpmn-js-minimap` nao tiver build de arquivo unico/offline compativel, implementar minimapa proprio leve (SVG/Canvas) sem dependencia nova.

### Carry-over da Fase 1
- **G1** `bpmn_tool.py layout` nao pode descartar `bpmndi:BPMNLabelStyle`/`dc:Font` de arquivos que ja os tem (preservar estilo de fonte por elemento apos relayout), com teste. Se inviavel, documentar a limitacao em `SKILL.md`/docs relevantes com teste de contrato.

## Testes

- Testes de comportamento em Chromium (Playwright para Python ja instalado; bpmn-js via CDN) em novo arquivo(s) `tests/test_editor_ui_phase2*.py`, cobrindo cada item acima; devem falhar no codigo anterior e passar depois.
- Suite atual (339 testes, `python -m pytest -q`) permanece verde, incluindo os testes da Fase 1 (`tests/test_editor_behavior.py`). Se um teste existente depender de um seletor/ID que a reorganizacao da barra mudar, ATUALIZE o seletor mantendo a intencao do teste; nunca enfraquecer asserts, nao usar `skip`/`xfail`/supressoes.
- Testes deterministicos; tempo total da suite alvo < 90 s. Se nao puder rodar em algum ambiente, registrar como blocker no resumo.

## Restricoes

- Funciona nos modos CDN e vendorizado; `tests/test_editor_offline.py` continua passando.
- File System Access API so em Chromium: manter fallback de download.
- Nao alterar arquivos protegidos (`pytest.ini`, `scripts/verify_tests.py`, `AGENTS.md`, `.harness/harness.yaml`).
- Nao alterar o formato `.bpmn` de forma que quebre `bpmn_tool.py validate/layout/fix` nem os presets existentes.
- Acessibilidade: foco visivel, ordem de tab logica, contraste adequado.
- Registrar no resumo o tamanho do `editor.html` antes/depois.
- Trabalhar em passos pequenos, rodando `python -m pytest -q` a cada mudanca logica; deixar a arvore consistente e testes verdes ao fim de cada iteracao, listando o que falta no resumo.

## Criterio de aceite global

Todos os itens F2.1-F2.15 e G1 implementados e cobertos por teste; sem regressao da Fase 1; testes verdes. (O teste de usabilidade com pessoas descrito no plano esta fora do escopo automatizavel e deve ser apenas mencionado como pendente.)

## Nota da rodada 2b

O codigo da iteracao anterior (commit feat(editor): fase 2) ja existe na branch e a suite (410 testes, ~70 s) passa. Esta rodada deve VERIFICAR cada item F2.1-F2.15 e G1 contra os criterios acima, corrigir lacunas e defeitos encontrados (ex.: toast sobrepondo o minimapa; modo vendorizado nao exercitado; campo de responsavel so para alguns tipos de tarefa) e registrar o que continuar pendente. Nao reescrever o que ja atende.
