/* global monaco: false */

// ───────────────────────────────────────────────
// State
// ───────────────────────────────────────────────
let editor = null;
let openTabs = [];       // { path, name, model }
let activeTab = null;
let allFunctions = [];   // full list from /api/functions
let fileFunctions = [];  // functions for currently open file
let activeFunc = null;   // currently selected function
let decorations = [];    // monaco decoration IDs

// ───────────────────────────────────────────────
// Monaco bootstrap
// ───────────────────────────────────────────────
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });

require(['vs/editor/editor.main'], function () {
    editor = monaco.editor.create(document.getElementById('monaco-container'), {
        theme: 'vs-dark',
        language: 'plaintext',
        readOnly: true,
        fontSize: 13,
        fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
        fontLigatures: true,
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        renderLineHighlight: 'gutter',
        smoothScrolling: true,
        cursorBlinking: 'phase',
        automaticLayout: true,
    });

    // Click on gutter / line → select matching function
    editor.onMouseDown(e => {
        const line = e.target.position ? e.target.position.lineNumber : null;
        if (!line) return;
        const fn = fileFunctions.find(f =>
            line >= (f.line_start || f.line_start) && line <= f.line_end
        );
        if (fn) selectFunction(fn);
    });

    // Initial load
    loadFunctions().then(loadTree);
});

// ───────────────────────────────────────────────
// API helpers
// ───────────────────────────────────────────────
async function apiFetch(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function loadFunctions() {
    try {
        allFunctions = await apiFetch('/api/functions');
        updateStatus(`${allFunctions.length} functions indexed`);
    } catch (e) {
        console.warn('loadFunctions:', e);
        allFunctions = [];
    }
}

// ───────────────────────────────────────────────
// File Tree
// ───────────────────────────────────────────────
async function loadTree() {
    const container = document.getElementById('file-tree');
    container.innerHTML = '<div style="padding:8px 12px;color:#6c7086;font-size:11px">Loading…</div>';
    try {
        const tree = await apiFetch('/api/tree');
        container.innerHTML = '';
        if (tree.error) {
            container.innerHTML = `<div class="info-empty">${tree.error}</div>`;
            return;
        }
        if (tree.children) {
            tree.children.forEach(node => container.appendChild(buildTreeNode(node, 1)));
        } else if (tree.type === 'file') {
            container.appendChild(buildTreeNode(tree, 1));
        }
    } catch (e) {
        container.innerHTML = `<div class="info-empty">No data.<br>Run <b>legacylens index</b> first.</div>`;
    }
}

function buildTreeNode(node, depth) {
    const indent = depth * 14;
    if (node.type === 'file') {
        const el = document.createElement('div');
        el.className = 'tree-file';
        el.style.paddingLeft = indent + 'px';
        el.innerHTML = `<span class="tree-icon">📄</span><span class="tree-name">${node.name}</span>`;
        el.dataset.path = node.path;
        el.title = node.path;
        el.addEventListener('click', () => openFile(node.path, node.name, el));
        return el;
    }
    // Directory
    const wrap = document.createElement('div');
    const header = document.createElement('div');
    header.className = 'tree-dir';
    header.style.paddingLeft = indent + 'px';
    const caret = document.createElement('span');
    caret.className = 'tree-caret';
    caret.textContent = '▶';
    header.appendChild(caret);
    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = '📁';
    header.appendChild(icon);
    const name = document.createElement('span');
    name.className = 'tree-name';
    name.textContent = node.name;
    header.appendChild(name);
    wrap.appendChild(header);

    const children = document.createElement('div');
    children.className = 'tree-children';
    (node.children || []).forEach(child => children.appendChild(buildTreeNode(child, depth + 1)));
    wrap.appendChild(children);

    header.addEventListener('click', () => {
        const open = children.classList.toggle('open');
        caret.classList.toggle('open', open);
        icon.textContent = open ? '📂' : '📁';
    });
    return wrap;
}

// ───────────────────────────────────────────────
// Open File
// ───────────────────────────────────────────────
async function openFile(path, name, treeEl) {
    // Highlight active tree item
    document.querySelectorAll('.tree-file.active').forEach(el => el.classList.remove('active'));
    if (treeEl) treeEl.classList.add('active');

    // Check if tab already open
    let tab = openTabs.find(t => t.path === path);
    if (!tab) {
        try {
            const data = await apiFetch(`/api/file?path=${encodeURIComponent(path)}`);
            const model = monaco.editor.createModel(data.content, data.language);
            tab = { path, name, model };
            openTabs.push(tab);
            renderTabs();
        } catch (e) {
            updateStatus('Error loading file: ' + e.message, true);
            return;
        }
    }
    activateTab(tab);

    // Load functions for this file
    fileFunctions = allFunctions.filter(f => f.file === path);
    applyDecorations();
    renderFuncList();
    clearInfoSelected();
    updateStatus(`${name}  —  ${fileFunctions.length} functions`);
}

// ───────────────────────────────────────────────
// Tabs
// ───────────────────────────────────────────────
function renderTabs() {
    const bar = document.getElementById('editor-tabs');
    bar.innerHTML = '';
    openTabs.forEach(tab => {
        const el = document.createElement('div');
        el.className = 'tab' + (tab === activeTab ? ' active' : '');
        el.innerHTML = `<span>${tab.name}</span><span class="tab-close" title="Close">✕</span>`;
        el.querySelector('span').addEventListener('click', () => activateTab(tab));
        el.querySelector('.tab-close').addEventListener('click', e => {
            e.stopPropagation();
            closeTab(tab);
        });
        bar.appendChild(el);
    });

    // Show/hide placeholder
    const ph = document.getElementById('editor-placeholder');
    const mc = document.getElementById('monaco-container');
    if (openTabs.length === 0) {
        ph.style.display = 'flex';
        mc.style.display = 'none';
    } else {
        ph.style.display = 'none';
        mc.style.display = 'block';
    }
}

function activateTab(tab) {
    activeTab = tab;
    editor.setModel(tab.model);
    renderTabs();
}

function closeTab(tab) {
    openTabs = openTabs.filter(t => t !== tab);
    tab.model.dispose();
    if (activeTab === tab) {
        activeTab = openTabs[openTabs.length - 1] || null;
        if (activeTab) editor.setModel(activeTab.model);
    }
    renderTabs();
    if (openTabs.length === 0) {
        fileFunctions = [];
        renderFuncList();
        clearInfoSelected();
        updateStatus('No file open');
    }
}

// ───────────────────────────────────────────────
// Monaco Decorations (function highlights)
// ───────────────────────────────────────────────
function applyDecorations() {
    if (!editor) return;
    const newDecorations = fileFunctions.map(fn => ({
        range: new monaco.Range(fn.line_start, 1, fn.line_end, 1),
        options: {
            isWholeLine: false,
            linesDecorationsClassName: scoreToClass(fn),
            overviewRuler: {
                color: scoreToColor(fn),
                position: monaco.editor.OverviewRulerLane.Left,
            },
            minimap: { color: scoreToColor(fn), position: monaco.editor.MinimapPosition.Inline },
        }
    }));
    decorations = editor.deltaDecorations(decorations, newDecorations);
}

function scoreToClass(fn) {
    const worst = Math.max(fn.energy || 0, fn.debt || 0);
    if (worst >= 7) return 'deco-danger';
    if (worst >= 4) return 'deco-warn';
    return 'deco-ok';
}

function scoreToColor(fn) {
    const worst = Math.max(fn.energy || 0, fn.debt || 0);
    if (worst >= 7) return '#f87171';
    if (worst >= 4) return '#fbbf24';
    return '#34d399';
}

// ───────────────────────────────────────────────
// Function list + selection
// ───────────────────────────────────────────────
function renderFuncList() {
    const content = document.getElementById('info-content');
    if (fileFunctions.length === 0) {
        content.innerHTML = '<div class="info-empty">Click a file in the<br>tree to explore it.<br><br>Functions will appear here.</div>';
        return;
    }

    let html = `<div class="func-list-title">Functions (${fileFunctions.length})</div>`;
    fileFunctions.forEach((fn, i) => {
        const dotClass = scoreToClass(fn).replace('deco-', 'dot-');
        const dotColor = dotClass.includes('danger') ? 'dot-red' : dotClass.includes('warn') ? 'dot-yellow' : 'dot-green';
        const shortName = fn.name.split('.').pop();
        html += `
      <div class="func-item" data-idx="${i}" title="${fn.name}">
        <span class="fi-name">${shortName}</span>
        <div style="display:flex;align-items:center;gap:4px">
          <span class="fi-lines">${fn.line_start}–${fn.line_end}</span>
          <span class="dot ${dotColor}"></span>
        </div>
      </div>`;
    });
    content.innerHTML = html;
    content.querySelectorAll('.func-item').forEach(el => {
        el.addEventListener('click', () => {
            const fn = fileFunctions[+el.dataset.idx];
            selectFunction(fn);
        });
    });
}

function selectFunction(fn) {
    activeFunc = fn;

    // Highlight in editor
    editor.revealLinesInCenter(fn.line_start, fn.line_end);
    editor.setSelection(new monaco.Range(fn.line_start, 1, fn.line_end + 1, 1));

    // Mark active in func list
    document.querySelectorAll('.func-item').forEach((el, i) => {
        el.classList.toggle('active', fileFunctions[i] === fn);
    });

    renderInfoPanel(fn);
}

// ───────────────────────────────────────────────
// Info Panel
// ───────────────────────────────────────────────
function renderInfoPanel(fn) {
    const content = document.getElementById('info-content');
    const shortName = fn.name.split('.').pop();
    const relFile = fn.file.split('/').slice(-2).join('/');

    const gradeE = scoreGrade(fn.energy);
    const gradeD = scoreGrade(fn.debt);
    const gradeS = scoreGrade(fn.safety);

    // Func list below scores
    let funcListHtml = `<div class="func-list-title" style="margin-top:16px">Functions (${fileFunctions.length})</div>`;
    fileFunctions.forEach((f, i) => {
        const dotColor = scoreToClass(f).includes('danger') ? 'dot-red'
            : scoreToClass(f).includes('warn') ? 'dot-yellow' : 'dot-green';
        const sn = f.name.split('.').pop();
        funcListHtml += `
      <div class="func-item ${f === fn ? 'active' : ''}" data-idx="${i}" title="${f.name}">
        <span class="fi-name">${sn}</span>
        <div style="display:flex;align-items:center;gap:4px">
          <span class="fi-lines">${f.line_start}–${f.line_end}</span>
          <span class="dot ${dotColor}"></span>
        </div>
      </div>`;
    });

    content.innerHTML = `
    <div class="info-func-name">${shortName}</div>
    <div class="info-file">…/${relFile}  L${fn.line_start}–${fn.line_end}</div>
    <div class="scores-grid">
      <div class="score-card">
        <div class="sc-label">⚡ Energy</div>
        <div class="sc-value sc-energy">${fn.energy ?? '–'}</div>
        <div class="sc-label">${gradeE}</div>
      </div>
      <div class="score-card">
        <div class="sc-label">🔧 Debt</div>
        <div class="sc-value sc-debt">${fn.debt ?? '–'}</div>
        <div class="sc-label">${gradeD}</div>
      </div>
      <div class="score-card">
        <div class="sc-label">🛡 Safety</div>
        <div class="sc-value sc-safety">${fn.safety ?? '–'}</div>
        <div class="sc-label">${gradeS}</div>
      </div>
    </div>
    ${funcListHtml}
  `;

    // Re-attach func list listeners
    content.querySelectorAll('.func-item').forEach(el => {
        el.addEventListener('click', () => selectFunction(fileFunctions[+el.dataset.idx]));
    });
}

function clearInfoSelected() {
    activeFunc = null;
    renderFuncList();
}

function scoreGrade(v) {
    if (v == null) return '';
    if (v <= 3) return '✓ Good';
    if (v <= 6) return '~ Fair';
    return '✗ High';
}

// ───────────────────────────────────────────────
// Status bar
// ───────────────────────────────────────────────
function updateStatus(msg, isError = false) {
    const el = document.getElementById('status-msg');
    if (el) { el.textContent = msg; el.style.color = isError ? '#f87171' : '#fff'; }
}
