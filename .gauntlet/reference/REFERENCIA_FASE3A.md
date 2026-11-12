# Referencia Gauntlet - Editor BPMN, Fase 3A (validacao viva)

Origem: `PLANO_MELHORIAS_EDITOR.md` (secao 3, Fase 3, bloco 3.1; secao 4 restricoes). Referencia congelada do loop. Escopo: **F3.1 a F3.4**. Os demais itens da Fase 3 (F3.5-F3.12) ficam para loops seguintes e estao FORA de escopo. Fases 1 e 2 ja foram entregues (EDITOR_VERSION 1.3.1) e NAO podem regredir.

## Fonte unica do editor

O editor vive em `scripts/generate_editor_html.py` (f-string Python; JS com chaves duplicadas `{{ }}`) e e gerado para `editor.html`. Toda mudanca vai no gerador; `editor.html` deve ser regenerado e coerente. Incrementar `EDITOR_VERSION` (1.3.1 -> 1.4.0) e atualizar os testes de versao. A fonte de verdade das regras e `scripts/lint_rules.py` (registro `@register(nome, severidade, fixable)`); a funcao de reparo e `run_fix` em `scripts/bpmn_tool.py`. Hoje o editor implementa so 6 regras em `collectValidationFindings()` (dead-end, unreachable-node, no-path-to-end, gateway-without-condition, unnamed-element, lane-coverage-missing).

## Itens e criterios de aceite

- **F3.1** Portar para o editor (JS, em `generate_editor_html.py`) as regras do linter que fazem sentido sobre o modelo em memoria do bpmn-js, **com os mesmos ids de regra e as mesmas severidades** de `lint_rules.py`. Alvo: todas as regras de grafo, evento, gateway, raia e estilo (ex.: missing-start-event, missing-end-event, start-has-incoming, end-has-outgoing, not-reachable-from-start, default-flow-invalid, boundary-invalid, boundary-host-missing, lane-coverage-duplicate, implicit-split, implicit-merge, mixed-gateway, parallel-join-without-split, parallel-split-without-join, duplicate-flow, self-loop, useless-gateway, id-convention, name-too-long, di-overlap, alem das 6 existentes). Regras que so existem por o XML poder estar malformado ou sem DI (ex.: malformed-element, missing-diagram, missing-plane, missing-shape, missing-edge, edge-waypoints, duplicate-id, flow-refs-mismatch, dangling-flow-ref, missing-process) podem ser omitidas no editor, desde que o motivo conste em um comentario/tabela no gerador e em teste de contrato que lista rule ids portados e rule ids omitidos (juntos cobrem TODOS os ids de `lint_rules.py`; um id novo no linter sem decisao falha o teste). A mensagem pode ser em pt-BR. O painel mostra o id da regra e a severidade (error/warn/info) de cada achado e permite filtrar/contar por severidade.
- **Paridade:** teste que, para `references/example-broken.bpmn`, `references/example-complete.bpmn` e pelo menos 3 modelos de `assets/templates/*.bpmn`, compara o conjunto `(rule id, element id)` produzido pelo editor (para as regras portadas) com o produzido por `lint_rules.run_rules` do Python sobre o mesmo arquivo. Divergencias so podem ocorrer em regras listadas como omitidas.
- **F3.2** Validacao automatica: roda sozinha, com debounce curto (~300-600 ms), apos qualquer alteracao do diagrama (`commandStack.changed`) e apos abrir/importar; nao exige clicar. Sem travar a digitacao e sem rodar em laco. O botao manual pode permanecer. Um indicador compacto de contagem (ex.: erros/avisos) fica visivel mesmo com o painel fechado (rodape ou barra), com nome acessivel.
- **F3.3** Marcar no canvas os elementos com problema: marcador visual (contorno colorido via `canvas.addMarker` e/ou overlay com icone) distinto por severidade (error vs warn; info opcional). O marcador some quando o problema e corrigido, nao entra no XML exportado, nao altera historico de desfazer e nao polui o PNG/SVG exportado (documentar ou excluir os marcadores na exportacao). Tem alternativa nao so por cor (icone/forma ou texto acessivel). Clicar no achado do painel seleciona e centraliza o elemento (ja existe; manter).
- **F3.4** Botao "Corrigir" para problemas mecanicamente corrigiveis (as regras marcadas `fixable` no linter e equivalentes mecanicos seguros no editor, ao menos `duplicate-flow`: remover fluxo duplicado exato, e quando aplicavel `flow-refs-mismatch`/DI faltante se o editor tiver o caso). Mostra **previa** (lista do que sera alterado) e so aplica apos confirmacao; aplica via `commandStack` em uma unica operacao (um Ctrl+Z desfaz tudo); nunca cria nos, fluxos, condicoes ou nomes (mesma filosofia do `run_fix`). Sem problemas corrigiveis o botao fica desabilitado ou oculto.

## Testes

- Novos testes de comportamento em Chromium (Playwright Python; bpmn-js via CDN) em `tests/test_editor_validation_phase3a.py` (e, se util, um teste Python puro de contrato de ids). Devem falhar no codigo anterior e passar depois. Cada item F3.1-F3.4 coberto; usar exemplos do repositorio como caso de referencia (criterio do plano: cada item tem teste de comportamento e pelo menos um exemplo do repositorio).
- Suite atual (430 testes, `python -m pytest -q`, ~82 s) permanece verde, incluindo Fases 1 e 2. Se um seletor/ID existente mudar, ATUALIZE o teste mantendo a intencao; nunca enfraquecer asserts, nao usar `skip`/`xfail`/supressoes. Nao baixar o tempo-limite do gate.
- Testes deterministicos; nao introduzir esperas fixas longas (preferir `wait_for_function`). Tempo adicional da suite alvo < 25 s.

## Restricoes

- Funciona nos modos CDN e vendorizado; `tests/test_editor_offline.py` continua passando.
- Nao alterar arquivos protegidos (`pytest.ini`, `scripts/verify_tests.py`, `AGENTS.md`, `.harness/harness.yaml`, `.claude/harness/`). Nao alterar `scripts/lint_rules.py` nem `scripts/bpmn_tool.py` de forma que mude o comportamento do linter/fix existente (leitura apenas; se precisar expor lista de ids, faca de forma aditiva e coberta por teste).
- Nao alterar o formato `.bpmn` salvo (marcadores e contadores nao vao para o XML). `bpmn_tool.py validate` continua passando nos exemplos.
- Acessibilidade: foco visivel, rotulos acessiveis, contraste adequado nos novos controles/marcadores; pt-BR.
- Registrar no resumo o tamanho do `editor.html` antes/depois (hoje ~247 KB) e justificar o crescimento.
- Trabalhar em passos pequenos, rodando `python -m pytest -q` a cada mudanca logica; deixar a arvore consistente e testes verdes ao fim da iteracao, listando o que falta no resumo.

## Criterio de aceite global

F3.1-F3.4 implementados e cobertos por teste, com paridade comprovada contra o linter Python nos exemplos do repositorio; sem regressao das Fases 1 e 2; testes verdes.
