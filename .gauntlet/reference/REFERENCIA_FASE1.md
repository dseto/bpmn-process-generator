# Referencia Gauntlet - Editor BPMN, Fase 1 (nao perder trabalho)

Origem: `PLANO_MELHORIAS_EDITOR.md` (secoes 2.2, 3 Fase 0/1, 4). Este documento e a referencia congelada do loop. Escopo desta rodada: **F0.2 (parcial) + F1.1 a F1.8**. Fases 2 e 3 estao FORA de escopo.

## Fonte unica do editor

O editor vive em `scripts/generate_editor_html.py` (f-string Python; JS com chaves duplicadas `{{ }}`) e e gerado para `editor.html`. Toda mudanca deve ser feita no gerador e o `editor.html` deve ser regenerado (comando atual do repositorio) e permanecer coerente com o gerador. `EDITOR_VERSION` deve ser incrementado (ex.: 1.1.0 -> 1.2.0) e os testes de versao atualizados.

## Defeitos a corrigir

| # | Problema |
|---|---|
| B1 | Um unico `Ctrl+Z` desfaz DUAS acoes (listener da janela duplica o atalho do bpmn-js `keyboard.bindTo: document`). |
| B2 | `Ctrl+Z` com foco em campo de texto (ex.: `#prop-name`) desfaz a edicao de OUTRO elemento e o texto digitado fica no campo. |
| B3 | Tamanho de fonte, negrito e italico nao sao gravados no `.bpmn` (so CSS em memoria, `elementFontStyles`). |
| B4 | Negrito/italico/tamanho ficam fora do historico de desfazer e nao marcam o diagrama como alterado. |
| B5 | Nao ha aviso (`beforeunload`) ao fechar/recarregar com alteracoes nao salvas. |
| B6 | Editor do projeto carrega o diagrama embutido no HTML antes do arquivo em disco; salvar depois pode sobrescrever versao mais nova. |

## Itens e criterios de aceite

- **F1.1** (B1): um atalho = uma unica acao de desfazer/refazer. Remover o listener duplicado ou manter apenas o do bpmn-js.
- **F1.2** (B2): `Ctrl+Z`, `Ctrl+Y`, `Ctrl+B`, `Ctrl+I`, `Ctrl+S` respeitam o foco. Com foco em `input`/`textarea`/contenteditable, o atalho age no campo, nunca no canvas (exceto `Ctrl+S`, que salva sem desfazer nada).
- **F1.3** (B3, B4): gravar a fonte no proprio DI do BPMN (`bpmndi:BPMNLabel` + `dc:Font`, ou `BPMNLabelStyle`), alterar via `commandStack` (desfazer/refazer funciona) e marcar o diagrama como alterado. Fonte sobrevive a salvar e reabrir. Arquivo sem informacao de fonte assume o padrao atual (12 px, sem negrito) e NAO e alterado ao abrir.
- **F1.4** (B5): `beforeunload` ativo apenas enquanto houver alteracoes nao salvas.
- **F1.5**: rascunho automatico em `localStorage` (try/catch com fallback sem erro), com oferta de recuperacao ao reabrir o editor; descartado apos salvar.
- **F1.6** (B6): ao abrir arquivo do projeto, ler do disco ANTES de usar o snapshot embutido; se o disco tiver versao mais nova que o snapshot, avisar o usuario.
- **F1.7**: aviso quando o arquivo aberto mudou no disco enquanto o editor estava aberto (ex.: skill regenerou), com opcao de recarregar. Nunca sobrescrever silenciosamente.
- **F1.8**: seletor "Tipo do elemento" mostra apenas tipos compativeis com o elemento e exibe o tipo atual; nao aparece para StartEvent/EndEvent/Lane quando nao ha troca valida.

**Criterio global:** nenhum caso de perda silenciosa de dados nos testes de comportamento; fonte sobrevive a salvar e reabrir.

## Testes (F0.2 parcial)

- Adicionar testes de comportamento em navegador (Playwright para Python ja esta instalado; Chromium funciona; bpmn-js carrega via CDN) cobrindo B1 a B6 e F1.5, F1.7, F1.8.
- Os testes novos devem falhar no codigo anterior e passar depois da correcao.
- A suite atual (305 testes, `python -m pytest -q`, ~5 s) permanece verde. Testes de comportamento devem ser deterministicos e razoavelmente rapidos (alvo: < 60 s no total).
- Nao enfraquecer testes existentes. Nao usar `skip`/`xfail`/supressoes (o anti-cheat as detecta). Se um teste nao puder rodar em algum ambiente, registre como blocker no resumo em vez de suprimir.

## Restricoes

- Funciona nos dois modos (CDN e vendorizado/offline); `tests/test_editor_offline.py` continua passando.
- File System Access API so existe em Chromium: manter fallback de download.
- Nao alterar arquivos protegidos (`pytest.ini`, `scripts/verify_tests.py`, `AGENTS.md`, `.harness/harness.yaml`).
- Nao alterar o formato do `.bpmn` de forma que quebre validacao/layout existentes (`bpmn_tool.py validate/layout/fix`).
- Nenhuma mudanca visual alem do necessario (avisos/banners e seletor de tipo). Barra de ferramentas, traducao e demais itens da Fase 2 ficam para outra rodada.
- Tamanho do `editor.html`: registrar o delta no resumo.
