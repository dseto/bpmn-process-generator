#!/usr/bin/env python3
"""
generate_editor_html.py
Generates the central editor.html in the root directory.
Includes File System Access API, Drag & Drop, Keyboard shortcuts, and embeds presets
so the editor works seamlessly under file:// protocol without CORS fetch blocks.

Enhanced with:
- Task resizing (CustomResizeModule)
- 90-degree orthogonal line routing (layoutConnection)
- Magnetic grid snapping (10px grid)
- Color palette (bioc coloring via modeling.setColor)
- Visual Undo/Redo history
- Zoom controls and canvas fit
- In-diagram SearchPad (Ctrl+F)
- High-resolution PNG and vector SVG exports
"""
import base64
import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Where a human can drop the bpmn-js distribution so the editor stops depending
# on the network. See assets/vendor/README.md.
VENDOR_DIR = ROOT_DIR / "assets" / "vendor"
VENDOR_JS = "bpmn-modeler.production.min.js"
VENDOR_DIAGRAM_CSS = "diagram-js.css"
VENDOR_BPMN_CSS = "bpmn.css"
VENDOR_FONT = "bpmn.woff"

CDN_BASE = "https://unpkg.com/bpmn-js@17.0.0/dist"

# Version of the editor handed to a project. Bump it whenever this generator
# changes: `bpmn_tool.copy_editor_if_needed` compares it against the copy already
# in the project and refreshes an older, untouched one (an edited copy is kept
# and reported instead -- see `was_edited_locally`).
EDITOR_VERSION = "1.2.0"

PRESET_FILES = {
    "06-bus-boarding-process.bpmn": ROOT_DIR / "tests" / "06-bus-boarding-process.bpmn",
    "04-incident-management.bpmn": ROOT_DIR / "tests" / "04-incident-management.bpmn",
    "03-order-fulfillment.bpmn": ROOT_DIR / "tests" / "03-order-fulfillment.bpmn",
    "02-credit-card-approval.bpmn": ROOT_DIR / "tests" / "02-credit-card-approval.bpmn",
    "01-user-onboarding.bpmn": ROOT_DIR / "tests" / "01-user-onboarding.bpmn",
    "05-document-revision-cycle.bpmn": ROOT_DIR / "tests" / "05-document-revision-cycle.bpmn",
    "example-complete.bpmn": ROOT_DIR / "references" / "example-complete.bpmn",
}

BLANK_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  id="Definitions_NewProcess"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_Novo" name="Novo Processo" isExecutable="false">
    <bpmn:startEvent id="Start_1" name="Início" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_Process_Novo">
    <bpmndi:BPMNPlane id="BPMNPlane_Process_Novo" bpmnElement="Process_Novo">
      <bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1">
        <omgdc:Bounds x="160" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""

presets_data = {"_blank": BLANK_TEMPLATE}
for name, path in PRESET_FILES.items():
    if path.exists():
        presets_data[name] = path.read_text(encoding="utf-8")
    else:
        print(f"[WARN] Preset file not found: {path}")

presets_json = json.dumps(presets_data, ensure_ascii=False)


def _embed_font(css, vendor_dir):
    """Replace the bpmn font URL with a data: URI, so no request leaves the page."""
    font = vendor_dir / VENDOR_FONT
    if not font.exists():
        return css
    encoded = base64.b64encode(font.read_bytes()).decode("ascii")
    return re.sub(
        r"url\(['\"]?[^)'\"]*bpmn\.woff[^)'\"]*['\"]?\)",
        f"url('data:font/woff;base64,{encoded}')",
        css,
    )


def head_assets(vendor_dir):
    """
    The <head> block that brings bpmn-js in.

    All three assets or none: a half-vendored directory would load two files
    locally and silently miss the third, which is worse than the CDN. The mode
    is stamped in a meta tag so the delivered editor says how it was built.
    """
    required = [vendor_dir / VENDOR_JS, vendor_dir / VENDOR_DIAGRAM_CSS, vendor_dir / VENDOR_BPMN_CSS]
    if all(path.exists() for path in required):
        script, diagram_css, bpmn_css = (path.read_text(encoding="utf-8") for path in required)
        bpmn_css = _embed_font(bpmn_css, vendor_dir)
        # A closing tag inside the bundle would end the script element early.
        script = script.replace("</script", r"<\/script")
        return (
            '<meta name="bpmn-editor-assets" content="vendored" />\n'
            "<!-- bpmn-js v17.0.0 (Modeler) embutido: o editor abre sem rede -->\n"
            f"<style>\n{diagram_css}\n{bpmn_css}\n</style>\n"
            f"<script>\n{script}\n</script>"
        )
    return (
        '<meta name="bpmn-editor-assets" content="cdn" />\n'
        "<!-- bpmn-js v17.0.0 (Modeler) -->\n"
        f'<link rel="stylesheet" href="{CDN_BASE}/assets/diagram-js.css" />\n'
        f'<link rel="stylesheet" href="{CDN_BASE}/assets/bpmn-font/css/bpmn.css" />\n'
        f'<script src="{CDN_BASE}/bpmn-modeler.production.min.js"></script>'
    )


def render_editor_html(vendor_dir=None):
    """Render the whole editor, embedding bpmn-js when it has been vendored."""
    assets = head_assets(VENDOR_DIR if vendor_dir is None else Path(vendor_dir))
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="bpmn-editor-version" content="{EDITOR_VERSION}" />
<meta name="bpmn-editor-hash" content="" />
<title>BPMN Editor Central</title>
{assets}

<style>
  :root {{
    --bg-header: #0f172a;
    --bg-header-border: #1e293b;
    --btn-primary: #2563eb;
    --btn-primary-hover: #1d4ed8;
    --btn-success: #16a34a;
    --btn-success-hover: #15803d;
    --btn-secondary: #334155;
    --btn-secondary-hover: #475569;
    --text-light: #f8fafc;
    --text-muted: #94a3b8;
  }}

  * {{ box-sizing: border-box; }}
  html, body {{
    height: 100%;
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}

  #app-header {{
    min-height: 48px;
    height: auto;
    background: var(--bg-header);
    border-bottom: 1px solid var(--bg-header-border);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    padding: 6px 12px;
    gap: 4px 6px;
    color: var(--text-light);
    user-select: none;
    overflow-x: auto;
    position: relative;
    z-index: 100;
    flex-shrink: 0;
  }}

  #app-header::-webkit-scrollbar {{
    height: 6px;
  }}
  #app-header::-webkit-scrollbar-track {{
    background: #0f172a;
  }}
  #app-header::-webkit-scrollbar-thumb {{
    background: #475569;
    border-radius: 3px;
  }}
  #app-header::-webkit-scrollbar-thumb:hover {{
    background: #64748b;
  }}

  .brand {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.3px;
    color: #38bdf8;
    margin-right: 4px;
    flex-shrink: 0;
  }}

  .brand svg {{
    width: 20px;
    height: 20px;
    fill: currentColor;
  }}

  .button-group {{
    display: flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
  }}

  .toolbar-sep {{
    width: 1px;
    height: 22px;
    background: rgba(255,255,255,0.12);
    margin: 0 2px;
    flex-shrink: 0;
  }}

  button, select {{
    background: var(--btn-secondary);
    color: var(--text-light);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s ease-in-out;
    white-space: nowrap;
    line-height: 1.2;
  }}

  button:hover {{
    background: var(--btn-secondary-hover);
  }}

  button:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
    pointer-events: none;
  }}

  button.btn-save {{
    background: var(--btn-success);
  }}
  button.btn-save:hover {{
    background: var(--btn-success-hover);
  }}

  button.btn-primary {{
    background: var(--btn-primary);
  }}
  button.btn-primary:hover {{
    background: var(--btn-primary-hover);
  }}

  button.btn-action {{
    background: #4338ca;
  }}
  button.btn-action:hover {{
    background: #3730a3;
  }}

  button.active {{
    background: #2563eb !important;
    color: #ffffff !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 0 6px rgba(56, 189, 248, 0.4);
  }}

  .btn-font-toggle {{
    font-weight: 700;
    min-width: 28px;
    justify-content: center;
  }}

  select {{
    padding-right: 24px;
    background-color: #1e293b;
    outline: none;
    font-size: 12px;
  }}

  /* Color Picker Palettes */
  .color-picker-group {{
    display: flex;
    align-items: center;
    gap: 4px;
    background: #1e293b;
    padding: 3px 6px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.08);
    flex-shrink: 0;
  }}

  .color-label {{
    font-size: 11px;
    color: var(--text-muted);
    margin-right: 2px;
  }}

  .color-dot {{
    width: 16px;
    height: 16px;
    border-radius: 50%;
    cursor: pointer;
    border: 2px solid rgba(255,255,255,0.25);
    transition: transform 0.15s ease, border-color 0.15s ease;
  }}
  .color-dot:hover {{
    transform: scale(1.3);
    border-color: #ffffff;
    box-shadow: 0 0 6px rgba(255,255,255,0.4);
  }}

  .file-badge {{
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    background: #1e293b;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-muted);
    border: 1px solid rgba(255,255,255,0.05);
    flex-shrink: 0;
  }}

  #current-filename {{
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: inline-block;
    vertical-align: middle;
  }}

  #preset-select {{
    max-width: 175px;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .file-badge strong {{
    color: var(--text-light);
    font-weight: 600;
  }}

  .status-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
  }}
  .status-dot.unsaved {{
    background: #f59e0b;
  }}

  #workspace {{
    flex: 1 1 auto;
    display: flex;
    min-height: 0;
    width: 100%;
  }}

  #canvas {{
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    background: #ffffff;
    position: relative;
  }}

  #properties-panel {{
    flex: 0 0 300px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    overflow-y: auto;
    background: #f8fafc;
    border-left: 1px solid #e2e8f0;
    font-size: 13px;
    color: #0f172a;
  }}
  #properties-panel.hidden {{
    display: none;
  }}
  #properties-panel h2 {{
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #475569;
  }}
  .prop-field {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .prop-field label {{
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
  }}
  .prop-field input[type="text"],
  .prop-field select,
  .prop-field textarea {{
    width: 100%;
    box-sizing: border-box;
    padding: 6px 8px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 13px;
    font-family: inherit;
    background: #ffffff;
    color: #0f172a;
  }}
  .prop-field input[readonly] {{
    background: #e2e8f0;
    color: #475569;
  }}
  .prop-field textarea {{
    resize: vertical;
    min-height: 64px;
  }}
  .prop-checkbox {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #334155;
  }}
  #prop-empty {{
    color: #64748b;
    line-height: 1.5;
  }}
  #prop-flow-fields.hidden,
  #prop-shape-fields.hidden,
  #prop-body.hidden {{
    display: none;
  }}

  #validation-section {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid #e2e8f0;
    padding-top: 12px;
  }}
  #validation-results {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .validation-finding {{
    text-align: left;
    padding: 8px 10px;
    border: 1px solid #e2e8f0;
    border-left-width: 4px;
    border-radius: 6px;
    background: #ffffff;
    font-size: 12px;
    line-height: 1.4;
    cursor: pointer;
    color: #0f172a;
  }}
  .validation-finding:hover {{
    background: #f1f5f9;
  }}
  .validation-finding.error {{
    border-left-color: #dc2626;
  }}
  .validation-finding.warn {{
    border-left-color: #f59e0b;
  }}
  .validation-finding .rule {{
    display: block;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748b;
  }}
  .validation-ok {{
    padding: 8px 10px;
    border-radius: 6px;
    background: #dcfce7;
    color: #166534;
    font-size: 12px;
  }}

  @media print {{
    @page {{
      size: landscape;
      margin: 10mm;
    }}
    #app-header,
    #properties-panel,
    #toast,
    #drop-overlay {{
      display: none !important;
    }}
    #workspace, #canvas {{
      width: 100%;
      height: auto;
    }}
  }}

  #error-banner {{
    display: none;
    position: fixed;
    top: 60px;
    left: 20px;
    right: 20px;
    background: #b91c1c;
    color: #ffffff;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 13px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    z-index: 2500;
    white-space: pre-wrap;
  }}

  #notice-banner {{
    position: fixed;
    top: 60px;
    right: 20px;
    max-width: 520px;
    z-index: 2400;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  #notice-banner .notice {{
    background: #1e3a5f;
    color: #ffffff;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    border-left: 4px solid #f59e0b;
  }}
  #notice-banner .notice-actions {{
    margin-top: 8px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  #notice-banner .notice-actions button {{
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.5);
    background: rgba(255,255,255,0.12);
    color: #ffffff;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
  }}

  #drop-overlay {{
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(4px);
    color: #fff;
    z-index: 2000;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 16px;
    font-size: 20px;
    font-weight: 600;
    border: 3px dashed #38bdf8;
    margin: 12px;
    border-radius: 12px;
  }}

  @media (max-width: 768px) {{
    .file-badge {{
      margin-left: 0;
    }}
    .toolbar-sep {{
      display: none;
    }}
  }}

  #toast {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #0f172a;
    color: #fff;
    border: 1px solid #38bdf8;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 13px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    z-index: 3000;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.2s ease-in-out;
    pointer-events: none;
  }}
  #toast.show {{
    opacity: 1;
    transform: translateY(0);
  }}
</style>
</head>
<body>

<header id="app-header">
  <div class="brand" title="BPMN Editor Central — Modelador Visual Interativo">
    <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
    BPMN Editor
  </div>

  <!-- Grupo Arquivo -->
  <div class="button-group">
    <button id="btn-open" class="btn-primary" title="Abrir arquivo .bpmn do computador (Ctrl+O)">
      📂 Abrir
    </button>
    <button id="btn-save" class="btn-save" title="Salvar diretamente no arquivo do disco (Ctrl+S)">
      💾 Salvar
    </button>
    <button id="btn-save-as" title="Salvar como novo arquivo ou download">
      📥 Salvar Como...
    </button>
    <button id="btn-new" title="Criar novo diagrama em branco">
      ➕ Novo
    </button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Histórico (Undo / Redo) -->
  <div class="button-group">
    <button id="btn-undo" title="Desfazer última ação (Ctrl+Z)" disabled>
      ↩️
    </button>
    <button id="btn-redo" title="Refazer ação (Ctrl+Y)" disabled>
      ↪️
    </button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Geometria & Roteamento -->
  <div class="button-group">
    <button id="btn-route-90" class="btn-action" title="Alinhar conexões selecionadas (ou todas) em ângulos ortogonais de 90°">
      📐 Curva 90°
    </button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Paleta de Cores -->
  <div class="color-picker-group" title="Selecione nós ou caixas e clique numa cor para personalizar">
    <span class="color-label">Cores:</span>
    <div class="color-dot" style="background:#ffffff;" data-fill="#ffffff" data-stroke="#22242a" title="Padrão (Branco)"></div>
    <div class="color-dot" style="background:#38bdf8;" data-fill="#e0f2fe" data-stroke="#0284c7" title="Azul"></div>
    <div class="color-dot" style="background:#4ade80;" data-fill="#dcfce7" data-stroke="#16a34a" title="Verde"></div>
    <div class="color-dot" style="background:#facc15;" data-fill="#fef9c3" data-stroke="#ca8a04" title="Amarelo"></div>
    <div class="color-dot" style="background:#f87171;" data-fill="#fee2e2" data-stroke="#dc2626" title="Vermelho"></div>
    <div class="color-dot" style="background:#c084fc;" data-fill="#f3e8ff" data-stroke="#9333ea" title="Roxo"></div>
    <div class="color-dot" style="background:#fb923c;" data-fill="#ffedd5" data-stroke="#ea580c" title="Laranja"></div>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Tipografia & Fonte -->
  <div class="button-group" title="Tipografia e estilo de fonte do diagrama">
    <span class="color-label">Fonte:</span>
    <select id="font-size-select" title="Alterar tamanho da fonte do diagrama">
      <option value="9px">9px</option>
      <option value="10px">10px</option>
      <option value="11px">11px</option>
      <option value="12px" selected>12px (Padrão)</option>
      <option value="13px">13px</option>
      <option value="14px">14px</option>
      <option value="16px">16px</option>
      <option value="18px">18px</option>
      <option value="20px">20px</option>
    </select>
    <button id="btn-font-bold" class="btn-font-toggle" title="Alternar Negrito (Ctrl+B)"><b>B</b></button>
    <button id="btn-font-italic" class="btn-font-toggle" title="Alternar Itálico (Ctrl+I)"><i>I</i></button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Alinhamento -->
  <div class="button-group">
    <button id="btn-align-left" title="Alinhar os elementos selecionados pela esquerda">
      ⬅️ Alinhar
    </button>
    <button id="btn-align-middle" title="Alinhar os elementos selecionados pelo centro horizontal">
      ↕️ Centralizar
    </button>
    <button id="btn-distribute-h" title="Distribuir os elementos selecionados com espaçamento igual">
      ↔️ Distribuir
    </button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Visualização & Zoom -->
  <div class="button-group">
    <button id="btn-props-toggle" title="Mostrar/ocultar o painel de propriedades">
      🧾 Propriedades
    </button>
    <button id="btn-search" title="Localizar elementos no diagrama (Ctrl+F)">
      🔍
    </button>
    <button id="btn-zoom-out" title="Diminuir zoom">
      ➖
    </button>
    <button id="btn-zoom-in" title="Aumentar zoom">
      ➕
    </button>
    <button id="btn-zoom-fit" title="Ajustar diagrama à tela">
      🎯
    </button>
    <button id="btn-zoom-reset" title="Zoom 100% (1:1)">
      1:1
    </button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Grupo Exportação Gráfica -->
  <div class="button-group">
    <button id="btn-export-svg" title="Exportar imagem vetorial (.svg)">
      🖼️ SVG
    </button>
    <button id="btn-export-png" title="Exportar imagem em alta resolução (.png)">
      📷 PNG
    </button>
    <button id="btn-export-pdf" title="Imprimir o diagrama (escolha &quot;Salvar como PDF&quot;)">
      🖨️ PDF
    </button>
  </div>

  <div class="toolbar-sep"></div>

  <!-- Seletor de Presets -->
  <div class="button-group">
    <!--PRESET_SELECT_START-->
    <select id="preset-select" title="Carregar um diagrama de teste ou exemplo integrado">
      <option value="">-- Exemplos / Testes --</option>
      <option value="06-bus-boarding-process.bpmn">06. Ônibus Completo (4 Raias)</option>
      <option value="04-incident-management.bpmn">04. Gestão de Incidentes (2 Raias)</option>
      <option value="03-order-fulfillment.bpmn">03. Atendimento de Pedido (AND Split/Join)</option>
      <option value="02-credit-card-approval.bpmn">02. Cartão de Crédito (XOR Gateway)</option>
      <option value="01-user-onboarding.bpmn">01. Onboarding Linear</option>
      <option value="05-document-revision-cycle.bpmn">05. Revisão de Documentos (Loop)</option>
      <option value="example-complete.bpmn">Exemplo Referência (Expense Approval)</option>
    </select>
    <!--PRESET_SELECT_END-->
  </div>

  <!-- Badge de Status do Arquivo -->
  <div class="file-badge">
    <div id="status-dot" class="status-dot" title="Arquivo sincronizado com o disco"></div>
    <span id="current-filename">Nenhum arquivo</span>
  </div>
</header>

<input type="file" id="file-input" accept=".bpmn,.xml" style="display:none" />

<div id="error-banner"></div>
<div id="notice-banner" role="status" aria-live="polite"></div>

<div id="workspace">
  <div id="canvas"></div>
  <aside id="properties-panel">
    <h2>Propriedades</h2>
    <div id="prop-empty">Selecione um elemento no diagrama para editar nome, documentação, tipo e — em conexões — a condição da decisão.</div>
    <div id="prop-body" class="hidden">
      <div class="prop-field">
        <label for="prop-id">Identificador</label>
        <input type="text" id="prop-id" readonly />
      </div>
      <div class="prop-field">
        <label for="prop-name">Nome</label>
        <input type="text" id="prop-name" placeholder="Verbo no infinitivo + objeto" />
      </div>
      <div class="prop-field">
        <label for="prop-documentation">Documentação</label>
        <textarea id="prop-documentation" placeholder="Detalhes, regras e observações desta etapa"></textarea>
      </div>
      <div id="prop-shape-fields">
        <div class="prop-field">
          <label for="prop-type">Tipo do elemento</label>
          <select id="prop-type">
            <option value="">(manter o tipo atual)</option>
            <option value="bpmn:Task">Tarefa genérica</option>
            <option value="bpmn:UserTask">Tarefa de pessoa (User Task)</option>
            <option value="bpmn:ServiceTask">Tarefa de sistema (Service Task)</option>
            <option value="bpmn:SendTask">Envio de mensagem (Send Task)</option>
            <option value="bpmn:ReceiveTask">Recebimento de mensagem (Receive Task)</option>
            <option value="bpmn:ManualTask">Tarefa manual</option>
            <option value="bpmn:BusinessRuleTask">Regra de negócio</option>
            <option value="bpmn:ExclusiveGateway">Decisão exclusiva (XOR)</option>
            <option value="bpmn:ParallelGateway">Paralelo (AND)</option>
            <option value="bpmn:InclusiveGateway">Inclusivo (OR)</option>
          </select>
        </div>
      </div>
      <div id="prop-flow-fields" class="hidden">
        <div class="prop-field">
          <label for="prop-condition">Condição da decisão</label>
          <input type="text" id="prop-condition" placeholder="ex.: valor &lt;= orcamento" />
        </div>
        <label class="prop-checkbox">
          <input type="checkbox" id="prop-default" />
          Fluxo padrão (quando nenhuma condição for atendida)
        </label>
      </div>
    </div>

    <div id="validation-section">
      <h2>Validação</h2>
      <button id="btn-validate" class="btn-action" title="Checar o diagrama contra as regras da skill">
        ✅ Validar diagrama
      </button>
      <div id="validation-results"></div>
    </div>
  </aside>
</div>

<div id="drop-overlay">
  <svg style="width:48px;height:48px;fill:#38bdf8;" viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
  <span>Solte o arquivo .bpmn aqui para abrir</span>
</div>

<div id="toast"></div>

<script>
  /*PRESETS_START*/
  const PRESETS = {presets_json};
  /*PRESETS_END*/
  let DEFAULT_DIAGRAM_NAME = "";
  let DEFAULT_DIAGRAM_XML = null;

  let currentFileHandle = null;
  let currentFileName = "diagrama.bpmn";
  let isDirty = false;
  let modeler = null;

  const errorBanner = document.getElementById('error-banner');
  const currentFileNameEl = document.getElementById('current-filename');
  const statusDot = document.getElementById('status-dot');
  const toast = document.getElementById('toast');
  const fileInput = document.getElementById('file-input');
  const presetSelect = document.getElementById('preset-select');
  const dropOverlay = document.getElementById('drop-overlay');
  const btnUndo = document.getElementById('btn-undo');
  const btnRedo = document.getElementById('btn-redo');
  const propertiesPanel = document.getElementById('properties-panel');
  const btnPropsToggle = document.getElementById('btn-props-toggle');
  const propEmpty = document.getElementById('prop-empty');
  const propBody = document.getElementById('prop-body');
  const propId = document.getElementById('prop-id');
  const propName = document.getElementById('prop-name');
  const propDocumentation = document.getElementById('prop-documentation');
  const propShapeFields = document.getElementById('prop-shape-fields');
  const propType = document.getElementById('prop-type');
  const propFlowFields = document.getElementById('prop-flow-fields');
  const propCondition = document.getElementById('prop-condition');
  const propDefault = document.getElementById('prop-default');
  const btnValidate = document.getElementById('btn-validate');
  const validationResults = document.getElementById('validation-results');
  const btnAlignLeft = document.getElementById('btn-align-left');
  const btnAlignMiddle = document.getElementById('btn-align-middle');
  const btnDistributeH = document.getElementById('btn-distribute-h');
  const btnExportPdf = document.getElementById('btn-export-pdf');
  const fontSizeSelect = document.getElementById('font-size-select');
  const btnFontBold = document.getElementById('btn-font-bold');
  const btnFontItalic = document.getElementById('btn-font-italic');

  let elementFontStyles = {{}};

  // Estado de sincronização com o disco (F1.5-F1.7)
  let diskUrl = null;            // URL relativa do arquivo quando lido via fetch (http/https)
  let lastDiskText = null;       // último conteúdo conhecido do arquivo em disco; null = sem referência
  let ignoredDiskText = null;    // versão do disco que o usuário já escolheu ignorar
  let diskCheckBusy = false;
  // `loadXML` mora no bloco que cria o modeler; os avisos globais chamam por este atalho.
  let loadXMLImpl = null;
  function loadDiagram(xml, name, handle, options) {{
    return loadXMLImpl(xml, name, handle, options);
  }}
  let draftTimer = null;
  let draftRecoveryPending = false;
  const noticeBanner = document.getElementById('notice-banner');

  function showToast(msg) {{
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2800);
  }}

  function showError(err) {{
    errorBanner.style.display = 'block';
    errorBanner.textContent = 'Erro ao processar diagrama: ' + (err && err.message ? err.message : err);
  }}

  function clearError() {{
    errorBanner.style.display = 'none';
    errorBanner.textContent = '';
  }}

  // Aviso do navegador ao fechar/recarregar: registrado SOMENTE enquanto houver
  // alterações não salvas (ver setFileState).
  function beforeUnloadHandler(e) {{
    e.preventDefault();
    e.returnValue = '';
    return '';
  }}

  function setFileState(name, handle = null, dirty = false) {{
    currentFileName = name;
    currentFileHandle = handle;
    isDirty = dirty;
    if (dirty) {{
      window.addEventListener('beforeunload', beforeUnloadHandler);
    }} else {{
      window.removeEventListener('beforeunload', beforeUnloadHandler);
      cancelDraftSave();
    }}
    currentFileNameEl.textContent = name + (dirty ? ' *' : '');
    document.title = (dirty ? '● ' : '') + name + ' — BPMN Editor';
    if (dirty) {{
      statusDot.classList.add('unsaved');
      statusDot.title = 'Modificações não salvas';
    }} else {{
      statusDot.classList.remove('unsaved');
      statusDot.title = handle ? 'Arquivo salvo e sincronizado com o disco' : 'Diagrama sem alterações';
    }}
  }}

  function updateUndoRedoState() {{
    if (!modeler) return;
    try {{
      const cs = modeler.get('commandStack');
      btnUndo.disabled = !cs.canUndo();
      btnRedo.disabled = !cs.canRedo();
    }} catch (e) {{}}
  }}

  // ---------------------------------------------------------------------
  // Avisos não bloqueantes (banners com ações). Substituem confirm() onde a
  // decisão do usuário não pode travar o fluxo (rascunho, arquivo mudou no disco).
  // ---------------------------------------------------------------------
  function hideNotice(id) {{
    const el = document.getElementById('notice-' + id);
    if (el) el.remove();
  }}

  function showNotice(id, message, actions, closable = true) {{
    hideNotice(id);
    const box = document.createElement('div');
    box.className = 'notice';
    box.id = 'notice-' + id;
    const text = document.createElement('div');
    text.className = 'notice-text';
    text.textContent = message;
    box.appendChild(text);
    const bar = document.createElement('div');
    bar.className = 'notice-actions';
    (actions || []).concat(closable ? [{{ label: 'Fechar aviso', handler: null }}] : []).forEach(action => {{
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = action.label;
      btn.addEventListener('click', () => {{
        hideNotice(id);
        if (action.handler) action.handler();
      }});
      bar.appendChild(btn);
    }});
    box.appendChild(bar);
    noticeBanner.appendChild(box);
  }}

  // ---------------------------------------------------------------------
  // Rascunho automático (localStorage). Tudo em try/catch: modo privado, cota
  // cheia ou storage bloqueado nunca podem quebrar a edição.
  // ---------------------------------------------------------------------
  function draftKey(name) {{
    return 'bpmn-editor-draft:' + window.location.pathname + '::' + (name || currentFileName);
  }}

  function readDraft(name) {{
    try {{
      const raw = window.localStorage.getItem(draftKey(name));
      const draft = raw ? JSON.parse(raw) : null;
      return draft && typeof draft.xml === 'string' ? draft : null;
    }} catch (e) {{
      return null;
    }}
  }}

  function writeDraft(xml) {{
    try {{
      window.localStorage.setItem(draftKey(), JSON.stringify({{
        xml: xml, name: currentFileName, savedAt: Date.now()
      }}));
      return true;
    }} catch (e) {{
      return false;
    }}
  }}

  function clearDraft(name) {{
    try {{
      window.localStorage.removeItem(draftKey(name));
    }} catch (e) {{}}
  }}

  function cancelDraftSave() {{
    if (draftTimer) {{
      clearTimeout(draftTimer);
      draftTimer = null;
    }}
  }}

  function scheduleDraftSave() {{
    cancelDraftSave();
    draftTimer = setTimeout(async () => {{
      draftTimer = null;
      // Enquanto a oferta de recuperação está pendente, o rascunho antigo não é sobrescrito.
      if (!isDirty || !modeler || draftRecoveryPending) return;
      try {{
        const {{ xml }} = await modeler.saveXML({{ format: true }});
        if (isDirty && !draftRecoveryPending) writeDraft(xml);
      }} catch (e) {{}}
    }}, 400);
  }}

  function offerDraftRecovery() {{
    const draft = readDraft();
    if (!draft) return;
    draftRecoveryPending = true;
    const when = new Date(draft.savedAt || Date.now()).toLocaleString();
    showNotice('draft',
      `Há um rascunho não salvo de '${{currentFileName}}' (${{when}}). Deseja recuperá-lo?`,
      [
        {{ label: 'Recuperar rascunho', handler: async () => {{
          draftRecoveryPending = false;
          await loadDiagram(draft.xml, currentFileName, currentFileHandle, {{ keepDiskRef: true }});
          setFileState(currentFileName, currentFileHandle, true);
          scheduleDraftSave();
        }} }},
        {{ label: 'Descartar rascunho', handler: () => {{
          draftRecoveryPending = false;
          clearDraft();
        }} }}
      ], false);
  }}

  // ---------------------------------------------------------------------
  // Arquivo em disco: leitura, detecção de mudança externa e proteção contra
  // sobrescrita silenciosa.
  // ---------------------------------------------------------------------
  function normalizeXmlText(text) {{
    return String(text || '').replace(/\\r\\n/g, '\\n').trim();
  }}

  async function fetchDiskText(url) {{
    try {{
      const res = await fetch(url, {{ cache: 'no-store' }});
      return res.ok ? await res.text() : null;
    }} catch (e) {{
      return null;
    }}
  }}

  async function readDiskText() {{
    if (currentFileHandle && currentFileHandle.getFile) {{
      const file = await currentFileHandle.getFile();
      return await file.text();
    }}
    if (diskUrl) return await fetchDiskText(diskUrl);
    return null;
  }}

  async function reloadFromDisk(text) {{
    hideNotice('disk-changed');
    clearDraft();
    await loadDiagram(text, currentFileName, currentFileHandle, {{ fromDisk: true, url: diskUrl }});
  }}

  async function checkDiskChange() {{
    if (diskCheckBusy || lastDiskText === null || !modeler) return;
    if (!currentFileHandle && !diskUrl) return;
    diskCheckBusy = true;
    try {{
      const text = await readDiskText();
      if (text !== null && text !== lastDiskText && text !== ignoredDiskText) {{
        showNotice('disk-changed',
          `O arquivo '${{currentFileName}}' foi alterado no disco enquanto o editor estava aberto` +
          (isDirty ? ' e há alterações não salvas aqui.' : '.'),
          [
            {{ label: 'Recarregar do disco', handler: async () => {{
              if (isDirty && !confirm('Recarregar do disco descarta as alterações não salvas. Continuar?')) {{
                ignoredDiskText = null;
                return;
              }}
              await reloadFromDisk(text);
            }} }},
            {{ label: 'Manter minha versão', handler: () => {{ ignoredDiskText = text; }} }}
          ]);
      }}
    }} catch (e) {{
      // Sem permissão/arquivo indisponível: não há o que comparar.
    }} finally {{
      diskCheckBusy = false;
    }}
  }}

  // Antes de gravar num arquivo já aberto, confere se o disco ainda é o que foi lido.
  async function confirmOverwriteIfDiskChanged() {{
    if (lastDiskText === null) return true;
    let text = null;
    try {{
      text = await readDiskText();
    }} catch (e) {{
      return true;
    }}
    if (text === null || text === lastDiskText) return true;
    return confirm(`O arquivo '${{currentFileName}}' foi alterado no disco depois de aberto neste editor. ` +
      'Salvar agora vai SOBRESCREVER essa versão mais nova. Sobrescrever mesmo assim?');
  }}

  // Pergunta antes de qualquer ação que descartaria alterações não salvas.
  function confirmDiscardIfDirty(message) {{
    if (!isDirty) return true;
    return confirm(message);
  }}

  window.addEventListener('focus', () => {{ checkDiskChange(); }});
  document.addEventListener('visibilitychange', () => {{
    if (document.visibilityState === 'visible') checkDiskChange();
  }});
  setInterval(() => {{ checkDiskChange(); }}, 5000);

  // Módulo de regras customizadas para permitir redimensionamento de tarefas (Task Resize)
  const CustomResizeModule = {{
    __init__: ['customResizeRules'],
    customResizeRules: ['type', function(eventBus) {{
      function canResizeTask(context) {{
        if (!context) return;
        const shape = context.shape;
        if (!shape) return;
        const type = shape.type;
        if (type && (type.indexOf('Task') !== -1 || type === 'bpmn:Activity' || type === 'bpmn:CallActivity')) {{
          const newBounds = context.newBounds;
          if (!newBounds) return true;
          return newBounds.width >= 70 && newBounds.height >= 50;
        }}
      }}

      // Prioridade 1500 executa antes da regra padrão do bpmn-js (prioridade 1000)
      eventBus.on('commandStack.shape.resize.canExecute', 1500, function(event) {{
        return canResizeTask(event.context);
      }});

      eventBus.on('shape.resize', 1500, function(context) {{
        return canResizeTask(context);
      }});
    }}]
  }};

  // ---------------------------------------------------------------------
  // Fonte gravada no DI do BPMN: bpmndi:BPMNLabel -> bpmndi:BPMNLabelStyle ->
  // dc:Font. A alteração passa pelo commandStack ('element.setFontStyle'),
  // então desfazer/refazer e o estado "não salvo" funcionam, e o estilo
  // sobrevive a salvar/reabrir. `elementFontStyles` é apenas o espelho,
  // derivado do DI, usado para pintar o CSS (ver applyAllElementFontStyles).
  // Sem informação de fonte vale o padrão: 12 px, sem negrito/itálico.
  // ---------------------------------------------------------------------
  const FONT_DEFAULT_SIZE = 12;

  // No bpmn-js 17 o DI mora no elemento do diagrama (`element.di`); ler `businessObject.di` lança erro.
  function diOf(element) {{
    return (element && element.di) || null;
  }}

  function isStyleableDi(di) {{
    return !!di && typeof di.$instanceOf === 'function' &&
      (di.$instanceOf('bpmndi:BPMNShape') || di.$instanceOf('bpmndi:BPMNEdge'));
  }}

  function fontOfElement(element) {{
    const di = diOf(element);
    const font = isStyleableDi(di) && di.label && di.label.labelStyle && di.label.labelStyle.font;
    return {{
      size: (font && Number(font.size) > 0) ? Number(font.size) : FONT_DEFAULT_SIZE,
      isBold: !!(font && font.isBold),
      isItalic: !!(font && font.isItalic)
    }};
  }}

  function isDefaultFont(font) {{
    return font.size === FONT_DEFAULT_SIZE && !font.isBold && !font.isItalic;
  }}

  function diagramOfDi(di) {{
    let node = di;
    while (node && !(typeof node.$instanceOf === 'function' && node.$instanceOf('bpmndi:BPMNDiagram'))) {{
      node = node.$parent;
    }}
    return node || null;
  }}

  function sameFont(style, font) {{
    const f = style && style.font;
    return !!f && !f.name && (Number(f.size) || FONT_DEFAULT_SIZE) === font.size &&
      !!f.isBold === font.isBold && !!f.isItalic === font.isItalic;
  }}

  function styleIsReferenced(diagram, style) {{
    const plane = diagram.plane;
    return !!plane && (plane.planeElement || []).some(di => di.label && di.label.labelStyle === style);
  }}

  // Comando único (um desfazer) que troca a fonte de vários elementos.
  function SetFontStyleHandler(moddle) {{
    this._moddle = moddle;
  }}
  SetFontStyleHandler.$inject = ['moddle'];

  SetFontStyleHandler.prototype.execute = function(context) {{
    const moddle = this._moddle;
    const labels = [];
    const diagrams = [];
    const touched = [];
    const candidates = [];

    context.changes.forEach(change => {{
      const di = diOf(change.element);
      if (!isStyleableDi(di)) return;
      const diagram = diagramOfDi(di);
      if (!diagram) return;
      const styles = diagram.get('labelStyle');
      if (!diagrams.some(d => d.diagram === diagram)) {{
        diagrams.push({{ diagram: diagram, styles: styles.slice() }});
      }}

      const oldLabel = di.label;
      labels.push({{ di: di, label: oldLabel }});
      if (oldLabel && oldLabel.labelStyle) candidates.push({{ diagram: diagram, style: oldLabel.labelStyle }});

      let style;
      if (!isDefaultFont(change.font)) {{
        style = styles.find(s => sameFont(s, change.font));
        if (!style) {{
          style = moddle.create('bpmndi:BPMNLabelStyle', {{
            font: moddle.create('dc:Font', {{
              size: change.font.size,
              isBold: change.font.isBold,
              isItalic: change.font.isItalic
            }})
          }});
          style.id = moddle.ids.nextPrefixed('LabelStyle_', style);
          styles.push(style);
        }}
      }}

      const attrs = {{}};
      if (oldLabel && oldLabel.bounds) attrs.bounds = oldLabel.bounds;
      if (style) attrs.labelStyle = style;
      di.set('label', (attrs.bounds || attrs.labelStyle) ? moddle.create('bpmndi:BPMNLabel', attrs) : undefined);
      touched.push(change.element);
    }});

    // Estilos que ficaram sem uso saem do diagrama (só os que este comando liberou).
    candidates.forEach(c => {{
      const styles = c.diagram.get('labelStyle');
      const idx = styles.indexOf(c.style);
      if (idx !== -1 && !styleIsReferenced(c.diagram, c.style)) styles.splice(idx, 1);
    }});

    context.snapshot = {{ labels: labels, diagrams: diagrams }};
    return touched;
  }};

  SetFontStyleHandler.prototype.revert = function(context) {{
    const snapshot = context.snapshot;
    const touched = [];
    snapshot.labels.forEach(entry => {{
      entry.di.set('label', entry.label);
    }});
    snapshot.diagrams.forEach(entry => {{
      const styles = entry.diagram.get('labelStyle');
      styles.splice(0, styles.length);
      entry.styles.forEach(s => styles.push(s));
    }});
    context.changes.forEach(change => touched.push(change.element));
    return touched;
  }};

  // Registra o comando no commandStack (módulo adicional passado ao BpmnJS).
  function FontStyleCommands(commandStack) {{
    commandStack.registerHandler('element.setFontStyle', SetFontStyleHandler);
  }}
  FontStyleCommands.$inject = ['commandStack'];
  const FontStyleModule = {{
    __init__: ['fontStyleCommands'],
    fontStyleCommands: ['type', FontStyleCommands]
  }};

  // Espelho derivado do DI: só elementos com fonte diferente do padrão.
  function refreshFontStylesFromDiagram() {{
    const mirror = {{}};
    try {{
      modeler.get('elementRegistry').forEach(el => {{
        if (el.labelTarget) return;
        const font = fontOfElement(el);
        if (isDefaultFont(font)) return;
        mirror[el.id] = {{ fontSize: font.size + 'px', isBold: font.isBold, isItalic: font.isItalic }};
      }});
    }} catch (e) {{}}
    elementFontStyles = mirror;
  }}

  // Aplica `change(fontAtual)` a cada elemento selecionado, num único comando.
  function applyFontChange(selection, change) {{
    const changes = selection
      .filter(el => isStyleableDi(diOf(el)))
      .map(el => ({{ element: el, font: change(fontOfElement(el)), before: fontOfElement(el) }}))
    .filter(c => c.font.size !== c.before.size || c.font.isBold !== c.before.isBold || c.font.isItalic !== c.before.isItalic);
  if (changes.length === 0) return 0;
    modeler.get('commandStack').execute('element.setFontStyle', {{ changes: changes }});
    return changes.length;
  }}

  if (typeof BpmnJS === 'undefined') {{
    showError('Não foi possível carregar a biblioteca bpmn-js do CDN. Verifique sua conexão com a internet.');
  }} else {{
    modeler = new BpmnJS({{
      container: '#canvas',
      keyboard: {{ bindTo: document }},
      gridSnapping: {{ active: true }},
      additionalModules: [
        CustomResizeModule,
        FontStyleModule
      ]
    }});

    // Atualiza estado de alteração e botões de undo/redo
    modeler.on('commandStack.changed', () => {{
      if (!isDirty) setFileState(currentFileName, currentFileHandle, true);
      updateUndoRedoState();
      applyAllElementFontStyles();
      updateFontToolbarFromSelection(getSelectedElements());
      scheduleDraftSave();
    }});

    // Atualiza controles de fonte na toolbar quando a seleção de elementos muda
    modeler.on('selection.changed', (e) => {{
      updateFontToolbarFromSelection(getSelectedElements());
      updatePropertiesPanel(e.newSelection || []);
    }});

    // Assegura roteamento ortogonal em 90° para novas conexões criadas no canvas
    try {{
      modeler.get('eventBus').on('commandStack.connection.create.postExecuted', (event) => {{
        const conn = event.context && event.context.connection;
        if (conn && conn.type === 'bpmn:SequenceFlow') {{
          try {{ modeler.get('modeling').layoutConnection(conn); }} catch (e) {{}}
        }}
      }});
    }} catch (e) {{}}

    // Converte automaticamente conexões diagonais legadas para curvas ortogonais de 90°
    function enforceOrthogonalConnections() {{
      try {{
        const elementRegistry = modeler.get('elementRegistry');
        const modeling = modeler.get('modeling');
        const conns = elementRegistry.filter(el => {{
          if (!el.waypoints || el.waypoints.length !== 2) return false;
          const p1 = el.waypoints[0];
          const p2 = el.waypoints[1];
          return Math.abs(p1.x - p2.x) > 5 && Math.abs(p1.y - p2.y) > 5;
        }});
        if (conns.length > 0) {{
          conns.forEach(conn => {{
            try {{ modeling.layoutConnection(conn); }} catch (e) {{}}
          }});
        }}
      }} catch (e) {{}}
    }}

    // ---------------------------------------------------------------------
    // Painel de propriedades: nome, documentação, tipo e, em conexões, a
    // condição da decisão. Tudo passa pelo `modeling`/`bpmnReplace` do
    // bpmn-js, e não pelo XML, para que undo/redo e o estado "não salvo"
    // continuem funcionando como em qualquer outra edição do canvas.
    // ---------------------------------------------------------------------
    function isFlowConnection(element) {{
      return !!element && element.type === 'bpmn:SequenceFlow';
    }}

    const TYPE_OPTIONS = Array.from(propType.options)
      .filter(o => o.value)
      .map(o => ({{ value: o.value, label: o.textContent }}));
    const TYPE_GROUPS = [
      {{
        members: ['bpmn:Task', 'bpmn:UserTask', 'bpmn:ServiceTask', 'bpmn:SendTask', 'bpmn:ReceiveTask',
                  'bpmn:ManualTask', 'bpmn:BusinessRuleTask', 'bpmn:ScriptTask'],
        offered: ['bpmn:Task', 'bpmn:UserTask', 'bpmn:ServiceTask', 'bpmn:SendTask', 'bpmn:ReceiveTask',
                  'bpmn:ManualTask', 'bpmn:BusinessRuleTask']
      }},
      {{
        members: ['bpmn:ExclusiveGateway', 'bpmn:ParallelGateway', 'bpmn:InclusiveGateway',
                  'bpmn:EventBasedGateway', 'bpmn:ComplexGateway'],
        offered: ['bpmn:ExclusiveGateway', 'bpmn:ParallelGateway', 'bpmn:InclusiveGateway']
      }}
    ];

    function currentPropertyElement() {{
      const selection = modeler.get('selection').get();
      return selection.length === 1 ? selection[0] : null;
    }}

    function documentationOf(element) {{
      const docs = element.businessObject.documentation || [];
      return docs.length ? (docs[0].text || '') : '';
    }}

    function conditionOf(element) {{
      const expression = element.businessObject.conditionExpression;
      return expression ? (expression.body || '') : '';
    }}

    function updatePropertiesPanel(selection) {{
      const element = (selection && selection.length === 1) ? selection[0] : null;
      const isRealElement = !!element && element.type !== 'bpmn:Process' && !element.labelTarget;

      propEmpty.style.display = isRealElement ? 'none' : 'block';
      propBody.classList.toggle('hidden', !isRealElement);
      if (!isRealElement) return;

      const businessObject = element.businessObject;
      propId.value = businessObject.id || '';
      propName.value = businessObject.name || '';
      propDocumentation.value = documentationOf(element);

      const flow = isFlowConnection(element);
      propFlowFields.classList.toggle('hidden', !flow);
      propShapeFields.classList.toggle('hidden', flow);

      if (flow) {{
        propCondition.value = conditionOf(element);
        const source = element.source && element.source.businessObject;
        propDefault.checked = !!(source && source.default && source.default.id === businessObject.id);
        propDefault.disabled = !source || !/Gateway/.test(source.$type || '');
      }} else {{
        populateTypeSelector(element);
      }}
    }}

    // Seletor "Tipo do elemento": só tipos compatíveis com o elemento (tarefas entre
    // si, gateways entre si), com o tipo ATUAL selecionado. Sem troca válida
    // (eventos de início/fim, raias, subprocessos...) o campo inteiro fica oculto.
    function populateTypeSelector(element) {{
      const group = TYPE_GROUPS.find(g => g.members.indexOf(element.type) !== -1);
      propShapeFields.classList.toggle('hidden', !group);
      propType.innerHTML = '';
      if (!group) return;
      const options = group.offered.map(value => ({{
        value: value,
        label: (TYPE_OPTIONS.find(o => o.value === value) || {{ label: value.replace('bpmn:', '') }}).label
      }}));
      if (!options.some(o => o.value === element.type)) {{
        options.unshift({{ value: element.type, label: element.type.replace('bpmn:', '') + ' (atual)' }});
      }}
      options.forEach(o => {{
        const opt = document.createElement('option');
        opt.value = o.value;
        opt.textContent = o.label;
        propType.appendChild(opt);
      }});
      propType.value = element.type;
    }}

    function applyPropertyName() {{
      const element = currentPropertyElement();
      if (!element) return;
      try {{
        modeler.get('modeling').updateLabel(element, propName.value);
      }} catch (e) {{
        showError(e);
      }}
    }}

    function applyPropertyDocumentation() {{
      const element = currentPropertyElement();
      if (!element) return;
      try {{
        const moddle = modeler.get('moddle');
        const text = propDocumentation.value.trim();
        const documentation = text
          ? [moddle.create('bpmn:Documentation', {{ text: text }})]
          : [];
        modeler.get('modeling').updateProperties(element, {{ documentation: documentation }});
      }} catch (e) {{
        showError(e);
      }}
    }}

    function applyPropertyType() {{
      const element = currentPropertyElement();
      const target = propType.value;
      if (!element || !target || element.type === target) return;
      try {{
        const replaced = modeler.get('bpmnReplace').replaceElement(element, {{ type: target }});
        modeler.get('selection').select(replaced);
        showToast('Tipo alterado para ' + target.replace('bpmn:', ''));
      }} catch (e) {{
        showError(e);
      }}
    }}

    function applyPropertyCondition() {{
      const element = currentPropertyElement();
      if (!element || !isFlowConnection(element)) return;
      try {{
        const moddle = modeler.get('moddle');
        const body = propCondition.value.trim();
        const conditionExpression = body
          ? moddle.create('bpmn:FormalExpression', {{ body: body }})
          : undefined;
        modeler.get('modeling').updateProperties(element, {{ conditionExpression: conditionExpression }});
      }} catch (e) {{
        showError(e);
      }}
    }}

    function applyPropertyDefaultFlow() {{
      const element = currentPropertyElement();
      if (!element || !isFlowConnection(element) || !element.source) return;
      try {{
        modeler.get('modeling').updateProperties(element.source, {{
          default: propDefault.checked ? element.businessObject : undefined
        }});
        if (propDefault.checked && propCondition.value.trim()) {{
          // O ramo default é justamente o "nenhuma condição bateu".
          propCondition.value = '';
          applyPropertyCondition();
        }}
      }} catch (e) {{
        showError(e);
      }}
    }}

    // ---------------------------------------------------------------------
    // Validação dentro do editor: um subconjunto das regras de
    // scripts/lint_rules.py, com os MESMOS ids de regra, para que o que o
    // editor mostra e o que `bpmn_tool validate` reporta sejam o mesmo
    // vocabulário. A autoridade continua sendo o linter em Python; aqui é
    // realimentação imediata enquanto se desenha.
    // ---------------------------------------------------------------------
    const GATEWAY_TYPES = [
      'bpmn:ExclusiveGateway', 'bpmn:ParallelGateway', 'bpmn:InclusiveGateway',
      'bpmn:EventBasedGateway', 'bpmn:ComplexGateway'
    ];

    function flowNodes() {{
      return modeler.get('elementRegistry').filter(el =>
        el.businessObject
        && el.businessObject.$instanceOf
        && el.businessObject.$instanceOf('bpmn:FlowNode')
        && !el.labelTarget
      );
    }}

    function outgoingOf(element) {{
      return (element.businessObject.outgoing || []);
    }}

    function incomingOf(element) {{
      return (element.businessObject.incoming || []);
    }}

    function reachesAnEnd(nodes) {{
      const byId = {{}};
      nodes.forEach(node => {{ byId[node.id] = node; }});
      const reaching = new Set();
      const stack = nodes.filter(n => n.type === 'bpmn:EndEvent').map(n => n.id);
      while (stack.length) {{
        const id = stack.pop();
        if (reaching.has(id)) continue;
        reaching.add(id);
        const node = byId[id];
        if (!node) continue;
        incomingOf(node).forEach(flow => {{
          if (flow.sourceRef) stack.push(flow.sourceRef.id);
        }});
        if (node.type === 'bpmn:BoundaryEvent' && node.businessObject.attachedToRef) {{
          stack.push(node.businessObject.attachedToRef.id);
        }}
      }}
      return reaching;
    }}

    function laneMembership() {{
      const covered = new Set();
      let hasLanes = false;
      modeler.get('elementRegistry').forEach(el => {{
        if (el.type !== 'bpmn:Lane') return;
        hasLanes = true;
        (el.businessObject.flowNodeRef || []).forEach(ref => covered.add(ref.id));
      }});
      return {{ hasLanes: hasLanes, covered: covered }};
    }}

    function collectValidationFindings() {{
      const findings = [];
      const nodes = flowNodes();
      if (!nodes.length) return findings;

      const reaching = reachesAnEnd(nodes);
      const hasEndEvent = nodes.some(n => n.type === 'bpmn:EndEvent');
      const lanes = laneMembership();

      nodes.forEach(node => {{
        const name = (node.businessObject.name || '').trim();
        const outgoing = outgoingOf(node);
        const incoming = incomingOf(node);

        if (node.type !== 'bpmn:EndEvent' && outgoing.length === 0) {{
          findings.push({{ rule: 'dead-end', severity: 'error', id: node.id,
            message: (name || node.id) + ' não tem fluxo de saída' }});
        }}
        if (node.type !== 'bpmn:StartEvent' && node.type !== 'bpmn:BoundaryEvent' && incoming.length === 0) {{
          findings.push({{ rule: 'unreachable-node', severity: 'error', id: node.id,
            message: (name || node.id) + ' não recebe nenhum fluxo' }});
        }}
        if (hasEndEvent && outgoing.length > 0 && !reaching.has(node.id)) {{
          findings.push({{ rule: 'no-path-to-end', severity: 'error', id: node.id,
            message: (name || node.id) + ' nunca alcança um evento de fim' }});
        }}
        if ((node.type === 'bpmn:ExclusiveGateway' || node.type === 'bpmn:InclusiveGateway')
            && outgoing.length > 1) {{
          const defaultFlow = node.businessObject.default;
          const missing = outgoing.filter(flow =>
            (!defaultFlow || flow.id !== defaultFlow.id)
            && !(flow.conditionExpression && (flow.conditionExpression.body || '').trim())
          );
          if (missing.length) {{
            findings.push({{ rule: 'gateway-without-condition', severity: 'warn', id: node.id,
              message: (name || node.id) + ' divide sem condição escrita em ' + missing.length + ' saída(s)' }});
          }}
        }}
        if (!name && (GATEWAY_TYPES.indexOf(node.type) >= 0
            || /Task$/.test(node.type) || node.type === 'bpmn:StartEvent' || node.type === 'bpmn:EndEvent')) {{
          findings.push({{ rule: 'unnamed-element', severity: 'warn', id: node.id,
            message: node.id + ' está sem nome e renderiza como caixa vazia' }});
        }}
        if (lanes.hasLanes && !lanes.covered.has(node.id)) {{
          findings.push({{ rule: 'lane-coverage-missing', severity: 'warn', id: node.id,
            message: (name || node.id) + ' não está em nenhuma raia' }});
        }}
      }});

      return findings;
    }}

    function selectValidationFinding(elementId) {{
      try {{
        const element = modeler.get('elementRegistry').get(elementId);
        if (!element) return;
        modeler.get('selection').select(element);
        modeler.get('canvas').scrollToElement(element);
      }} catch (e) {{}}
    }}

    function runDiagramValidation() {{
      validationResults.innerHTML = '';
      let findings = [];
      try {{
        findings = collectValidationFindings();
      }} catch (e) {{
        showError(e);
        return;
      }}

      if (!findings.length) {{
        const ok = document.createElement('div');
        ok.className = 'validation-ok';
        ok.textContent = '✅ Nenhum problema encontrado nas regras verificadas aqui.';
        validationResults.appendChild(ok);
        return;
      }}

      findings.forEach(finding => {{
        const item = document.createElement('button');
        item.className = 'validation-finding ' + finding.severity;
        item.title = 'Clique para selecionar o elemento no diagrama';
        const rule = document.createElement('span');
        rule.className = 'rule';
        rule.textContent = finding.severity + ' · ' + finding.rule;
        item.appendChild(rule);
        item.appendChild(document.createTextNode(finding.message));
        item.addEventListener('click', () => selectValidationFinding(finding.id));
        validationResults.appendChild(item);
      }});
      showToast(findings.length + ' achado(s) de validação');
    }}

    btnValidate.addEventListener('click', runDiagramValidation);

    // ---------------------------------------------------------------------
    // Alinhar / distribuir (módulos nativos do bpmn-js) e impressão em PDF
    // ---------------------------------------------------------------------
    function alignSelection(direction) {{
      const selected = getSelectedElements().filter(el => !el.waypoints);
      if (selected.length < 2) {{
        showToast('Selecione pelo menos 2 elementos para alinhar');
        return;
      }}
      try {{
        modeler.get('alignElements').trigger(selected, direction);
      }} catch (e) {{
        showError(e);
      }}
    }}

    function distributeSelection(axis) {{
      // O distributeElements do bpmn-js reposiciona os elementos DO MEIO: com
      // dois selecionados não há meio, então ele não teria o que fazer.
      const selected = getSelectedElements().filter(el => !el.waypoints);
      if (selected.length < 3) {{
        showToast('Selecione pelo menos 3 elementos para distribuir o espaçamento');
        return;
      }}
      try {{
        modeler.get('distributeElements').trigger(selected, axis);
      }} catch (e) {{
        showError(e);
      }}
    }}

    function exportPDF() {{
      // A folha de estilo @media print esconde a interface e imprime só o
      // canvas; o "Salvar como PDF" do próprio navegador gera o arquivo.
      showToast('Escolha "Salvar como PDF" na janela de impressão');
      window.print();
    }}

    btnAlignLeft.addEventListener('click', () => alignSelection('left'));
    btnAlignMiddle.addEventListener('click', () => alignSelection('middle'));
    btnDistributeH.addEventListener('click', () => distributeSelection('horizontal'));
    btnExportPdf.addEventListener('click', exportPDF);

    propName.addEventListener('change', applyPropertyName);
    propDocumentation.addEventListener('change', applyPropertyDocumentation);
    propType.addEventListener('change', applyPropertyType);
    propCondition.addEventListener('change', applyPropertyCondition);
    propDefault.addEventListener('change', applyPropertyDefaultFlow);
    btnPropsToggle.addEventListener('click', () => {{
      propertiesPanel.classList.toggle('hidden');
    }});

    // options.fromDisk: `xml` é o conteúdo lido do disco (arquivo/handle/fetch) e passa a ser a
    //   referência para detectar mudanças externas (options.url = origem via fetch).
    // options.keepDiskRef: mantém a referência de disco atual (ex.: recuperação de rascunho).
    async function loadXML(xml, name = "diagrama.bpmn", handle = null, options = {{}}) {{
      try {{
        clearError();
        if (isDirty && !options.keepDiskRef) {{
          // Chegar aqui com alterações pendentes significa que o usuário já confirmou o descarte.
          cancelDraftSave();
          clearDraft();
        }}
        elementFontStyles = {{}};
        updateFontToolbarFromSelection([]);
        updatePropertiesPanel([]);
        await modeler.importXML(xml);
        if (!options.keepDiskRef) {{
          lastDiskText = options.fromDisk ? xml : null;
          diskUrl = options.fromDisk ? (options.url || null) : null;
          ignoredDiskText = null;
          hideNotice('disk-changed');
        }}
        enforceOrthogonalConnections();
        applyAllElementFontStyles();
        try {{ modeler.get('commandStack').clear(); }} catch (e) {{}}
        setFileState(name, handle, false);
        updateUndoRedoState();
        setTimeout(() => {{
          try {{ modeler.get('canvas').zoom('fit-viewport'); }} catch (e) {{}}
        }}, 100);
        showToast(`Diagrama '${{name}}' carregado com sucesso.`);
      }} catch (err) {{
        showError(err);
      }}
    }}

    loadXMLImpl = loadXML;

    // Abrir arquivo via File System Access API ou input fallback
    async function openFile() {{
      if (!confirmDiscardIfDirty('Você possui alterações não salvas. Deseja descartá-las para abrir outro arquivo?')) return;
      if (window.showOpenFilePicker) {{
        try {{
          const [handle] = await window.showOpenFilePicker({{
            types: [{{
              description: 'Arquivos BPMN / XML',
              accept: {{ 'application/xml': ['.bpmn', '.xml'] }}
            }}],
            multiple: false
          }});
          const file = await handle.getFile();
          const text = await file.text();
          await loadXML(text, file.name, handle, {{ fromDisk: true }});
        }} catch (err) {{
          if (err.name !== 'AbortError') showError(err);
        }}
      }} else {{
        fileInput.value = '';
        fileInput.click();
      }}
    }}

    fileInput.addEventListener('change', async (e) => {{
      const file = e.target.files[0];
      if (!file) return;
      const text = await file.text();
      await loadXML(text, file.name, null);
    }});

    // Salvamento bem-sucedido: o rascunho deixa de ser necessário.
    function afterSave(previousName) {{
      cancelDraftSave();
      clearDraft();
      if (previousName) clearDraft(previousName);
      draftRecoveryPending = false;
      hideNotice('draft');
    }}

    // Salvar diretamente no arquivo
    async function saveFile() {{
      try {{
        const {{ xml }} = await modeler.saveXML({{ format: true }});
        if (currentFileHandle && currentFileHandle.createWritable) {{
          // Nunca sobrescrever em silêncio uma versão mais nova que está no disco.
          if (!(await confirmOverwriteIfDiskChanged())) {{
            showToast('Salvamento cancelado: o arquivo no disco foi alterado.');
            return;
          }}
          const writable = await currentFileHandle.createWritable();
          await writable.write(xml);
          await writable.close();
          lastDiskText = xml;
          ignoredDiskText = null;
          hideNotice('disk-changed');
          setFileState(currentFileName, currentFileHandle, false);
          afterSave();
          showToast(`Arquivo '${{currentFileName}}' salvo diretamente no disco!`);
          return;
        }}
        // Se não possui handle ativo, chama Salvar Como
        await saveFileAs();
      }} catch (err) {{
        showError('Falha ao salvar: ' + err.message);
      }}
    }}

    // Salvar Como / Download
    async function saveFileAs() {{
      const previousName = currentFileName;
      try {{
        const {{ xml }} = await modeler.saveXML({{ format: true }});
        if (window.showSaveFilePicker) {{
          try {{
            const handle = await window.showSaveFilePicker({{
              suggestedName: currentFileName,
              types: [{{
                description: 'Arquivo BPMN',
                accept: {{ 'application/xml': ['.bpmn', '.xml'] }}
              }}]
            }});
            const writable = await handle.createWritable();
            await writable.write(xml);
            await writable.close();
            lastDiskText = xml;
            diskUrl = null;
            ignoredDiskText = null;
            hideNotice('disk-changed');
            setFileState(handle.name, handle, false);
            afterSave(previousName);
            showToast(`Arquivo salvo como '${{handle.name}}'!`);
            return;
          }} catch (err) {{
            if (err.name === 'AbortError') return;
          }}
        }}

        // Fallback: Download via Blob
        const blob = new Blob([xml], {{ type: 'application/xml' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = currentFileName.endsWith('.bpmn') ? currentFileName : currentFileName + '.bpmn';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setFileState(currentFileName, currentFileHandle, false);
        afterSave();
        showToast(`Download de '${{currentFileName}}' iniciado.`);
      }} catch (err) {{
        showError('Falha ao exportar: ' + err.message);
      }}
    }}

    // Novo Processo
    function newDiagram() {{
      if (isDirty && !confirm('Você possui alterações não salvas. Deseja descartá-las para criar um novo diagrama?')) {{
        return;
      }}
      loadXML(PRESETS['_blank'], 'novo-processo.bpmn', null);
    }}

    // Alinhamento Ortogonal 90° de Conexões
    function layoutOrthogonalRoute() {{
      try {{
        const selection = modeler.get('selection').get();
        const modeling = modeler.get('modeling');
        const connections = selection.filter(el => el.waypoints);

        if (connections.length > 0) {{
          connections.forEach(conn => modeling.layoutConnection(conn));
          showToast(`${{connections.length}} conexão(ões) recalculada(s) em curvas de 90°!`);
        }} else {{
          const elementRegistry = modeler.get('elementRegistry');
          const allConns = elementRegistry.filter(el => el.waypoints && (el.type === 'bpmn:SequenceFlow' || el.type === 'bpmn:MessageFlow' || el.type === 'bpmn:Association'));
          if (allConns.length === 0) {{
            showToast('Nenhuma conexão encontrada para alinhar.');
            return;
          }}
          allConns.forEach(conn => modeling.layoutConnection(conn));
          showToast(`Todas as ${{allConns.length}} conexões foram alinhadas em 90°!`);
        }}
      }} catch (err) {{
        showError('Erro ao calcular rota ortogonal: ' + err.message);
      }}
    }}

    // Aplicação de Cores
    function applyColor(fill, stroke) {{
      try {{
        const selection = modeler.get('selection').get();
        if (!selection || selection.length === 0) {{
          showToast('Selecione um ou mais elementos para aplicar a cor.');
          return;
        }}
        const modeling = modeler.get('modeling');
        modeling.setColor(selection, {{ fill, stroke }});
        showToast(`Cor aplicada a ${{selection.length}} elemento(s).`);
      }} catch (err) {{
        showError('Erro ao aplicar cor: ' + err.message);
      }}
    }}

    // Seleção atual normalizada: um rótulo externo conta como o elemento dono dele,
    // sem duplicatas (o estilo mora no DI do elemento, não no rótulo).
    function getSelectedElements() {{
      if (!modeler) return [];
      try {{
        const selection = modeler.get('selection').get() || [];
        const result = [];
        selection.forEach(el => {{
          const target = el.labelTarget || el;
          if (result.indexOf(target) === -1) result.push(target);
        }});
        return result;
      }} catch (e) {{
        return [];
      }}
    }}


    // Injeta/atualiza regras de estilo CSS específicas para os elementos estilizados
    function applyAllElementFontStyles() {{
      if (modeler) refreshFontStylesFromDiagram();
      const keys = Object.keys(elementFontStyles);
      let cssRules = '';

      const elementRegistry = modeler ? modeler.get('elementRegistry') : null;

      keys.forEach(id => {{
        const s = elementFontStyles[id];
        if (!s) return;
        const weight = s.isBold ? 'bold' : 'normal';
        const style = s.isItalic ? 'italic' : 'normal';
        const size = s.fontSize || '12px';

        // Determina ID do rótulo externo (se existir)
        let labelId = id + '_label';
        if (elementRegistry) {{
          try {{
            const shape = elementRegistry.get(id);
            if (shape && shape.label && shape.label.id) {{
              labelId = shape.label.id;
            }}
          }} catch (e) {{}}
        }}

        cssRules += `
          g[data-element-id="${{id}}"] text,
          g[data-element-id="${{id}}"] text tspan,
          g[data-element-id="${{id}}"] .djs-label,
          g[data-element-id="${{id}}"] .djs-label tspan,
          g[data-element-id="${{labelId}}"] text,
          g[data-element-id="${{labelId}}"] text tspan,
          g[data-element-id="${{labelId}}"] .djs-label,
          g[data-element-id="${{labelId}}"] .djs-label tspan {{
            font-size: ${{size}} !important;
            font-weight: ${{weight}} !important;
            font-style: ${{style}} !important;
          }}
        `;

        // Aplica também diretamente no DOM gráfico dos nós correspondentes
        if (elementRegistry) {{
          try {{
            const gfx = elementRegistry.getGraphics(id);
            if (gfx) {{
              gfx.querySelectorAll('text, tspan').forEach(t => {{
                t.style.setProperty('font-size', size, 'important');
                t.style.setProperty('font-weight', weight, 'important');
                t.style.setProperty('font-style', style, 'important');
              }});
            }}
            if (labelId && labelId !== id) {{
              const labelGfx = elementRegistry.getGraphics(labelId);
              if (labelGfx) {{
                labelGfx.querySelectorAll('text, tspan').forEach(t => {{
                  t.style.setProperty('font-size', size, 'important');
                  t.style.setProperty('font-weight', weight, 'important');
                  t.style.setProperty('font-style', style, 'important');
                }});
              }}
            }}
          }} catch (e) {{}}
        }}
      }});

      // 1. Atualiza folha de estilo no documento para visualização imediata no canvas
      let styleTag = document.getElementById('diagram-font-override');
      if (!styleTag) {{
        styleTag = document.createElement('style');
        styleTag.id = 'diagram-font-override';
        document.head.appendChild(styleTag);
      }}
      styleTag.textContent = cssRules;

      // 2. Injeta bloco de estilo no SVG <defs> para exportações SVG e PNG
      try {{
        const svgEl = document.querySelector('#canvas svg');
        if (svgEl) {{
          let defs = svgEl.querySelector('defs');
          if (!defs) {{
            defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            svgEl.insertBefore(defs, svgEl.firstChild);
          }}
          let svgStyle = defs.querySelector('#svg-font-style');
          if (!svgStyle) {{
            svgStyle = document.createElementNS('http://www.w3.org/2000/svg', 'style');
            svgStyle.setAttribute('id', 'svg-font-style');
            svgStyle.setAttribute('type', 'text/css');
            defs.appendChild(svgStyle);
          }}
          svgStyle.textContent = cssRules;
        }}
      }} catch (e) {{
        console.warn('Erro ao atualizar estilos tipográficos do SVG:', e);
      }}
    }}

    const applyDiagramFont = applyAllElementFontStyles;

    function updateFontToolbarFromSelection(selection) {{
      if (!selection || selection.length === 0) {{
        fontSizeSelect.value = '12px';
        btnFontBold.classList.remove('active');
        btnFontItalic.classList.remove('active');
        return;
      }}
      if (selection.length === 1) {{
        const s = elementFontStyles[selection[0].id];
        if (s) {{
          fontSizeSelect.value = s.fontSize || '12px';
          btnFontBold.classList.toggle('active', !!s.isBold);
          btnFontItalic.classList.toggle('active', !!s.isItalic);
          return;
        }}
      }}
      const allBold = selection.every(el => elementFontStyles[el.id] && elementFontStyles[el.id].isBold);
      const allItalic = selection.every(el => elementFontStyles[el.id] && elementFontStyles[el.id].isItalic);
      btnFontBold.classList.toggle('active', allBold);
      btnFontItalic.classList.toggle('active', allItalic);
      const firstSize = (elementFontStyles[selection[0].id] && elementFontStyles[selection[0].id].fontSize) || '12px';
      const sameSize = selection.every(el => ((elementFontStyles[el.id] && elementFontStyles[el.id].fontSize) || '12px') === firstSize);
      fontSizeSelect.value = sameSize ? firstSize : '12px';
    }}

    function setFontSize(val) {{
      const selection = getSelectedElements();
      if (selection.length === 0) {{
        showToast('Selecione um ou mais elementos para alterar o tamanho da fonte.');
        fontSizeSelect.value = '12px';
        return;
      }}
      const size = parseInt(val, 10) || FONT_DEFAULT_SIZE;
      try {{
        const count = applyFontChange(selection, font => ({{ size: size, isBold: font.isBold, isItalic: font.isItalic }}));
        showToast(`Tamanho da fonte (${{size}}px) aplicado a ${{count}} elemento(s).`);
      }} catch (err) {{
        showError('Erro ao alterar a fonte: ' + err.message);
      }}
    }}

    function toggleBold() {{
      const selection = getSelectedElements();
      if (selection.length === 0) {{
        showToast('Selecione um ou mais elementos para alternar negrito.');
        return;
      }}
      const newBold = !selection.every(el => fontOfElement(el).isBold);
      try {{
        const count = applyFontChange(selection, font => ({{ size: font.size, isBold: newBold, isItalic: font.isItalic }}));
        showToast(`Negrito ${{newBold ? 'ativado' : 'desativado'}} em ${{count}} elemento(s).`);
      }} catch (err) {{
        showError('Erro ao alterar a fonte: ' + err.message);
      }}
    }}

    function toggleItalic() {{
      const selection = getSelectedElements();
      if (selection.length === 0) {{
        showToast('Selecione um ou mais elementos para alternar itálico.');
        return;
      }}
      const newItalic = !selection.every(el => fontOfElement(el).isItalic);
      try {{
        const count = applyFontChange(selection, font => ({{ size: font.size, isBold: font.isBold, isItalic: newItalic }}));
        showToast(`Itálico ${{newItalic ? 'ativado' : 'desativado'}} em ${{count}} elemento(s).`);
      }} catch (err) {{
        showError('Erro ao alterar a fonte: ' + err.message);
      }}
    }}

    // Desfazer / Refazer
    function undoAction() {{
      try {{
        const cs = modeler.get('commandStack');
        if (cs.canUndo()) cs.undo();
      }} catch (e) {{}}
    }}

    function redoAction() {{
      try {{
        const cs = modeler.get('commandStack');
        if (cs.canRedo()) cs.redo();
      }} catch (e) {{}}
    }}

    // Controles de Zoom
    function zoomIn() {{
      try {{
        const canvas = modeler.get('canvas');
        canvas.zoom(canvas.zoom() * 1.25);
      }} catch (e) {{}}
    }}

    function zoomOut() {{
      try {{
        const canvas = modeler.get('canvas');
        canvas.zoom(canvas.zoom() * 0.8);
      }} catch (e) {{}}
    }}

    function zoomFit() {{
      try {{
        modeler.get('canvas').zoom('fit-viewport');
      }} catch (e) {{}}
    }}

    function zoomReset() {{
      try {{
        modeler.get('canvas').zoom(1.0);
      }} catch (e) {{}}
    }}

    // Busca no Diagrama (SearchPad)
    function toggleSearch() {{
      try {{
        const searchPad = modeler.get('searchPad');
        if (searchPad) {{
          searchPad.toggle();
        }}
      }} catch (e) {{
        console.warn('SearchPad não disponível:', e);
      }}
    }}

    // Exportação SVG
    async function exportSVG() {{
      try {{
        applyDiagramFont();
        const {{ svg }} = await modeler.saveSVG({{ format: true }});
        const blob = new Blob([svg], {{ type: 'image/svg+xml;charset=utf-8' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const baseName = currentFileName.replace(/\\.(bpmn|xml)$/i, '');
        a.download = `${{baseName}}.svg`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        showToast(`Diagrama vetorial '${{baseName}}.svg' exportado!`);
      }} catch (err) {{
        showError('Falha ao exportar SVG: ' + err.message);
      }}
    }}

    // Exportação PNG em Alta Resolução (2x retina)
    async function exportPNG() {{
      try {{
        applyDiagramFont();
        const {{ svg }} = await modeler.saveSVG();
        const img = new Image();
        const svgBlob = new Blob([svg], {{ type: 'image/svg+xml;charset=utf-8' }});
        const url = URL.createObjectURL(svgBlob);

        img.onload = () => {{
          try {{
            const canvas = document.createElement('canvas');
            const scale = 2;
            canvas.width = (img.naturalWidth || img.width || 1200) * scale;
            canvas.height = (img.naturalHeight || img.height || 800) * scale;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);

            canvas.toBlob((pngBlob) => {{
              const pngUrl = URL.createObjectURL(pngBlob);
              const a = document.createElement('a');
              a.href = pngUrl;
              const baseName = currentFileName.replace(/\\.(bpmn|xml)$/i, '');
              a.download = `${{baseName}}.png`;
              document.body.appendChild(a);
              a.click();
              a.remove();
              setTimeout(() => URL.revokeObjectURL(pngUrl), 1000);
              showToast(`Imagem PNG de alta resolução '${{baseName}}.png' exportada!`);
            }}, 'image/png');
          }} catch (e) {{
            URL.revokeObjectURL(url);
            showError('Falha ao gerar PNG: ' + e.message);
          }}
        }};

        img.onerror = () => {{
          URL.revokeObjectURL(url);
          showError('Falha ao renderizar vetor para PNG.');
        }};

        img.src = url;
      }} catch (err) {{
        showError('Falha ao exportar PNG: ' + err.message);
      }}
    }}

    // Eventos da Toolbar
    document.getElementById('btn-open').addEventListener('click', openFile);
    document.getElementById('btn-save').addEventListener('click', saveFile);
    document.getElementById('btn-save-as').addEventListener('click', saveFileAs);
    document.getElementById('btn-new').addEventListener('click', newDiagram);
    btnUndo.addEventListener('click', undoAction);
    btnRedo.addEventListener('click', redoAction);
    document.getElementById('btn-route-90').addEventListener('click', layoutOrthogonalRoute);
    document.getElementById('btn-search').addEventListener('click', toggleSearch);
    document.getElementById('btn-zoom-out').addEventListener('click', zoomOut);
    document.getElementById('btn-zoom-in').addEventListener('click', zoomIn);
    document.getElementById('btn-zoom-fit').addEventListener('click', zoomFit);
    document.getElementById('btn-zoom-reset').addEventListener('click', zoomReset);
    document.getElementById('btn-export-svg').addEventListener('click', exportSVG);
    document.getElementById('btn-export-png').addEventListener('click', exportPNG);
    fontSizeSelect.addEventListener('change', (e) => setFontSize(e.target.value));
    btnFontBold.addEventListener('click', toggleBold);
    btnFontItalic.addEventListener('click', toggleItalic);

    // Eventos de Cores
    document.querySelectorAll('.color-dot').forEach(dot => {{
      dot.addEventListener('click', () => {{
        const fill = dot.getAttribute('data-fill');
        const stroke = dot.getAttribute('data-stroke');
        applyColor(fill, stroke);
      }});
    }});

    // Seletor de Presets
    presetSelect.addEventListener('change', (e) => {{
      const val = e.target.value;
      if (!val || !PRESETS[val]) return;
      if (isDirty && !confirm('Você possui alterações não salvas. Deseja carregar o exemplo selecionado?')) {{
        presetSelect.value = '';
        return;
      }}
      loadXML(PRESETS[val], val, null);
      presetSelect.value = '';
    }});

    // Drag & Drop
    window.addEventListener('dragenter', (e) => {{
      e.preventDefault();
      dropOverlay.style.display = 'flex';
    }});
    dropOverlay.addEventListener('dragover', (e) => e.preventDefault());
    dropOverlay.addEventListener('dragleave', (e) => {{
      if (e.relatedTarget === null || e.relatedTarget === document.body) {{
        dropOverlay.style.display = 'none';
      }}
    }});
    dropOverlay.addEventListener('drop', async (e) => {{
      e.preventDefault();
      dropOverlay.style.display = 'none';
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {{
        const file = files[0];
        if (file.name.endsWith('.bpmn') || file.name.endsWith('.xml')) {{
          if (!confirmDiscardIfDirty('Você possui alterações não salvas. Deseja descartá-las para abrir o arquivo solto?')) return;
          const text = await file.text();
          loadXML(text, file.name, null);
        }} else {{
          showError('Por favor, selecione um arquivo com extensão .bpmn ou .xml');
        }}
      }}
    }});

    // Permite rolagem horizontal da barra pelo scroll vertical do mouse quando houver overflow
    const appHeader = document.getElementById('app-header');
    if (appHeader) {{
      appHeader.addEventListener('wheel', (e) => {{
        if (e.deltaY !== 0 && appHeader.scrollWidth > appHeader.clientWidth) {{
          e.preventDefault();
          appHeader.scrollLeft += e.deltaY;
        }}
      }}, {{ passive: false }});
    }}

    // Atalhos de teclado.
    // Ctrl+Z, Ctrl+Y/Ctrl+Shift+Z (desfazer/refazer) e Ctrl+F (busca) pertencem ao
    // `keyboard` do próprio bpmn-js (bindTo: document). NÃO são tratados aqui: um
    // segundo listener executaria a ação duas vezes, e ainda desfaria o canvas
    // quando o foco está num campo de texto (o navegador deve desfazer no campo).
    // Aqui ficam só Ctrl+S, Ctrl+O, Ctrl+B e Ctrl+I, respeitando o foco.
    function isTextEditingTarget(el) {{
      if (!el || !el.tagName) return false;
      const tag = el.tagName.toUpperCase();
      if (tag === 'TEXTAREA') return true;
      if (tag === 'INPUT') {{
        const type = (el.getAttribute('type') || 'text').toLowerCase();
        return ['button', 'checkbox', 'radio', 'submit', 'reset', 'file', 'range', 'color', 'image'].indexOf(type) === -1;
      }}
      return !!el.isContentEditable;
    }}

    window.addEventListener('keydown', (e) => {{
      if (e.defaultPrevented || !(e.ctrlKey || e.metaKey) || e.altKey || !e.key) return;
      const key = e.key.toLowerCase();
      const editing = isTextEditingTarget(e.target);
      if (key === 's') {{
        e.preventDefault();
        // Confirma a edição pendente do campo (dispara 'change') antes de salvar.
        if (editing && propertiesPanel.contains(e.target)) e.target.blur();
        saveFile();
      }} else if (key === 'o') {{
        e.preventDefault();
        openFile();
      }} else if (key === 'b' && !editing) {{
        e.preventDefault();
        toggleBold();
      }} else if (key === 'i' && !editing) {{
        e.preventDefault();
        toggleItalic();
      }}
    }});

    // Carga inicial
    const urlParams = new URLSearchParams(window.location.search);
    const fileParam = urlParams.get('file');

    // Diagrama do projeto: o arquivo em DISCO vem antes do snapshot embutido no HTML
    // (que fica velho quando o .bpmn é regenerado). O snapshot só entra quando o
    // disco não pode ser lido (ex.: file://), e então o usuário é avisado.
    async function loadProjectDiagram() {{
      const url = encodeURI(DEFAULT_DIAGRAM_NAME);
      const disk = await fetchDiskText(url);
      if (disk !== null) {{
        await loadXML(disk, DEFAULT_DIAGRAM_NAME, null, {{ fromDisk: true, url: url }});
        if (normalizeXmlText(disk) !== normalizeXmlText(DEFAULT_DIAGRAM_XML)) {{
          showNotice('snapshot-stale',
            `O arquivo '${{DEFAULT_DIAGRAM_NAME}}' em disco é diferente do snapshot embutido neste editor ` +
            '(provavelmente mais novo). Foi carregada a versão do disco.');
        }}
        return;
      }}
      await loadXML(DEFAULT_DIAGRAM_XML, DEFAULT_DIAGRAM_NAME, null);
      showNotice('snapshot-only',
        `Não foi possível ler '${{DEFAULT_DIAGRAM_NAME}}' do disco; foi carregado o snapshot embutido neste editor, ` +
        'que pode estar desatualizado. Use "Abrir" para escolher o arquivo do projeto antes de editar e salvar.');
    }}

    async function initEditor() {{
      await loadInitialDiagram();
      offerDraftRecovery();
    }}

    async function loadInitialDiagram() {{
      applyDiagramFont();

      let baseParam = fileParam;
      if (fileParam) {{
        const lastSlash = Math.max(fileParam.lastIndexOf('/'), fileParam.lastIndexOf('\\\\'));
        if (lastSlash >= 0) {{
          baseParam = fileParam.substring(lastSlash + 1);
        }}
      }}

      // 1. Se foi passado ?file=..., prioriza o arquivo solicitado
      if (fileParam) {{
        currentFileName = baseParam || fileParam;
        setFileState(currentFileName, null, false);

        // Se o arquivo solicitado corresponder ao diagrama padrão embutido (por nome exato ou nome base)
        if (DEFAULT_DIAGRAM_NAME && (fileParam === DEFAULT_DIAGRAM_NAME || baseParam === DEFAULT_DIAGRAM_NAME) && DEFAULT_DIAGRAM_XML) {{
          await loadProjectDiagram();
          return;
        }}

        // Se corresponder a um dos presets embutidos
        const presetKey = PRESETS[fileParam] ? fileParam : (baseParam && PRESETS[baseParam] ? baseParam : null);
        if (presetKey) {{
          await loadXML(PRESETS[presetKey], presetKey, null);
          return;
        }}

        // Tenta fetch local (funciona se servido via http/https ou servidor dev)
        try {{
          const res = await fetch(fileParam, {{ cache: 'no-store' }});
          if (res.ok) {{
            const xml = await res.text();
            await loadXML(xml, currentFileName, null, {{ fromDisk: true, url: fileParam }});
            return;
          }}
        }} catch (e) {{
          console.warn('Falha no fetch de arquivo local (possível CORS em file://):', e);
        }}

        // Se há diagrama padrão embutido neste editor do projeto, carrega-o para a tela não ficar em branco
        if (DEFAULT_DIAGRAM_NAME && DEFAULT_DIAGRAM_XML) {{
          await loadProjectDiagram();
          showToast(`Carregado diagrama padrão '${{DEFAULT_DIAGRAM_NAME}}'.`);
          return;
        }}

        // Se não há diagrama embutido e fetch falhou, inicializa novo diagrama limpo para a interface não ficar em branco
        newDiagram();
        showToast(`Arquivo '${{fileParam}}' configurado. Use '📂 Abrir' ou arraste o arquivo para carregar.`);
        return;
      }}

      // 2. Se não foi passado ?file=, mas há um diagrama padrão configurado (editor copiado no projeto)
      if (DEFAULT_DIAGRAM_NAME && DEFAULT_DIAGRAM_XML) {{
        await loadProjectDiagram();
        return;
      }}

      // 3. Fallback: NUNCA apontar para diagrama de exemplo da skill por padrão. Inicia em branco.
      newDiagram();
    }}

    initEditor();
  }}
</script>
</body>
</html>
"""

html_content = render_editor_html()


def main():
    output_path = ROOT_DIR / "editor.html"
    content = render_editor_html()
    output_path.write_text(content, encoding="utf-8")
    mode = "offline (bpmn-js embutido)" if 'content="vendored"' in content else "CDN (unpkg)"
    size = output_path.stat().st_size
    print(f"[OK] Generated central editor at: {output_path} ({size} bytes on disk) -- assets: {mode}")


if __name__ == "__main__":
    main()
