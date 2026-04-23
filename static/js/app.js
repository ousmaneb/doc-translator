// ── Upload page state ─────────────────────────────────────────────────────────
let selectedFile = null;
let currentFormat = 'pdf';

const LANG = { en: 'English', fr: 'French' };
const STEPS = [
  'Uploading document…',
  'Extracting text…',
  'Detecting language…',
  'Translating…',
  'Building output file…',
];

// ── File selection ────────────────────────────────────────────────────────────
const fileInput = document.getElementById('file-upload-input');
const dropZone = document.getElementById('drop-zone');

fileInput?.addEventListener('change', (e) => {
  const f = e.target.files?.[0];
  if (f) applyFile(f);
});

dropZone?.addEventListener('dragover', (e) => e.preventDefault());
dropZone?.addEventListener('drop', (e) => {
  e.preventDefault();
  const f = e.dataTransfer.files?.[0];
  if (f) applyFile(f);
});

function applyFile(file) {
  selectedFile = file;

  const empty = document.getElementById('drop-zone-empty');
  const selected = document.getElementById('drop-zone-selected');
  if (empty && selected) {
    empty.classList.add('hidden');
    selected.classList.remove('hidden');
    const nameEl = document.getElementById('selected-filename');
    const sizeEl = document.getElementById('selected-filesize');
    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = `${(file.size / 1024).toFixed(0)} KB · Tap to change`;
  }

  const btn = document.getElementById('translate-btn');
  if (btn) btn.disabled = false;

  const errDiv = document.getElementById('upload-error');
  if (errDiv) errDiv.classList.add('hidden');
}

// ── Format selection ──────────────────────────────────────────────────────────
function setFormat(fmt) {
  currentFormat = fmt;
  document.querySelectorAll('.fmt-btn').forEach((btn) => {
    const isActive = btn.dataset.fmt === fmt;
    btn.classList.toggle('border-indigo-500', isActive);
    btn.classList.toggle('bg-indigo-500/10', isActive);
    btn.classList.toggle('text-indigo-300', isActive);
    btn.classList.toggle('border-slate-700', !isActive);
    btn.classList.toggle('text-slate-400', !isActive);
  });
}

// ── Translation ───────────────────────────────────────────────────────────────
async function handleTranslate() {
  if (!selectedFile) return;

  const btn = document.getElementById('translate-btn');
  const progressArea = document.getElementById('progress-area');
  const progressText = document.getElementById('progress-text');
  const progressBar = document.getElementById('progress-bar');
  const errDiv = document.getElementById('upload-error');
  const resultsSection = document.getElementById('results-section');

  if (errDiv) errDiv.classList.add('hidden');
  if (resultsSection) resultsSection.classList.add('hidden');
  if (btn) { btn.disabled = true; btn.textContent = 'Processing…'; }
  if (progressArea) progressArea.classList.remove('hidden');

  // Animate progress steps
  let step = 0;
  if (progressText) progressText.textContent = STEPS[0];
  if (progressBar) progressBar.style.width = '20%';

  const ticker = setInterval(() => {
    step = Math.min(step + 1, STEPS.length - 1);
    if (progressText) progressText.textContent = STEPS[step];
    if (progressBar) progressBar.style.width = `${((step + 1) / STEPS.length) * 100}%`;
  }, 1600);

  try {
    const form = new FormData();
    form.append('file', selectedFile);
    form.append('output_format', currentFormat);

    const res = await fetch('/api/upload', { method: 'POST', body: form });
    clearInterval(ticker);

    if (!res.ok) {
      const b = await res.json();
      showError(b.detail || b.error || 'Upload failed');
      return;
    }

    const data = await res.json();
    showResult(data);
  } catch (err) {
    clearInterval(ticker);
    showError(err.message || 'An error occurred');
  } finally {
    if (progressArea) progressArea.classList.add('hidden');
    if (btn) { btn.disabled = false; btn.textContent = 'Translate now →'; }
  }
}

function showError(msg) {
  const errDiv = document.getElementById('upload-error');
  const errMsg = document.getElementById('upload-error-msg');
  if (errMsg) errMsg.textContent = msg;
  if (errDiv) errDiv.classList.remove('hidden');
}

function showResult(data) {
  const src = LANG[data.sourceLang] ?? data.sourceLang;
  const tgt = LANG[data.targetLang] ?? data.targetLang;

  document.getElementById('result-source-lang').textContent = src;
  document.getElementById('result-target-lang').textContent = tgt;
  document.getElementById('original-label').textContent = `Original (${src})`;
  document.getElementById('translated-label').textContent = `Translated (${tgt}) · ${data.outputFormat?.toUpperCase()}`;
  document.getElementById('original-download').href = data.originalUrl;
  document.getElementById('translated-download').href = data.translatedUrl;

  // Original preview
  const origContainer = document.getElementById('original-preview-container');
  const ext = (data.inputType || '').toLowerCase();
  if (origContainer) {
    if (ext === 'pdf') {
      origContainer.innerHTML = `<iframe src="${data.originalUrl}" class="w-full h-64 sm:h-80 rounded-xl border border-slate-200"></iframe>`;
    } else if (['png', 'jpg', 'jpeg'].includes(ext)) {
      origContainer.innerHTML = `<img src="${data.originalUrl}" alt="Document" class="w-full h-64 sm:h-80 object-contain rounded-xl border border-slate-200 bg-slate-50" />`;
    } else {
      origContainer.innerHTML = `<p class="text-sm text-slate-400 italic py-4">Original ${ext.toUpperCase()} file</p>`;
    }
  }

  // Translated preview
  const pdfPreview = document.getElementById('translated-pdf-preview');
  const textPreview = document.getElementById('translated-text-preview');
  const textContent = document.getElementById('translated-text-content');

  if (data.outputFormat === 'pdf' && pdfPreview) {
    pdfPreview.innerHTML = `<iframe src="${data.translatedUrl}" class="w-full h-64 sm:h-80 rounded-xl border border-slate-200"></iframe>`;
  }

  if (data.translatedPreview && textContent) {
    textContent.textContent = data.translatedPreview + (data.translatedPreview.length >= 800 ? ' …' : '');
    if (textPreview) textPreview.classList.remove('hidden');
  }

  const resultsSection = document.getElementById('results-section');
  if (resultsSection) {
    resultsSection.classList.remove('hidden');
    setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  }
}

function resetTranslation() {
  selectedFile = null;
  const resultsSection = document.getElementById('results-section');
  if (resultsSection) resultsSection.classList.add('hidden');

  const empty = document.getElementById('drop-zone-empty');
  const selected = document.getElementById('drop-zone-selected');
  if (empty) empty.classList.remove('hidden');
  if (selected) selected.classList.add('hidden');

  const btn = document.getElementById('translate-btn');
  if (btn) btn.disabled = true;

  const fi = document.getElementById('file-upload-input');
  if (fi) fi.value = '';

  window.scrollTo({ top: 0, behavior: 'smooth' });
}
