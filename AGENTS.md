# AGENTS.md — Diretrizes para Agentes

<!-- harness:begin -->
## Governança do Harness (gerado — edite .harness/harness.yaml e rode `harness compile`)

Política de aprovação: **auto**. Rede (WebFetch/WebSearch/curl)
sempre exige aprovação humana.

1. TDD recomendado (enforcement desligado nesta configuração).
2. **Orçamento (orientação)**: alvo de ~500,000 tokens
   por tarefa e 120 tool calls. O Claude Code não
   expõe contagem de tokens a hooks — este teto é disciplina, não enforcement;
   se a tarefa estourar muito, pare e replaneje com o humano.
3. **Artefatos temporários de verificação** (screenshots, dumps de rede,
   HTML de debug, JSON de resposta de API): salve SEMPRE em
   `.harness/scratch/` — única área liberada para arquivos que não pertencem
   a nenhuma tarefa do contrato. A pasta é auto-ignorada pelo git e apagável
   a qualquer momento; nunca referencie nada dela em código e nunca salve
   esses artefatos na raiz do repositório.
<!-- harness:end -->
