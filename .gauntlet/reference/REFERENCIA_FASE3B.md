# Referencia Gauntlet - Editor BPMN, Fase 3B (integracao com a skill)

Origem: `PLANO_MELHORIAS_EDITOR.md` (secao 3, Fase 3, bloco 3.2; secoes 4 e 6). Referencia congelada do loop. Escopo: **F3.5, F3.6, F3.7**. Os demais itens da Fase 3 (F3.8-F3.12) estao FORA de escopo. Fases 1, 2 e 3A ja foram entregues (EDITOR_VERSION 1.4.0) e NAO podem regredir.

## Fonte unica do editor

O editor vive em `scripts/generate_editor_html.py` (f-string Python; JS com chaves duplicadas `{{ }}`) e e gerado para `editor.html`. Toda mudanca vai no gerador; `editor.html` deve ser regenerado e coerente. Incrementar `EDITOR_VERSION` (1.4.0 -> 1.5.0) e atualizar os testes de versao. O editor e JavaScript no navegador: a logica da skill que hoje existe em Python precisa ser **portada para JS com os mesmos resultados**, provada por testes de paridade contra o Python. Fontes de verdade (somente leitura; nao mudar o comportamento existente): `scripts/bpmn_build.py` (spec -> XML: `build_tree`, `_normalise_*`, ids, `SpecError`), `scripts/bpmn_tool.py` (`extract_spec`, `compute_diagram`, `build_graph`, `run_layout` com preservacao de estilos de fonte G1) e `references/process-spec.md` (formato e erros de spec).

## Itens e criterios de aceite

- **F3.5 Importar e exportar o spec JSON.**
  - **Exportar** (menu Arquivo): gera o spec JSON do diagrama aberto, com a mesma semantica de `extract_spec` (ids dos elementos como ids internos, `type` com alias preferido, `event`, `attachedTo`, `interrupting`, `lane`, `lanes`, `flows` com `label`/`condition`/`default`, `executable`). Baixa/salva como `<nome>-spec.json` (JSON UTF-8 com indentacao, sem escapar acentos). Avisa em pt-BR, sem bloquear, quando o diagrama tem varios processos/pools ou subprocesso expandido com fluxo interno (perda na reconstrucao), como o `extract` faz.
  - **Importar** (menu Arquivo): le um spec JSON, valida com **os mesmos erros do `SpecError`** (campos obrigatorios, type/event desconhecidos, id repetido, fluxo para no inexistente, boundary sem/ruim `attachedTo`, default fora de gateway ou com condition, raia inexistente), mostrando a mensagem em pt-BR sem alterar o diagrama atual quando invalido; quando valido, gera o BPMN (ids PascalCase sem acento com prefixo por tipo, sufixo numerico em colisao, `Flow_N` sequenciais, `incoming`/`outgoing` coerentes, laneSet quando houver raias, nos sem raia na primeira) e **calcula o layout (F3.6)**, abrindo o resultado como diagrama novo. Se houver alteracoes nao salvas, pede confirmacao antes de substituir.
  - **Paridade (obrigatoria, testada):** para `references/example-spec.json`, para o spec extraido (`extract_spec`) de cada `assets/templates/*.bpmn` e de pelo menos 3 arquivos de `tests/*.bpmn`, a parte semantica do XML gerada no editor (ids, tipos, nomes, fluxos, condicoes, default, raias, eventos) e igual a de `bpmn_build.build_xml`; e o round-trip editor -> spec -> editor preserva o processo (mesmo conjunto de nos/fluxos/raias). A saida do editor tambem passa em `bpmn_tool.py validate` e no validador embutido (3A) sem erros.
- **F3.6 Auto-layout no editor**, reutilizando a logica de `bpmn_tool layout` (portar `build_graph`/`compute_diagram`: ordem topologica, colunas, linhas, raias, colisoes, waypoints, mesmas constantes de tamanho/espacamento).
  - Acao "Organizar automaticamente" (menu Editar ou Exibir, com atalho opcional e rotulo acessivel) aplicada ao diagrama aberto.
  - **Paridade (obrigatoria, testada):** para os `.bpmn` do repositorio (exemplos, templates, 3+ de `tests/`), mesmos bounds de shapes (x, y, width, height) e mesmos waypoints de arestas que `bpmn_tool.compute_diagram` produz para o mesmo grafo.
  - Aplicado de forma **desfazivel**: uma unica operacao no `commandStack` (um Ctrl+Z restaura todas as posicoes); marca o diagrama como alterado; preserva nomes, cores, estilos de fonte e documentacao (G1); nao muda o grafo. Funciona com e sem raias; em diagrama vazio nao faz nada (sem erro). Estado do diagrama continua valido apos o layout (validador 3A sem novos erros).
  - O import do spec (F3.5) usa o mesmo codigo de layout.
- **F3.7 Comentarios de revisao por elemento**, **em arquivo lateral** (decisao do plano, secao 6 item 2: mais seguro para ferramentas que leem BPMN padrao). O `.bpmn` salvo/exportado NAO muda por causa de comentarios (testar: XML identico com e sem comentarios, byte a byte).
  - UI: secao "Comentarios de revisao" no painel de propriedades do elemento selecionado (lista, adicionar, resolver/reabrir, excluir; autor opcional; data automatica), com rotulos acessiveis e pt-BR. Indicador no canvas (selo/contador, distinto dos marcadores de validacao 3A, nao exportado no SVG/PNG/PDF, nao entra no XML) nos elementos com comentarios abertos; contador total no rodape ou no menu.
  - Formato do arquivo lateral: JSON `<nome>.review.json` com `version`, referencia ao diagrama (nome do arquivo) e lista de comentarios (`id`, `elementId`, `text`, `author`, `createdAt`, `resolved`). Menu Arquivo: "Salvar comentarios" e "Abrir comentarios" (salva por File System Access ao lado do .bpmn quando possivel, senao download; abre por seletor/`input file`). Rascunho local em `localStorage` (try/catch, sem erro quando bloqueado) para nao perder comentarios entre sessoes, sem misturar com o rascunho do diagrama. Comentarios de elementos que nao existem mais sao preservados e listados como orfaos, nao descartados em silencio.
  - Comentar/resolver NAO marca o diagrama como alterado nem entra no historico de desfazer do diagrama; porem comentarios nao salvos entram em um aviso proprio ao fechar (nao confundir com `beforeunload` do diagrama; sem aviso quando nao ha comentarios pendentes).

## Testes

- Novos testes em `tests/test_editor_integration_phase3b.py` (Chromium via Playwright Python; bpmn-js via CDN) e, quando util, testes Python puros de paridade que chamam `bpmn_build`/`bpmn_tool` direto e comparam com o resultado do editor. Devem falhar no codigo anterior e passar depois. Cada item F3.5-F3.7 coberto, com exemplos do repositorio como caso de referencia (criterio do plano).
- A suite atual (482 testes, `python -m pytest -q`, ~104 s) permanece verde, incluindo Fases 1, 2 e 3A. Se um seletor/ID existente mudar, ATUALIZE o teste mantendo a intencao; nunca enfraquecer asserts, nao usar `skip`/`xfail`/supressoes. Reutilizar uma sessao de editor compartilhada nos testes novos para manter o acrescimo de tempo da suite < 30 s. Nao baixar o tempo-limite do gate.
- Testes deterministicos; sem esperas fixas longas (preferir `wait_for_function`).

## Restricoes

- Funciona nos modos CDN e vendorizado; `tests/test_editor_offline.py` continua passando. Sem dependencias novas (nada de CDN extra para layout/spec).
- Nao alterar arquivos protegidos (`pytest.ini`, `scripts/verify_tests.py`, `AGENTS.md`, `.harness/harness.yaml`, `.claude/harness/`). Nao alterar o comportamento de `scripts/bpmn_build.py`, `scripts/bpmn_tool.py` nem `scripts/lint_rules.py` (leitura apenas; se precisar expor algo, so de forma aditiva e coberta por teste).
- File System Access API so em Chromium: manter fallback de download.
- Nao alterar o formato `.bpmn` salvo alem do layout pedido pelo usuario; `bpmn_tool.py validate` continua passando nos exemplos e nos arquivos gerados pelo import.
- Acessibilidade: foco visivel, rotulos acessiveis, contraste adequado nos novos controles; pt-BR.
- Registrar no resumo o tamanho do `editor.html` antes/depois (hoje ~285 KB) e justificar o crescimento.
- Trabalhar em passos pequenos, rodando `python -m pytest -q` a cada mudanca logica; deixar a arvore consistente e testes verdes ao fim da iteracao, listando o que falta no resumo. Ordem sugerida: (1) porte do layout + paridade (F3.6 numerico); (2) exportar spec; (3) importar spec/build + SpecError; (4) auto-layout desfazivel e menu; (5) comentarios; (6) versao 1.5.0.

## Criterio de aceite global

F3.5-F3.7 implementados e cobertos por teste, com paridade comprovada contra `bpmn_build`/`bpmn_tool` nos exemplos do repositorio; XML intacto com comentarios; sem regressao das Fases 1, 2 e 3A; testes verdes.
