# assets/vendor — bpmn-js local (modo offline do editor)

Por padrão o `editor.html` carrega o bpmn-js do CDN da unpkg. Isso quebra em três situações reais: máquina sem internet, rede corporativa bloqueando o CDN, e diagrama aberto em `file://` num ambiente restrito. Nesses casos o editor abre como página em branco.

Colocando os arquivos do bpmn-js **aqui**, o gerador passa a **embutir** tudo dentro do `editor.html`, e o editor deixa de depender de rede — inclusive nas cópias distribuídas para os projetos.

## Arquivos esperados

| Arquivo | Origem (bpmn-js 17.0.0) |
|---|---|
| `bpmn-modeler.production.min.js` | `dist/bpmn-modeler.production.min.js` |
| `diagram-js.css` | `dist/assets/diagram-js.css` |
| `bpmn.css` | `dist/assets/bpmn-font/css/bpmn.css` |
| `bpmn.woff` (opcional, recomendado) | `dist/assets/bpmn-font/font/bpmn.woff` |

Os três primeiros são obrigatórios: **ou estão todos presentes, ou nenhum é usado**. Um diretório meio preenchido carregaria dois arquivos localmente e perderia o terceiro em silêncio, então o gerador prefere voltar inteiro para o CDN. A fonte é opcional; quando está aqui, ela é embutida como `data:` URI e os ícones dos elementos também funcionam offline.

## Como obter

Pelo npm, num diretório qualquer fora deste repositório:

```powershell
npm pack bpmn-js@17.0.0
```

Descompacte o `.tgz` e copie os quatro arquivos da tabela para cá. Baixar direto da unpkg (`https://unpkg.com/bpmn-js@17.0.0/dist/...`) pelo navegador também serve.

## Depois de copiar

```powershell
python scripts/generate_editor_html.py
```

A saída informa o modo (`offline (bpmn-js embutido)` ou `CDN (unpkg)`), e o próprio `editor.html` passa a declarar `<meta name="bpmn-editor-assets" content="vendored">`. Rode a suíte para confirmar:

```powershell
pytest tests/test_editor_offline.py -q
```

> Estes arquivos são de terceiros (bpmn-js, licença MIT). Versione-os apenas se a distribuição offline for um requisito do seu repositório — o `editor.html` gerado passa a ter cerca de 1,3 MB.
