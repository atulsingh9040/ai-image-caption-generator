/**
 * Frontend JavaScript for AI Image Caption Generator
 */

let selectedFile = null;
let currentCaptionResult = null;

// DOM Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const browseBtn = document.getElementById('browse-btn');
const dropZoneIdle = document.getElementById('drop-zone-idle');
const previewWrapper = document.getElementById('preview-wrapper');
const imagePreview = document.getElementById('image-preview');
const removeImgBtn = document.getElementById('remove-img-btn');
const analyzeBtn = document.getElementById('analyze-btn');
const btnSpinner = document.getElementById('spinner');
const btnText = document.getElementById('btn-text');

// AWS Status & Modal Elements
const awsStatusPill = document.getElementById('aws-status-pill');
const awsStatusText = document.getElementById('aws-status-text');
const openSettingsBtn = document.getElementById('open-settings-btn');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
const settingsModal = document.getElementById('settings-modal');
const awsConfigForm = document.getElementById('aws-config-form');

// Results Elements
const resultsEmpty = document.getElementById('results-empty');
const resultsContent = document.getElementById('results-content');
const primaryCaptionText = document.getElementById('primary-caption-text');
const shortCaptionBadge = document.getElementById('short-caption-badge');
const detailedDescriptionText = document.getElementById('detailed-description-text');
const labelsContainer = document.getElementById('labels-container');
const labelCount = document.getElementById('label-count');
const hashtagsText = document.getElementById('hashtags-text');
const detectedTextCard = document.getElementById('detected-text-card');
const detectedTextContainer = document.getElementById('detected-text-container');
const rawJsonViewer = document.getElementById('raw-json-viewer');
const analysisSourceBadge = document.getElementById('analysis-source-badge');

// Action Buttons
const copyCaptionBtn = document.getElementById('copy-caption-btn');
const copyHashtagsBtn = document.getElementById('copy-hashtags-btn');
const speakBtn = document.getElementById('speak-btn');

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  checkAWSStatus();
  setupEventListeners();
});

function setupEventListeners() {
  // File Browse
  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });
  dropZone.addEventListener('click', () => {
    if (!selectedFile) fileInput.click();
  });
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  // Drag and Drop
  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });
  dropZone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  // Paste Image from Clipboard
  window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let item of items) {
      if (item.type.indexOf('image') !== -1) {
        const blob = item.getAsFile();
        handleFileSelected(blob);
        showToast('Image pasted from clipboard!');
        break;
      }
    }
  });

  // Remove Image
  removeImgBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetUpload();
  });

  // Sample Images
  document.querySelectorAll('.sample-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.stopPropagation();
      loadSampleImage(chip.dataset.sample);
    });
  });

  // Analyze Button
  analyzeBtn.addEventListener('click', performAnalysis);

  // Modal Controls
  openSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
  closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
  cancelSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
  awsConfigForm.addEventListener('submit', handleSaveAWSConfig);

  // Copy Buttons
  copyCaptionBtn.addEventListener('click', () => {
    if (currentCaptionResult) {
      navigator.clipboard.writeText(currentCaptionResult.primary_caption);
      showToast('Caption copied to clipboard! 📋');
    }
  });
  copyHashtagsBtn.addEventListener('click', () => {
    if (currentCaptionResult && currentCaptionResult.hashtags) {
      navigator.clipboard.writeText(currentCaptionResult.hashtags.join(' '));
      showToast('Tags copied to clipboard! #️⃣');
    }
  });

  // Text-To-Speech (SpeechSynthesis)
  speakBtn.addEventListener('click', () => {
    if (!currentCaptionResult || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(currentCaptionResult.primary_caption);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
    showToast('🔊 Speaking caption...');
  });
}

function handleFileSelected(file) {
  if (!file.type.startsWith('image/')) {
    showToast('Please select a valid image file (PNG, JPG, WEBP).', 'error');
    return;
  }
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    imagePreview.src = e.target.result;
    dropZoneIdle.classList.add('hidden');
    previewWrapper.classList.remove('hidden');
    analyzeBtn.disabled = false;
  };
  reader.readAsDataURL(file);
}

function resetUpload() {
  selectedFile = null;
  fileInput.value = '';
  imagePreview.src = '';
  previewWrapper.classList.add('hidden');
  dropZoneIdle.classList.remove('hidden');
  analyzeBtn.disabled = true;
}

// Sample Image Generator (SVG Data URL)
function loadSampleImage(type) {
  const samples = {
    nature: {
      title: "Alpine Lake",
      color: "#22c55e",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#0284c7"/></linearGradient></defs><rect width="600" height="400" fill="url(#g)"/><polygon points="50,300 200,120 350,300" fill="#475569"/><polygon points="250,300 400,160 550,300" fill="#334155"/><rect y="280" width="600" height="120" fill="#047857"/><circle cx="500" cy="80" r="40" fill="#fef08a"/></svg>`
    },
    wildlife: {
      title: "Safari Lion",
      color: "#f59e0b",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400"><rect width="600" height="400" fill="#fbbf24"/><circle cx="300" cy="200" r="100" fill="#b45309"/><circle cx="300" cy="200" r="70" fill="#d97706"/><circle cx="270" cy="180" r="12" fill="#1e293b"/><circle cx="330" cy="180" r="12" fill="#1e293b"/><polygon points="300,210 285,230 315,230" fill="#1e293b"/><rect y="320" width="600" height="80" fill="#78350f"/></svg>`
    },
    city: {
      title: "Metropolis Skyline",
      color: "#6366f1",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400"><rect width="600" height="400" fill="#0f172a"/><rect x="80" y="140" width="80" height="260" fill="#334155"/><rect x="180" y="80" width="100" height="320" fill="#1e293b"/><rect x="300" y="160" width="90" height="240" fill="#334155"/><rect x="410" y="110" width="110" height="290" fill="#1e293b"/><circle cx="100" cy="60" r="30" fill="#f8fafc"/></svg>`
    },
    sports: {
      title: "Soccer Match",
      color: "#ec4899",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400"><rect width="600" height="400" fill="#15803d"/><circle cx="300" cy="200" r="80" fill="none" stroke="#fff" stroke-width="4"/><line x1="300" y1="0" x2="300" y2="400" stroke="#fff" stroke-width="4"/><circle cx="300" cy="200" r="35" fill="#f8fafc" stroke="#0f172a" stroke-width="3"/></svg>`
    }
  };

  const sample = samples[type] || samples.nature;
  const blob = new Blob([sample.svg], { type: 'image/svg+xml' });
  const file = new File([blob], `${type}-sample.svg`, { type: 'image/svg+xml' });
  handleFileSelected(file);
  showToast(`Loaded sample: ${sample.title}`);
}

async function checkAWSStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.aws_configured) {
      awsStatusPill.className = 'status-pill status-connected';
      awsStatusText.textContent = `AWS Active (${data.region})`;
    } else {
      awsStatusPill.className = 'status-pill status-demo';
      awsStatusText.textContent = 'Demo Mode (Add AWS Key)';
    }
  } catch (err) {
    awsStatusPill.className = 'status-pill status-demo';
    awsStatusText.textContent = 'Server Offline';
  }
}

async function handleSaveAWSConfig(e) {
  e.preventDefault();
  const keyId = document.getElementById('aws-key-id').value.trim();
  const secretKey = document.getElementById('aws-secret-key').value.trim();
  const region = document.getElementById('aws-region').value;

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        aws_access_key_id: keyId,
        aws_secret_access_key: secretKey,
        aws_region: region
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast('AWS Credentials saved successfully! ✅');
      settingsModal.classList.add('hidden');
      checkAWSStatus();
    } else {
      showToast(data.error || 'Failed to save credentials', 'error');
    }
  } catch (err) {
    showToast('Network error saving configuration', 'error');
  }
}

async function performAnalysis() {
  if (!selectedFile) return;

  setLoading(true);

  const formData = new FormData();
  formData.append('image', selectedFile);

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Failed to analyze image');
    }

    renderResults(data);
    showToast('Image analyzed successfully! ✨');
  } catch (error) {
    console.error('Analysis error:', error);
    showToast(error.message, 'error');
  } finally {
    setLoading(false);
  }
}

function renderResults(data) {
  currentCaptionResult = data;

  resultsEmpty.classList.add('hidden');
  resultsContent.classList.remove('hidden');

  // Source Badge
  if (data.source === 'aws_rekognition') {
    analysisSourceBadge.textContent = '⚡ AWS Rekognition';
    analysisSourceBadge.className = 'badge-aws';
    analysisSourceBadge.classList.remove('hidden');
  } else {
    analysisSourceBadge.textContent = 'ℹ️ Demo Simulation';
    analysisSourceBadge.className = 'badge status-demo';
    analysisSourceBadge.classList.remove('hidden');
  }

  // Primary Caption & Badge
  primaryCaptionText.textContent = data.primary_caption || 'No caption available.';
  shortCaptionBadge.textContent = data.short_caption || 'Analysis complete';

  // Detailed Description
  detailedDescriptionText.textContent = data.detailed_description || '';

  // Labels & Confidence
  labelsContainer.innerHTML = '';
  const labels = data.labels_summary || [];
  labelCount.textContent = `${labels.length} detected`;
  
  labels.forEach(l => {
    const pill = document.createElement('div');
    pill.className = 'label-pill';
    pill.innerHTML = `<span>${l.name}</span><span class="label-confidence">${l.confidence}%</span>`;
    labelsContainer.appendChild(pill);
  });

  // Detected Text (OCR)
  if (data.detected_text && data.detected_text.length > 0) {
    detectedTextCard.classList.remove('hidden');
    detectedTextContainer.innerHTML = data.detected_text.map(t => `<span class="label-pill">${t}</span>`).join(' ');
  } else {
    detectedTextCard.classList.add('hidden');
  }

  // Hashtags
  hashtagsText.textContent = (data.hashtags || []).join(' ');

  // Raw JSON
  rawJsonViewer.textContent = JSON.stringify(data, null, 2);

  // Notice alert if demo mode
  if (data.notice) {
    showToast(data.notice);
  }
}

function setLoading(isLoading) {
  if (isLoading) {
    analyzeBtn.disabled = true;
    btnSpinner.classList.remove('hidden');
    btnText.textContent = 'Analyzing with AWS...';
  } else {
    analyzeBtn.disabled = !selectedFile;
    btnSpinner.classList.add('hidden');
    btnText.textContent = '🚀 Analyze & Generate Caption';
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast';
  if (type === 'error') {
    toast.style.borderColor = '#ef4444';
    toast.style.color = '#fca5a5';
  }
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
