# Lições — fricções observadas

Append-only. Escrito por `harness lesson`. Quem fecha um item é o HUMANO,
revisando em cadência própria — o agente anota, não aplica.
- [ ] editor.html e build output de scripts/generate_editor_html.py, mas o comando de build nao entrou na superficie do contrato; 4 tarefas (T-12 a T-15) ficaram bloqueadas esperando acao humana depois do codigo pronto → no /harness-creator:plan, quando o contrato tocar um arquivo GERADO, declarar o comando que o regenera junto do verify_cmd (ou como extra_allowed_commands) na hora da compilacao, nao depois
- [ ] os verify_cmd do contrato cobriam so os arquivos de teste novos; tests/test_bpmn_tool.py (pre-existente) quebrou com a reescrita do example-broken.bpmn e so a verificacao cega pegou, ja com tudo 'fechado' → quando o contrato altera um artefato COMPARTILHADO (fixture, exemplo canonico, modulo usado por testes antigos), declarar tambem a suite completa como verify_cmd de pelo menos uma tarefa - rodar so os arquivos novos esconde regressao nos antigos
