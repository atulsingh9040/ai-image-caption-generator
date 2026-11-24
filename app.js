/**
 * Lumina Studio — Client Controller
 * Multimodal Computer Vision & Captioning Engine
 */

let activeFile = null;
let activeEngine = 'openrouter';
let currentPayload = null;
let isAnalyzing = false;

// DOM Selectors
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const dropZoneIdle = document.getElementById('drop-zone-idle');
const previewFrame = document.getElementById('preview-frame');
const imagePreview = document.getElementById('image-preview');
const removeImgBtn = document.getElementById('remove-img-btn');
const imgDimPill = document.getElementById('img-dim-pill');
const imgSizePill = document.getElementById('img-size-pill');

const analyzeBtn = document.getElementById('analyze-btn');
const btnSpinner = document.getElementById('btn-spinner');
const btnLabel = document.getElementById('btn-label');

const systemStatusIndicator = document.getElementById('system-status-indicator');
const systemStatusLabel = document.getElementById('system-status-label');
const quickPingBtn = document.getElementById('quick-ping-btn');

// Inspector Results Elements
const inspectorEmpty = document.getElementById('inspector-empty');
const inspectorResults = document.getElementById('inspector-results');
const engineBadge = document.getElementById('engine-badge');
const latencyBadge = document.getElementById('latency-badge');

const primaryCaptionText = document.getElementById('primary-caption-text');
const shortCaptionChip = document.getElementById('short-caption-chip');
const detailedNarrativeText = document.getElementById('detailed-narrative-text');
const entitiesGrid = document.getElementById('entities-grid');
const entityCountBadge = document.getElementById('entity-count-badge');
const ocrCard = document.getElementById('ocr-card');
const ocrTagsContainer = document.getElementById('ocr-tags-container');
const tagsCluster = document.getElementById('tags-cluster');
const rawJsonCode = document.getElementById('raw-json-code');
const charCount = document.getElementById('char-count');
const wordCount = document.getElementById('word-count');

// Action Buttons
const copyCaptionBtn = document.getElementById('copy-caption-btn');
const speakCaptionBtn = document.getElementById('speak-caption-btn');
const copyTagsBtn = document.getElementById('copy-tags-btn');

// Settings Modal Selectors
const settingsBackdrop = document.getElementById('settings-backdrop');
const openSettingsModalBtn = document.getElementById('open-settings-modal-btn');
const closeModalX = document.getElementById('close-modal-x');
const closeModalBtn = document.getElementById('close-modal-btn');
const settingsForm = document.getElementById('settings-form');
const inputOpenrouterKey = document.getElementById('input-openrouter-key');
const toggleKeyVisibility = document.getElementById('toggle-key-visibility');
const testKeyBtn = document.getElementById('test-key-btn');
const testSpinner = document.getElementById('test-spinner');
const testBtnText = document.getElementById('test-btn-text');
const keyTestFeedback = document.getElementById('key-test-feedback');
const inputBackendUrl = document.getElementById('input-backend-url');
const inputAwsKeyId = document.getElementById('input-aws-key-id');
const inputAwsSecret = document.getElementById('input-aws-secret');
const selectAwsRegion = document.getElementById('select-aws-region');

// ── Initialization ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSavedSettings();
  initEventListeners();
  checkSystemStatus();
});

function getApiEndpoint(path) {
  const customHost = localStorage.getItem('lumina_backend_host');
  if (customHost) {
    return `${customHost.replace(/\/$/, '')}${path}`;
  }
  return path;
}

function loadSavedSettings() {
  const savedKey = localStorage.getItem('lumina_or_key') || '';
  const savedHost = localStorage.getItem('lumina_backend_host') || '';
  if (inputOpenrouterKey) inputOpenrouterKey.value = savedKey;
  if (inputBackendUrl) inputBackendUrl.value = savedHost;
}

// ── Event Handlers ───────────────────────────────────────────────────────────
function initEventListeners() {
  // File Upload Interactions
  dropZone.addEventListener('click', (e) => {
    if (!activeFile && e.target !== removeImgBtn) {
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      processSelectedImage(e.target.files[0]);
    }
  });

  // Drag and Drop
  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processSelectedImage(e.dataTransfer.files[0]);
    }
  });

  // Clipboard Paste Support (Ctrl/Cmd + V)
  window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items || [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const blob = item.getAsFile();
        processSelectedImage(blob);
        triggerToast('Image pasted from clipboard', 'info');
        break;
      }
    }
  });

  // Global Keyboard Shortcut: Ctrl/Cmd + Enter to trigger analysis
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      if (activeFile && !isAnalyzing) {
        e.preventDefault();
        executeImageAnalysis();
      }
    }
  });

  removeImgBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetMediaState();
  });

  // Engine Segment Selection
  document.querySelectorAll('.segment-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeEngine = btn.dataset.engine || 'openrouter';
    });
  });

  // Reference Sample Shelf
  document.querySelectorAll('.sample-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      generateReferenceSample(btn.dataset.sample);
    });
  });

  // Execution CTA
  analyzeBtn.addEventListener('click', executeImageAnalysis);

  // Results Actions
  copyCaptionBtn.addEventListener('click', () => {
    if (currentPayload?.primary_caption) {
      navigator.clipboard.writeText(currentPayload.primary_caption);
      triggerToast('Caption copied to clipboard', 'success');
    }
  });

  copyTagsBtn.addEventListener('click', () => {
    if (currentPayload?.hashtags?.length) {
      navigator.clipboard.writeText(currentPayload.hashtags.join(' '));
      triggerToast('Keywords copied to clipboard', 'success');
    }
  });

  speakCaptionBtn.addEventListener('click', () => {
    if (!currentPayload?.primary_caption || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(currentPayload.primary_caption);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
    triggerToast('Synthesizing speech audio...', 'info');
  });

  // Settings Modal Controls
  openSettingsModalBtn.addEventListener('click', () => settingsBackdrop.classList.remove('hidden'));
  closeModalX.addEventListener('click', () => settingsBackdrop.classList.add('hidden'));
  closeModalBtn.addEventListener('click', () => settingsBackdrop.classList.add('hidden'));
  settingsBackdrop.addEventListener('click', (e) => {
    if (e.target === settingsBackdrop) settingsBackdrop.classList.add('hidden');
  });

  toggleKeyVisibility.addEventListener('click', () => {
    const isPassword = inputOpenrouterKey.type === 'password';
    inputOpenrouterKey.type = isPassword ? 'text' : 'password';
  });

  testKeyBtn.addEventListener('click', () => {
    runKeyHandshakeTest(inputOpenrouterKey.value.trim());
  });

  quickPingBtn.addEventListener('click', () => {
    runKeyHandshakeTest(localStorage.getItem('lumina_or_key') || '');
  });

  settingsForm.addEventListener('submit', handleSaveSettings);
}

// ── Media Processing ────────────────────────────────────────────────────────
function processSelectedImage(file) {
  if (!file || !file.type.startsWith('image/')) {
    triggerToast('Please provide a valid image format (PNG, JPEG, WEBP)', 'error');
    return;
  }

  activeFile = file;
  const reader = new FileReader();

  reader.onload = (e) => {
    imagePreview.src = e.target.result;
    
    // Read Image Dimensions
    const imgObj = new Image();
    imgObj.onload = () => {
      imgDimPill.textContent = `${imgObj.naturalWidth} × ${imgObj.naturalHeight}`;
    };
    imgObj.src = e.target.result;

    // Size formatted
    const kb = (file.size / 1024).toFixed(1);
    imgSizePill.textContent = `${kb} KB`;

    dropZoneIdle.classList.add('hidden');
    previewFrame.classList.remove('hidden');
    analyzeBtn.disabled = false;
  };

  reader.readAsDataURL(file);
}

function resetMediaState() {
  activeFile = null;
  fileInput.value = '';
  imagePreview.src = '';
  previewFrame.classList.add('hidden');
  dropZoneIdle.classList.remove('hidden');
  analyzeBtn.disabled = true;
}

// ── Synthetic Reference Samples ─────────────────────────────────────────────
function generateReferenceSample(type) {
  const definitions = {
    alpine: {
      name: "Alpine Range",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500"><defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#334155"/></linearGradient><linearGradient id="mtn" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#94a3b8"/><stop offset="100%" stop-color="#475569"/></linearGradient></defs><rect width="800" height="500" fill="url(#sky)"/><circle cx="680" cy="90" r="35" fill="#fef08a" opacity="0.9"/><polygon points="40,420 280,140 520,420" fill="url(#mtn)"/><polygon points="340,420 540,190 760,420" fill="#334155"/><rect y="400" width="800" height="100" fill="#064e3b"/></svg>`
    },
    metropolis: {
      name: "Modern Metropolis",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500"><rect width="800" height="500" fill="#090d16"/><rect x="80" y="160" width="110" height="340" fill="#1e293b"/><rect x="220" y="80" width="140" height="420" fill="#334155"/><rect x="400" y="200" width="120" height="300" fill="#1e293b"/><rect x="560" y="120" width="150" height="380" fill="#2d3748"/><circle cx="120" cy="70" r="28" fill="#e2e8f0"/></svg>`
    },
    wildlife: {
      name: "Wildlife Profile",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500"><rect width="800" height="500" fill="#78350f"/><circle cx="400" cy="240" r="140" fill="#b45309"/><circle cx="400" cy="240" r="100" fill="#d97706"/><circle cx="360" cy="220" r="14" fill="#1c1917"/><circle cx="440" cy="220" r="14" fill="#1c1917"/><polygon points="400,260 380,290 420,290" fill="#1c1917"/><rect y="410" width="800" height="90" fill="#451a03"/></svg>`
    },
    athletics: {
      name: "Athletic Motion",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500"><rect width="800" height="500" fill="#047857"/><circle cx="400" cy="250" r="110" fill="none" stroke="#fff" stroke-width="4"/><line x1="400" y1="0" x2="400" y2="500" stroke="#fff" stroke-width="4"/><circle cx="400" cy="250" r="45" fill="#f8fafc" stroke="#0f172a" stroke-width="4"/></svg>`
    }
  };

  const sample = definitions[type] || definitions.alpine;
  const blob = new Blob([sample.svg], { type: 'image/svg+xml' });
  const sampleFile = new File([blob], `${type}-reference.svg`, { type: 'image/svg+xml' });
  processSelectedImage(sampleFile);
  triggerToast(`Loaded reference: ${sample.name}`, 'info');
}

// ── System Health & Key Validation ──────────────────────────────────────────
async function checkSystemStatus() {
  try {
    const res = await fetch(getApiEndpoint('/api/status'));
    const data = await res.json();
    
    if (data.openrouter_active || localStorage.getItem('lumina_or_key')) {
      systemStatusIndicator.className = 'status-indicator ready';
      systemStatusLabel.textContent = 'Vision Ready';
    } else if (data.aws_active) {
      systemStatusIndicator.className = 'status-indicator ready';
      systemStatusLabel.textContent = `AWS Active (${data.aws_region})`;
    } else {
      systemStatusIndicator.className = 'status-indicator demo';
      systemStatusLabel.textContent = 'Simulation Engine';
    }
  } catch (err) {
    systemStatusIndicator.className = 'status-indicator demo';
    systemStatusLabel.textContent = 'Standby Mode';
  }
}

async function runKeyHandshakeTest(keyToTest) {
  if (testSpinner) testSpinner.classList.remove('hidden');
  if (testBtnText) testBtnText.textContent = 'Testing...';
  if (keyTestFeedback) keyTestFeedback.classList.add('hidden');

  const targetKey = keyToTest || localStorage.getItem('lumina_or_key') || '';

  try {
    const res = await fetch(getApiEndpoint('/api/test-key'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: targetKey })
    });
    const data = await res.json();

    if (data.success) {
      triggerToast(`Handshake verified (${data.latency_ms}ms latency)`, 'success');
      if (keyTestFeedback) {
        keyTestFeedback.className = 'test-feedback success';
        keyTestFeedback.textContent = `✓ ${data.message}`;
        keyTestFeedback.classList.remove('hidden');
      }
      checkSystemStatus();
    } else {
      triggerToast(`Key validation rejected: ${data.message}`, 'error');
      if (keyTestFeedback) {
        keyTestFeedback.className = 'test-feedback error';
        keyTestFeedback.textContent = `✕ ${data.message}`;
        keyTestFeedback.classList.remove('hidden');
      }
    }
  } catch (err) {
    triggerToast('Network endpoint unreachable', 'error');
    if (keyTestFeedback) {
      keyTestFeedback.className = 'test-feedback error';
      keyTestFeedback.textContent = `✕ Network error: ${err.message}`;
      keyTestFeedback.classList.remove('hidden');
    }
  } finally {
    if (testSpinner) testSpinner.classList.add('hidden');
    if (testBtnText) testBtnText.textContent = 'Test Key';
  }
}

// ── Settings Form Submission ────────────────────────────────────────────────
async function handleSaveSettings(e) {
  e.preventDefault();
  const orKey = inputOpenrouterKey.value.trim();
  const backendHost = inputBackendUrl.value.trim();
  const awsKey = inputAwsKeyId.value.trim();
  const awsSec = inputAwsSecret.value.trim();
  const awsReg = selectAwsRegion.value;

  if (orKey) localStorage.setItem('lumina_or_key', orKey);
  else localStorage.removeItem('lumina_or_key');

  if (backendHost) localStorage.setItem('lumina_backend_host', backendHost);
  else localStorage.removeItem('lumina_backend_host');

  try {
    await fetch(getApiEndpoint('/api/config'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        openrouter_api_key: orKey,
        aws_access_key_id: awsKey,
        aws_secret_access_key: awsSec,
        aws_region: awsReg
      })
    });
  } catch (err) {
    // Non-fatal if offline
  }

  triggerToast('Preferences committed to storage', 'success');
  settingsBackdrop.classList.add('hidden');
  checkSystemStatus();
}

// ── Inference Execution ─────────────────────────────────────────────────────
async function executeImageAnalysis() {
  if (!activeFile || isAnalyzing) return;

  setAnalyzingState(true);

  const formData = new FormData();
  formData.append('image', activeFile);
  formData.append('engine', activeEngine);

  const customKey = localStorage.getItem('lumina_or_key') || '';
  const headers = {};
  if (customKey) {
    headers['X-OpenRouter-Key'] = customKey;
  }

  try {
    const response = await fetch(getApiEndpoint('/api/analyze'), {
      method: 'POST',
      headers,
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Computer vision pipeline failed');
    }

    renderSemanticResults(data);
    triggerToast('Inference generated successfully', 'success');
  } catch (error) {
    console.error('Vision analysis failure:', error);
    triggerToast(error.message, 'error');
  } finally {
    setAnalyzingState(false);
  }
}

function renderSemanticResults(data) {
  currentPayload = data;

  inspectorEmpty.classList.add('hidden');
  inspectorResults.classList.remove('hidden');

  // Engine & Performance Badges
  engineBadge.textContent = data.engine_name || (data.source === 'openrouter' ? 'Llama 3.2 Vision' : 'Vision Engine');
  engineBadge.classList.remove('hidden');

  if (data.latency_ms) {
    latencyBadge.textContent = `${data.latency_ms}ms`;
    latencyBadge.classList.remove('hidden');
  } else {
    latencyBadge.classList.add('hidden');
  }

  // Primary Editorial Caption
  const caption = data.primary_caption || 'No caption generated.';
  primaryCaptionText.textContent = caption;

  // Word & Character Analytics
  const words = caption.trim().split(/\s+/).filter(Boolean).length;
  charCount.textContent = `${caption.length} characters`;
  wordCount.textContent = `${words} words`;

  // Headline Chip
  shortCaptionChip.textContent = data.short_caption || 'Visual Analysis';

  // Scene Narrative
  detailedNarrativeText.textContent = data.detailed_description || 'Detailed narrative unavailable.';

  // Entity Confidence Matrix
  entitiesGrid.innerHTML = '';
  const labels = data.labels_summary || [];
  entityCountBadge.textContent = `${labels.length} items`;

  labels.forEach(item => {
    const score = Number(item.confidence || 0).toFixed(1);
    const chip = document.createElement('div');
    chip.className = 'entity-chip';
    chip.innerHTML = `
      <div class="entity-label-row">
        <span class="entity-name" title="${item.name}">${item.name}</span>
        <span class="entity-score">${score}%</span>
      </div>
      <div class="meter-track">
        <div class="meter-fill" style="width: ${Math.min(score, 100)}%;"></div>
      </div>
    `;
    entitiesGrid.appendChild(chip);
  });

  // Extracted Optical Text (OCR)
  if (data.detected_text && data.detected_text.length > 0) {
    ocrCard.classList.remove('hidden');
    ocrTagsContainer.innerHTML = data.detected_text.map(t => `<span class="ocr-chip">${escapeHtml(t)}</span>`).join('');
  } else {
    ocrCard.classList.add('hidden');
  }

  // Tags & Keywords
  tagsCluster.innerHTML = '';
  const tags = data.hashtags || [];
  tags.forEach(tag => {
    const pill = document.createElement('span');
    pill.className = 'tag-pill';
    pill.textContent = tag;
    pill.addEventListener('click', () => {
      navigator.clipboard.writeText(tag);
      triggerToast(`Copied ${tag}`, 'info');
    });
    tagsCluster.appendChild(pill);
  });

  // Raw Developer JSON Payload
  rawJsonCode.textContent = JSON.stringify(data, null, 2);
}

function setAnalyzingState(busy) {
  isAnalyzing = busy;
  if (busy) {
    analyzeBtn.disabled = true;
    btnSpinner.classList.remove('hidden');
    btnLabel.textContent = 'Processing Inference...';
  } else {
    analyzeBtn.disabled = !activeFile;
    btnSpinner.classList.add('hidden');
    btnLabel.textContent = 'Execute Analysis';
  }
}

// ── UI Micro-Utilities ──────────────────────────────────────────────────────
function triggerToast(message, type = 'info') {
  const deck = document.getElementById('toast-deck');
  if (!deck) return;

  const pill = document.createElement('div');
  pill.className = `toast-pill ${type}`;
  pill.textContent = message;

  deck.appendChild(pill);

  setTimeout(() => {
    pill.style.opacity = '0';
    pill.style.transform = 'translateY(6px)';
    pill.style.transition = 'all 0.2s ease';
    setTimeout(() => pill.remove(), 200);
  }, 3400);
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
