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
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

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

html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>BPMN Editor Central</title>
<!-- bpmn-js v17.0.0 (Modeler) -->
<link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.0.0/dist/assets/diagram-js.css" />
<link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.0.0/dist/assets/bpmn-font/css/bpmn.css" />
<script src="https://unpkg.com/bpmn-js@17.0.0/dist/bpmn-modeler.production.min.js"></script>

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

  #canvas {{
    flex: 1 1 auto;
    width: 100%;
    min-height: 0;
    background: #ffffff;
    position: relative;
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

  <!-- Grupo Visualização & Zoom -->
  <div class="button-group">
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
<div id="canvas"></div>

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
  const fontSizeSelect = document.getElementById('font-size-select');
  const btnFontBold = document.getElementById('btn-font-bold');
  const btnFontItalic = document.getElementById('btn-font-italic');

  let elementFontStyles = {{}};

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

  function setFileState(name, handle = null, dirty = false) {{
    currentFileName = name;
    currentFileHandle = handle;
    isDirty = dirty;
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

  if (typeof BpmnJS === 'undefined') {{
    showError('Não foi possível carregar a biblioteca bpmn-js do CDN. Verifique sua conexão com a internet.');
  }} else {{
    modeler = new BpmnJS({{
      container: '#canvas',
      keyboard: {{ bindTo: document }},
      gridSnapping: {{ active: true }},
      additionalModules: [
        CustomResizeModule
      ]
    }});

    // Atualiza estado de alteração e botões de undo/redo
    modeler.on('commandStack.changed', () => {{
      if (!isDirty) setFileState(currentFileName, currentFileHandle, true);
      updateUndoRedoState();
      applyAllElementFontStyles();
    }});

    // Atualiza controles de fonte na toolbar quando a seleção de elementos muda
    modeler.on('selection.changed', (e) => {{
      updateFontToolbarFromSelection(e.newSelection || []);
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

    async function loadXML(xml, name = "diagrama.bpmn", handle = null) {{
      try {{
        clearError();
        elementFontStyles = {{}};
        updateFontToolbarFromSelection([]);
        await modeler.importXML(xml);
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

    // Abrir arquivo via File System Access API ou input fallback
    async function openFile() {{
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
          await loadXML(text, file.name, handle);
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

    // Salvar diretamente no arquivo
    async function saveFile() {{
      try {{
        const {{ xml }} = await modeler.saveXML({{ format: true }});
        if (currentFileHandle && currentFileHandle.createWritable) {{
          const writable = await currentFileHandle.createWritable();
          await writable.write(xml);
          await writable.close();
          setFileState(currentFileName, currentFileHandle, false);
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
            setFileState(handle.name, handle, false);
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

    // Mapa de estilos tipográficos específicos por elemento: elementId -> fontSize, isBold, isItalic
    function getSelectedElements() {{
      if (!modeler) return [];
      try {{
        const selection = modeler.get('selection').get();
        return selection || [];
      }} catch (e) {{
        return [];
      }}
    }}

    // Injeta/atualiza regras de estilo CSS específicas para os elementos estilizados
    function applyAllElementFontStyles() {{
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
      selection.forEach(el => {{
        if (!elementFontStyles[el.id]) {{
          elementFontStyles[el.id] = {{ fontSize: '12px', isBold: false, isItalic: false }};
        }}
        elementFontStyles[el.id].fontSize = val;
      }});
      applyAllElementFontStyles();
      showToast(`Tamanho da fonte (${{val}}) aplicado a ${{selection.length}} elemento(s).`);
    }}

    function toggleBold() {{
      const selection = getSelectedElements();
      if (selection.length === 0) {{
        showToast('Selecione um ou mais elementos para alternar negrito.');
        return;
      }}
      const allBold = selection.every(el => elementFontStyles[el.id] && elementFontStyles[el.id].isBold);
      const newBold = !allBold;
      selection.forEach(el => {{
        if (!elementFontStyles[el.id]) {{
          elementFontStyles[el.id] = {{ fontSize: '12px', isBold: false, isItalic: false }};
        }}
        elementFontStyles[el.id].isBold = newBold;
      }});
      btnFontBold.classList.toggle('active', newBold);
      applyAllElementFontStyles();
      showToast(`Negrito ${{newBold ? 'ativado' : 'desativado'}} em ${{selection.length}} elemento(s).`);
    }}

    function toggleItalic() {{
      const selection = getSelectedElements();
      if (selection.length === 0) {{
        showToast('Selecione um ou mais elementos para alternar itálico.');
        return;
      }}
      const allItalic = selection.every(el => elementFontStyles[el.id] && elementFontStyles[el.id].isItalic);
      const newItalic = !allItalic;
      selection.forEach(el => {{
        if (!elementFontStyles[el.id]) {{
          elementFontStyles[el.id] = {{ fontSize: '12px', isBold: false, isItalic: false }};
        }}
        elementFontStyles[el.id].isItalic = newItalic;
      }});
      btnFontItalic.classList.toggle('active', newItalic);
      applyAllElementFontStyles();
      showToast(`Itálico ${{newItalic ? 'ativado' : 'desativado'}} em ${{selection.length}} elemento(s).`);
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

    // Atalhos de teclado (Ctrl+O, Ctrl+S, Ctrl+Z, Ctrl+Y, Ctrl+F, Ctrl+B, Ctrl+I)
    window.addEventListener('keydown', (e) => {{
      const isCtrlOrMeta = e.ctrlKey || e.metaKey;
      if (isCtrlOrMeta && e.key.toLowerCase() === 's') {{
        e.preventDefault();
        saveFile();
      }} else if (isCtrlOrMeta && e.key.toLowerCase() === 'o') {{
        e.preventDefault();
        openFile();
      }} else if (isCtrlOrMeta && e.key.toLowerCase() === 'z' && !e.shiftKey) {{
        e.preventDefault();
        undoAction();
      }} else if (isCtrlOrMeta && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {{
        e.preventDefault();
        redoAction();
      }} else if (isCtrlOrMeta && e.key.toLowerCase() === 'f') {{
        e.preventDefault();
        toggleSearch();
      }} else if (isCtrlOrMeta && e.key.toLowerCase() === 'b') {{
        e.preventDefault();
        toggleBold();
      }} else if (isCtrlOrMeta && e.key.toLowerCase() === 'i') {{
        e.preventDefault();
        toggleItalic();
      }}
    }});

    // Carga inicial
    const urlParams = new URLSearchParams(window.location.search);
    const fileParam = urlParams.get('file');

    async function initEditor() {{
      applyDiagramFont();

      // 1. Se foi passado ?file=..., prioriza o arquivo solicitado
      if (fileParam) {{
        currentFileName = fileParam;
        setFileState(fileParam, null, false);

        // Se o arquivo solicitado corresponder ao diagrama padrão embutido, carrega diretamente (sem CORS)
        if (DEFAULT_DIAGRAM_NAME && fileParam === DEFAULT_DIAGRAM_NAME && DEFAULT_DIAGRAM_XML) {{
          await loadXML(DEFAULT_DIAGRAM_XML, DEFAULT_DIAGRAM_NAME, null);
          return;
        }}

        // Se corresponder a um dos presets embutidos, carrega do preset
        if (PRESETS[fileParam]) {{
          await loadXML(PRESETS[fileParam], fileParam, null);
          return;
        }}

        // Tenta fetch local
        try {{
          const res = await fetch(fileParam);
          if (res.ok) {{
            const xml = await res.text();
            await loadXML(xml, fileParam, null);
            return;
          }}
        }} catch (e) {{
          console.warn('Falha no fetch de arquivo local (possível CORS em file://):', e);
        }}
        showToast(`Arquivo '${{fileParam}}' configurado. Use '📂 Abrir' ou arraste o arquivo para carregar.`);
        return;
      }}

      // 2. Se há um diagrama padrão configurado para este editor (quando copiado no projeto)
      if (DEFAULT_DIAGRAM_NAME && DEFAULT_DIAGRAM_XML) {{
        await loadXML(DEFAULT_DIAGRAM_XML, DEFAULT_DIAGRAM_NAME, null);
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

def main():
    output_path = ROOT_DIR / "editor.html"
    output_path.write_text(html_content, encoding="utf-8")
    print(f"[OK] Generated central editor at: {output_path} ({len(html_content)} bytes)")


if __name__ == "__main__":
    main()
