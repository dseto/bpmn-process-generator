# Decisões do projeto

Append-only. Escrito por `harness decide` — não edite entradas antigas;
mudou de ideia, registre uma decisão nova que supersede a anterior.

## D-001 — Protecao de editor.html editado localmente fica em T-14 (2026-09-09)
Decisão: T-03 testa o comportamento atual: copy_editor_if_needed reescreve editor.html no projeto embutindo o diagrama gerado como preset default
Porquê: commit 6d0de91 mudou a funcao para sempre reescrever e apontar o editor ao diagrama gerado; preservar ajuste local do editor e o escopo declarado de T-14, entao duplicar essa regra em T-03 criaria dois contratos concorrentes sobre o mesmo arquivo

## D-002 — T-16 entrega o mecanismo de modo offline, nao o estado offline ativo (2026-09-09)
Decisão: editor.html continua sendo construido em modo CDN; a vendorizacao liga quando alguem colocar os arquivos do bpmn-js em assets/vendor/ e rodar o gerador. O editor declara o modo em <meta name=bpmn-editor-assets> e o teste assere os dois ramos
Porquê: os binarios do bpmn-js nao podem ser baixados daqui (runtime floor bloqueia rede) - isso estava registrado como unknown no spec aprovado, e o usuario escolheu explicitamente 'mecanismo agora, assets depois' quando perguntado. A verificacao cega apontou com razao que a promessa literal da tarefa (abrir sem internet) so se cumpre depois dessa acao humana
