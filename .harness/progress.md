# Claude Progress

Contrato: `bpmn-skill-upgrade`

## Features

| id | desc | status |
| --- | --- | --- |
| T-01 | Descrever um processo num spec JSON simples gera um arquivo BPMN com ids legíveis e referências de fluxo sempre coerentes | done |
| T-02 | Eventos tipados, prazos anexados a tarefas, condições de decisão e raias completas saem corretos do spec | done |
| T-03 | Um único comando entrega o diagrama pronto: gera, posiciona, valida e deixa o editor na pasta do projeto | done |
| T-04 | Um diagrama existente pode ser reconvertido em spec e regerado sem perder informação do processo | done |
| T-05 | Cada checagem do validador vira uma regra identificável com gravidade própria (erro, aviso, informação) | done |
| T-06 | O validador acusa erros estruturais que hoje passam despercebidos e reprovam o diagrama | done |
| T-07 | O validador aponta problemas de qualidade de modelagem como aviso, sem reprovar o diagrama | done |
| T-08 | O resultado da validação pode ser lido em JSON pelo assistente e endurecido para tratar avisos como falha | done |
| T-09 | Problemas mecânicos do arquivo são corrigidos automaticamente, com prévia do que muda e sem inventar conteúdo do processo | done |
| T-10 | Os seis diagramas de exemplo da skill passam no modo mais rigoroso, virando padrão de qualidade | done |
| T-11 | O manual da skill instrui a perguntar o que falta e a gerar pelo spec, não escrevendo XML à mão | done |
| T-12 | No editor é possível alterar nome, documentação, tipo do elemento e a condição de cada fluxo por um painel | AGUARDANDO VOCÊ — liberar 'python scripts/generate_editor_html.py' no .harness/harness.yaml (extra_allowed_commands) ou rodar o comando no terminal do usuario: editor.html e build output do gerador e precisa ser regerado para as tarefas do editor (T-12 a T-16) |
| T-13 | O editor mostra os problemas do diagrama numa lista clicável que leva ao elemento com defeito | AGUARDANDO VOCÊ — mesma acao de T-12: liberar 'python scripts/generate_editor_html.py' no .harness/harness.yaml ou rodar o comando no terminal do usuario para regerar editor.html |
| T-14 | O editor entregue num projeto se atualiza sozinho quando a skill evolui, sem apagar ajustes locais | AGUARDANDO VOCÊ — mesma acao de T-12: liberar 'python scripts/generate_editor_html.py' no .harness/harness.yaml ou rodar o comando no terminal do usuario para regerar editor.html (as metas de versao/hash so existem no gerador) |
| T-15 | O editor permite alinhar e distribuir elementos selecionados e gerar um PDF do diagrama | AGUARDANDO VOCÊ — mesma acao de T-12: liberar 'python scripts/generate_editor_html.py' no .harness/harness.yaml ou rodar o comando no terminal do usuario para regerar editor.html |
| T-16 | O editor abre e renderiza o diagrama em máquina sem internet | AGUARDANDO VOCÊ — duas acoes humanas: (1) colocar os arquivos do bpmn-js@17 em assets/vendor/ (bpmn-modeler.production.min.js, diagram-js.css, bpmn.css e a fonte bpmn.woff) - o runtime floor bloqueia download pela rede, conforme o unknown registrado no spec; (2) liberar 'python scripts/generate_editor_html.py' para regerar editor.html |

## Última atualização

<!-- harness:auto -->
- 2026-09-09T10:40:16.361153+00:00 — T-02 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-02.json
- 2026-09-09T10:42:23.075045+00:00 — T-03 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-03.json
- 2026-09-09T10:45:03.508288+00:00 — T-04 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-04.json
- 2026-09-09T10:47:51.397634+00:00 — T-05 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-05.json
- 2026-09-09T10:50:19.444145+00:00 — T-06 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-06.json
- 2026-09-09T10:51:54.113286+00:00 — T-07 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-07.json
- 2026-09-09T10:53:03.489460+00:00 — T-08 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-08.json
- 2026-09-09T10:54:49.399568+00:00 — T-09 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-09.json
- 2026-09-09T10:59:03.216029+00:00 — T-10 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-10.json
- 2026-09-09T11:02:33.019099+00:00 — T-11 verificado (exit_code 0) — .harness/evidence/bpmn-skill-upgrade/T-11.json
<!-- /harness:auto -->


_(vazio — preenchido pelo agente durante a sessão)_
