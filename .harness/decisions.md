# Decisões do projeto

Append-only. Escrito por `harness decide` — não edite entradas antigas;
mudou de ideia, registre uma decisão nova que supersede a anterior.

## D-001 — Protecao de editor.html editado localmente fica em T-14 (2026-09-09)
Decisão: T-03 testa o comportamento atual: copy_editor_if_needed reescreve editor.html no projeto embutindo o diagrama gerado como preset default
Porquê: commit 6d0de91 mudou a funcao para sempre reescrever e apontar o editor ao diagrama gerado; preservar ajuste local do editor e o escopo declarado de T-14, entao duplicar essa regra em T-03 criaria dois contratos concorrentes sobre o mesmo arquivo
