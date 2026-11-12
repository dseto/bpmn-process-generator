# Plano de Melhorias do Editor BPMN

Documento de análise e proposta para o `editor.html` do gerador de processos BPMN. Objetivo: tornar o editor mais completo, intuitivo e fácil de usar, com uma experiência bem superior à atual.

- **Data da análise:** 2026-11-11
- **Escopo:** `editor.html` (gerado por `scripts/generate_editor_html.py`), `assets/bpmn-editor-template.html`, painel de propriedades, validação, exportação e fluxo de abertura/salvamento.
- **Fora do escopo:** geração de BPMN a partir de spec (`bpmn_build.py`), linter em Python (`lint_rules.py`) e a skill em si, exceto onde o editor depende deles.

---

## 1. Resumo executivo

O editor já tem uma base sólida: bpmn-js 17, painel de propriedades, validação embutida, salvamento direto no disco via File System Access API, exportação SVG/PNG/PDF e modo offline opcional.

Os problemas mais graves não são de funcionalidade ausente, e sim de **confiabilidade** e **usabilidade**:

1. Alguns atalhos de teclado se comportam de forma errada (desfazem duas vezes, ou desfazem a ação de outro elemento enquanto o usuário digita).
2. Formatação de fonte (tamanho, negrito, itálico) não é gravada no arquivo `.bpmn`; é perdida ao reabrir.
3. Não há proteção contra fechar a aba com alterações não salvas.
4. A barra de ferramentas tem 30 controles sem agrupamento claro, sem rótulos acessíveis e com mistura de idiomas.
5. A validação embutida cobre apenas 6 das cerca de 36 regras do linter e só roda quando o usuário clica.

Recomendação: **resolver a Fase 1 (confiabilidade) antes de qualquer funcionalidade nova**, porque hoje o usuário pode perder trabalho sem perceber.

---

## 2. Diagnóstico

### 2.1 Método

- Leitura do código-fonte do gerador e do template.
- Execução do editor em servidor local, carregando o preset `06-bus-boarding-process.bpmn` (4 raias, 111 elementos).
- Testes de comportamento com JavaScript injetado no navegador, além de capturas de tela em 1440 px e 800 px de largura.

Cada achado abaixo indica se foi **verificado no navegador** ou apenas **identificado por leitura de código**.

### 2.2 Defeitos de confiabilidade

| # | Problema | Como foi verificado | Impacto para o usuário |
|---|---|---|---|
| B1 | Um único `Ctrl+Z` desfaz **duas** ações | Verificado: a pilha de comandos caiu de 2 para 0 com uma tecla | O usuário perde uma alteração que não queria desfazer |
| B2 | `Ctrl+Z` com foco no campo "Nome" desfaz a edição de **outro** elemento, e o texto digitado continua no campo | Verificado: o campo ficou com `PASSO-1XYZ` enquanto `PASSO-2` (outro elemento) foi revertido | Corrupção silenciosa de dados; o painel mostra valores que não batem com o canvas |
| B3 | Tamanho da fonte, negrito e itálico não são gravados no `.bpmn` | Verificado: o XML salvo não contém nenhuma informação de fonte | Toda formatação some ao reabrir o arquivo. Ferramenta de fonte existe, mas não cumpre o que promete |
| B4 | Negrito/itálico/tamanho ficam fora do histórico de desfazer e não marcam o diagrama como "não salvo" | Verificado: após aplicar negrito, `canUndo` continua igual e o título não muda | Usuário não sabe que tem alterações pendentes |
| B5 | Fechar a aba ou recarregar a página com alterações não salvas não avisa nada | Verificado: não há handler de `beforeunload` | Perda total de trabalho não salvo |
| B6 | Editor entregue ao projeto carrega o diagrama embutido no HTML antes do arquivo em disco; um salvamento posterior pode sobrescrever uma versão mais nova | Identificado por leitura de código (`initEditor`, `generate_editor_html.py`) | Risco de sobrescrever edição feita em outro lugar. Não reproduzido |

### 2.3 Defeitos de usabilidade menores

- O seletor **"Tipo do elemento"** aparece também para eventos e raias, com opções de tarefa e gateway, e não mostra o tipo atual do elemento.
- Paleta de criação e menus de contexto do bpmn-js estão em **inglês** ("Create task", "Activate lasso tool") dentro de uma interface em português.
- Botão **"Centralizar"** faz alinhamento pelo centro horizontal, mas o nome sugere centro do diagrama. Não há alinhamento pelo topo, base, direita ou centro vertical.
- Propriedades só são aplicadas ao sair do campo (evento `change`), não ao digitar. Quem digita e clica em "Salvar" logo em seguida pode não ver o valor refletido.
- Diagrama de 4 raias abre com zoom de 18%, ilegível.
- Cores são `div` sem suporte de teclado e sem nome acessível.
- Nenhum `aria-label` na barra de ferramentas.

### 2.4 Lacunas de funcionalidade

- Validação com 6 regras, executada só ao clicar, sem marcação visual no canvas.
- Sem auto-layout no editor (existe só no Python).
- Sem importar ou exportar o spec JSON, que é a fonte de entrada da skill.
- Sem comentários de revisão por elemento.
- Sem atalho de ajuda com a lista de teclas.
- Tela inicial mostra só um evento de início, sem modelos.
- Sem minimapa.

### 2.5 Dívida técnica

- O editor inteiro vive dentro de uma f-string Python de cerca de 1.800 linhas, com chaves duplicadas (`{{ }}`). Isso dificulta leitura, revisão e teste.
- Os testes atuais (`tests/test_editor_*.py`) verificam o HTML por expressão regular. Não há teste de comportamento no navegador, por isso os bugs B1 e B2 passaram despercebidos.
- `assets/bpmn-editor-template.html` (636 linhas) duplica parte da interface, mas sem painel de propriedades nem validação. Hoje são duas versões divergentes.
- Dependências de plugins adicionais (minimapa, por exemplo) precisam de verificação de compatibilidade com o modo de arquivo único e com o modo offline.

---

## 3. Proposta de melhorias

### Fase 0 — Base técnica (pré-requisito)

Objetivo: tornar o editor testável e fácil de evoluir, sem mudar o comportamento visível.

- **F0.1** Mover o código do editor para arquivos-fonte reais (`assets/editor/editor.html`, `editor.js`, `editor.css`). O gerador passa a só montar o artefato final a partir deles.
- **F0.2** Adicionar testes de comportamento no navegador (Playwright, já disponível no ambiente) cobrindo os bugs da Fase 1 antes de corrigi-los.
- **F0.3** Unificar o template standalone (`assets/bpmn-editor-template.html`) com o editor principal, usando a mesma base.

**Critério de aceite:** a suíte atual continua verde; os testes novos de B1 a B5 falham antes da correção e passam depois.

### Fase 1 — Não perder trabalho (prioridade máxima)

- **F1.1** Corrigir B1: um atalho dispara uma única ação de desfazer. Remover o listener duplicado ou deixar apenas o do bpmn-js.
- **F1.2** Corrigir B2: atalhos de edição (`Ctrl+Z`, `Ctrl+Y`, `Ctrl+B`, `Ctrl+I`, `Ctrl+S`) respeitam o foco. Quando o foco está em campo de texto, o atalho age no campo, não no canvas.
- **F1.3** Corrigir B3 e B4: gravar fonte no próprio DI do BPMN (`BPMNLabelStyle` / `dc:Font`), passar pelo `commandStack` e marcar o diagrama como alterado.
- **F1.4** Corrigir B5: aviso `beforeunload` enquanto houver alterações não salvas.
- **F1.5** Rascunho automático em `localStorage` (com try/catch e fallback), oferecendo recuperação ao reabrir o editor.
- **F1.6** Corrigir B6: ao abrir um arquivo do projeto, ler do disco antes de usar o snapshot embutido. Se o disco tiver versão mais nova, avisar.
- **F1.7** Aviso quando o arquivo aberto mudou no disco (por exemplo, a skill regenerou o diagrama enquanto o editor estava aberto), com opção de recarregar.
- **F1.8** Corrigir o seletor "Tipo do elemento": mostrar apenas tipos compatíveis com o elemento e exibir o tipo atual.

**Critério de aceite:** nenhum caso de perda silenciosa de dados nos testes de comportamento; fonte sobrevive a salvar e reabrir.

### Fase 2 — Mais intuitivo

#### 2.1 Barra de ferramentas e navegação
- **F2.1** Reorganizar a barra em grupos com menus: **Arquivo** (abrir, salvar, salvar como, novo, exportar), **Editar** (desfazer, refazer, buscar), **Exibir** (zoom, minimapa, ajuda). Manter na barra apenas as ações mais usadas.
- **F2.2** Barra contextual que aparece só com seleção: cor, fonte, alinhamento e tipo. Some quando não há seleção.
- **F2.3** Rodapé com porcentagem de zoom e botão de ajuste à seleção.
- **F2.4** Rótulos acessíveis (`aria-label`) e navegação por teclado em todos os controles, incluindo as cores.
- **F2.5** Layout responsivo testado em 1440 px, 1024 px e 800 px, sem quebra em três linhas.

#### 2.2 Idioma
- **F2.6** Traduzir para pt-BR a paleta de criação, menus de contexto e rótulos do bpmn-js, via módulo de tradução customizado.

#### 2.3 Alinhamento
- **F2.7** Adicionar alinhar pelo topo, base, direita e centro vertical.
- **F2.8** Adicionar distribuir vertical.
- **F2.9** Renomear "Centralizar" para deixar claro o eixo (por exemplo "Centro horizontal").

#### 2.4 Painel de propriedades
- **F2.10** Aplicar alterações de nome e documentação enquanto o usuário digita, com debounce curto.
- **F2.11** Campos específicos por tipo de elemento: evento de tempo (timer), evento de mensagem, evento de erro, tarefa com responsável, raia com nome.
- **F2.12** Quando nada está selecionado, mostrar propriedades do próprio processo (id, nome, versão).

#### 2.5 Descoberta e primeiro uso
- **F2.13** Tecla `?` abre a lista de atalhos.
- **F2.14** Tela inicial com modelos prontos (linear, com decisão, com raias, com laço) em vez de um evento de início isolado.
- **F2.15** Abertura de diagramas grandes com zoom que cabe à tela, e não em 18%. Minimapa para navegar.

**Critério de aceite:** teste de usabilidade com 3 a 5 pessoas que nunca usaram o editor, tarefa "criar um processo com uma decisão e exportar PNG", com conclusão sem ajuda externa.

### Fase 3 — Mais completo

#### 3.1 Validação viva
- **F3.1** Portar as regras restantes do linter para o editor, reutilizando os mesmos ids de regra. Hoje são 6 de cerca de 36.
- **F3.2** Validação roda automaticamente com pequeno atraso após cada alteração, sem precisar clicar.
- **F3.3** Marcar no canvas os elementos com problema (contorno colorido ou ícone), além da lista no painel.
- **F3.4** Botão "Corrigir" para os problemas que o comando `fix` já resolve de forma mecânica, com prévia.

#### 3.2 Integração com a skill
- **F3.5** Importar e exportar o spec JSON (`references/process-spec.md`). O usuário pode ajustar o processo pelo editor e gerar o spec de volta.
- **F3.6** Auto-layout no editor, reutilizando a lógica do `bpmn_tool layout`.
- **F3.7** Comentários de revisão por elemento, gravados como extensão do BPMN ou em arquivo lateral, sem alterar o processo.

#### 3.3 Análise e colaboração
- **F3.8** Diff visual entre duas versões do mesmo diagrama, destacando elementos adicionados, removidos e alterados.
- **F3.9** Simulação simples de fluxo (token percorrendo o diagrama), útil para validar caminhos e encontrar becos.
- **F3.10** Modo somente leitura gerado em HTML para envio a stakeholders, sem barra de ferramentas.

#### 3.4 Exportação
- **F3.11** PNG com escala escolhida (1x, 2x, 4x), fundo transparente opcional e cópia direta para a área de transferência.
- **F3.12** PDF paginado para diagramas grandes, com cabeçalho e número de página.

**Critério de aceite:** cada item tem teste de comportamento e pelo menos um exemplo do repositório como caso de referência.

---

## 4. Restrições e riscos

| Tema | Restrição | Tratamento proposto |
|---|---|---|
| Modo offline | Os binários do bpmn-js não podem ser baixados a partir do ambiente de desenvolvimento (rede bloqueada). A pasta `assets/vendor/` precisa ser preenchida manualmente | Toda funcionalidade nova deve funcionar nos dois modos (CDN e vendorizado). Testes cobrem os dois ramos |
| Plugins externos | Minimapa e outros módulos podem não ter build de arquivo único | Verificar cada plugin antes de adotar; preferir módulos que já vêm no pacote do bpmn-js |
| Compatibilidade de navegador | File System Access API existe só em Chromium | Manter fallback de download; documentar a limitação na interface |
| Compatibilidade com arquivos existentes | Diagramas já salvos pela skill não têm informação de fonte | Fonte ausente deve assumir o padrão atual (12 px, sem negrito), sem alterar o diagrama ao abrir |
| Tamanho do arquivo | O editor embute os presets e o bpmn-js; o tamanho cresce a cada módulo | Acompanhar tamanho em cada fase; teto de referência a definir |
| Harness do repositório | Mudanças em `scripts/generate_editor_html.py` e no editor exigem contrato e evidência | Abrir contrato por fase, com critérios de aceite acima |

---

## 5. Métricas de sucesso

- **Perda de dados:** zero casos reproduzíveis nos testes de comportamento da Fase 1.
- **Tempo para criar um processo simples com decisão e exportar PNG:** medir antes e depois com as mesmas 3 a 5 pessoas.
- **Cobertura de regras no editor:** de 6 para o total de regras do linter que se aplicam ao canvas.
- **Controles com rótulo acessível:** 100% da barra de ferramentas.
- **Tamanho do `editor.html` entregue:** registrar a cada fase, sem crescimento não justificado.

---

## 6. Questões em aberto

1. **Prioridade:** confirmar se a Fase 1 deve ser concluída antes de qualquer mudança visual.
2. **Comentários de revisão (F3.7):** gravar dentro do `.bpmn` (extensão própria) ou em arquivo lateral? Arquivo lateral é mais seguro para não quebrar ferramentas que leem o BPMN padrão.
3. **Spec JSON no editor (F3.5):** o usuário espera que o editor seja a fonte principal de edição, ou que a conversa com o assistente continue sendo a entrada principal?
4. **Idioma:** o editor deve ser só em português, ou manter a possibilidade de inglês?
5. **Modo offline:** a equipe vai preencher `assets/vendor/`? Sem isso, o editor continua dependendo de CDN.

---

## 7. Pendências relacionadas no repositório

- `harness reconcile` acusou 16 evidências obsoletas (T-01 a T-16) do contrato anterior. Resolver antes de abrir novo contrato, com `harness verify` em cada tarefa.
- Os testes de comportamento propostos em F0.2 ainda não existem; hoje a cobertura do editor é apenas estrutural.

---

## Apêndice A — Referências no código

| Assunto | Localização |
|---|---|
| Atalhos de teclado | `scripts/generate_editor_html.py` (listener `keydown`, perto da linha 1869) |
| Painel de propriedades | `scripts/generate_editor_html.py` (linhas 1010 a 1105) |
| Validação embutida | `scripts/generate_editor_html.py` (linhas 1114 a 1260) |
| Abertura e carga de arquivo | `scripts/generate_editor_html.py` (`loadXML`, perto da linha 1316; `initEditor`, perto da linha 1899) |
| Salvamento | `scripts/generate_editor_html.py` (`saveFile` e `saveFileAs`, perto das linhas 1368 e 1387) |
| Fonte por elemento | `scripts/generate_editor_html.py` (`applyAllElementFontStyles`, perto da linha 1488) |
| Cópia do editor para o projeto | `scripts/bpmn_tool.py` (`copy_editor_if_needed`, linha 431) |
| Modo offline | `scripts/generate_editor_html.py` (`head_assets`, linha 94) e `assets/vendor/README.md` |
| Template standalone | `assets/bpmn-editor-template.html` |
| Testes do editor | `tests/test_editor_features.py`, `tests/test_editor_offline.py`, `tests/test_editor_version.py`, `tests/test_generate_editor_html.py` |
