#!/usr/bin/env python3
"""
generate_editor_html.py
Generates the central editor.html in the root directory.
Includes File System Access API, Drag & Drop, Keyboard shortcuts, and embeds presets
so the editor works seamlessly under file:// protocol without CORS fetch blocks.
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
  html, body {{ height: 100%; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; overflow: hidden; }}

  #app-header {{
    height: 52px;
    background: var(--bg-header);
    border-bottom: 1px solid var(--bg-header-border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 12px;
    color: var(--text-light);
    user-select: none;
  }}

  .brand {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.3px;
    color: #38bdf8;
    margin-right: 8px;
  }}

  .brand svg {{
    width: 20px;
    height: 20px;
    fill: currentColor;
  }}

  .button-group {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  button, select {{
    background: var(--btn-secondary);
    color: var(--text-light);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.15s ease-in-out;
  }}

  button:hover {{
    background: var(--btn-secondary-hover);
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

  select {{
    padding-right: 28px;
    background-color: #1e293b;
    outline: none;
  }}

  .file-badge {{
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    background: #1e293b;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-muted);
    border: 1px solid rgba(255,255,255,0.05);
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
    height: calc(100% - 52px);
    width: 100%;
    background: #ffffff;
    position: relative;
  }}

  #error-banner {{
    display: none;
    position: absolute;
    top: 60px;
    left: 20px;
    right: 20px;
    background: #b91c1c;
    color: #ffffff;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 13px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    z-index: 1000;
    white-space: pre-wrap;
  }}

  #drop-overlay {{
    display: none;
    position: absolute;
    top: 52px;
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
  <div class="brand">
    <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
    BPMN Editor
  </div>

  <div class="button-group">
    <button id="btn-open" class="btn-primary" title="Abrir arquivo do computador (Ctrl+O)">
      📂 Abrir .bpmn
    </button>
    <button id="btn-save" class="btn-save" title="Salvar no mesmo arquivo do disco (Ctrl+S)">
      💾 Salvar
    </button>
    <button id="btn-save-as" title="Salvar como novo arquivo ou download">
      📥 Salvar Como...
    </button>
    <button id="btn-new" title="Criar novo diagrama em branco">
      ➕ Novo
    </button>
  </div>

  <div class="button-group" style="margin-left: 8px;">
    <select id="preset-select" title="Carregar um diagrama de teste ou exemplo">
      <option value="">-- Exemplos / Testes --</option>
      <option value="06-bus-boarding-process.bpmn">06. Ônibus Completo (4 Raias)</option>
      <option value="04-incident-management.bpmn">04. Gestão de Incidentes (2 Raias)</option>
      <option value="03-order-fulfillment.bpmn">03. Atendimento de Pedido (AND Split/Join)</option>
      <option value="02-credit-card-approval.bpmn">02. Cartão de Crédito (XOR Gateway)</option>
      <option value="01-user-onboarding.bpmn">01. Onboarding Linear</option>
      <option value="05-document-revision-cycle.bpmn">05. Revisão de Documentos (Loop)</option>
      <option value="example-complete.bpmn">Exemplo Referência (Expense Approval)</option>
    </select>
  </div>

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
  const PRESETS = {presets_json};

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

  if (typeof BpmnJS === 'undefined') {{
    showError('Não foi possível carregar a biblioteca bpmn-js do CDN. Verifique sua conexão com a internet.');
  }} else {{
    modeler = new BpmnJS({{
      container: '#canvas',
      keyboard: {{ bindTo: document }}
    }});

    // Listen for model changes to flag dirty state
    modeler.on('commandStack.changed', () => {{
      if (!isDirty) setFileState(currentFileName, currentFileHandle, true);
    }});

    async function loadXML(xml, name = "diagrama.bpmn", handle = null) {{
      try {{
        clearError();
        await modeler.importXML(xml);
        setFileState(name, handle, false);
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

    // Eventos da Toolbar
    document.getElementById('btn-open').addEventListener('click', openFile);
    document.getElementById('btn-save').addEventListener('click', saveFile);
    document.getElementById('btn-save-as').addEventListener('click', saveFileAs);
    document.getElementById('btn-new').addEventListener('click', newDiagram);

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

    // Atalhos de teclado (Ctrl+O, Ctrl+S)
    window.addEventListener('keydown', (e) => {{
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {{
        e.preventDefault();
        saveFile();
      }} else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {{
        e.preventDefault();
        openFile();
      }}
    }});

    // Carga inicial: carregar o teste 06 (ônibus completo) como padrão
    if (PRESETS['06-bus-boarding-process.bpmn']) {{
      loadXML(PRESETS['06-bus-boarding-process.bpmn'], '06-bus-boarding-process.bpmn', null);
    }} else {{
      newDiagram();
    }}
  }}
</script>
</body>
</html>
"""

output_path = ROOT_DIR / "editor.html"
output_path.write_text(html_content, encoding="utf-8")
print(f"[OK] Generated central editor at: {output_path} ({len(html_content)} bytes)")
