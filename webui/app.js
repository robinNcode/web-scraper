const $ = selector => document.querySelector(selector);
let keyMap = {};

const esc = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Request failed');
  return result;
}

async function loadConfig() {
  const config = await api('/api/config');
  keyMap = config.keys;
  $('#provider').innerHTML = config.providers.map(provider =>
    `<option value="${provider}">${provider[0].toUpperCase() + provider.slice(1)}${provider === 'ollama' ? ' · local' : ''}</option>`
  ).join('');
  $('#keyProvider').innerHTML = config.providers.filter(provider => provider !== 'ollama').map(provider =>
    `<option value="${provider}">${provider[0].toUpperCase() + provider.slice(1)}</option>`
  ).join('');
  $('#provider').value = 'anthropic';
  providerNote();
  $('#keyStatus').innerHTML = config.providers.map(provider =>
    `<span class="key-chip ${config.keys[provider] ? '' : 'missing'}">${provider} ${config.keys[provider] ? 'configured' : 'not configured'}</span>`
  ).join('');
}

function providerNote() {
  $('#providerNote').textContent = keyMap[$('#provider').value]
    ? 'Key configured locally.'
    : 'No key configured. Add one in Settings.';
}

async function loadPapers() {
  const list = $('#paperList');
  try {
    const { papers } = await api('/api/papers');
    $('#paperCount').textContent = String(papers.length).padStart(2, '0');
    $('#navPaperCount').textContent = papers.length;
    list.innerHTML = papers.length
      ? papers.map(paper => `<div class="paper-row">
          <span class="paper-icon">▤</span>
          <a class="paper-name" href="/api/papers/${encodeURIComponent(paper.name)}" data-preview="${esc(paper.name)}" data-title="${esc(paper.title || paper.name)}" title="${esc(paper.path)}">${esc(paper.title || paper.name)}</a>
          <span class="paper-date">${esc(paper.modified)}</span>
        </div>`).join('')
      : '<div class="empty">No papers yet. Your finished analyses will show up here.</div>';
  } catch (error) {
    list.innerHTML = `<div class="empty">Could not load papers: ${esc(error.message)}</div>`;
  }
}

function inlineMd(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function renderMarkdown(markdown) {
  const lines = esc(markdown).replace(/\r/g, '').split('\n');
  const output = [];
  let paragraph = [];
  let list = '';
  let inCode = false;
  let codeLines = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      output.push(`<p>${inlineMd(paragraph.join('<br>'))}</p>`);
      paragraph = [];
    }
  };
  const endList = () => {
    if (list) {
      output.push(`</${list}>`);
      list = '';
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      flushParagraph();
      endList();
      if (inCode) {
        output.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
        codeLines = [];
      }
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      endList();
      continue;
    }

    let match;
    if ((match = line.match(/^(#{1,4})\s+(.+)$/))) {
      flushParagraph();
      endList();
      const level = match[1].length;
      output.push(`<h${level}>${inlineMd(match[2])}</h${level}>`);
    } else if (/^[-*_]{3,}\s*$/.test(line)) {
      flushParagraph();
      endList();
      output.push('<hr>');
    } else if ((match = line.match(/^\s*>\s?(.*)$/))) {
      flushParagraph();
      endList();
      output.push(`<blockquote>${inlineMd(match[1])}</blockquote>`);
    } else if ((match = line.match(/^\s*[-*+]\s+(.+)$/))) {
      flushParagraph();
      if (list !== 'ul') {
        endList();
        list = 'ul';
        output.push('<ul>');
      }
      output.push(`<li>${inlineMd(match[1])}</li>`);
    } else if ((match = line.match(/^\s*\d+[.)]\s+(.+)$/))) {
      flushParagraph();
      if (list !== 'ol') {
        endList();
        list = 'ol';
        output.push('<ol>');
      }
      output.push(`<li>${inlineMd(match[1])}</li>`);
    } else {
      endList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  endList();
  if (inCode) output.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
  return output.join('');
}

async function previewPaper(name, title = name) {
  const panel = $('#reader');
  panel.classList.remove('hidden');
  $('#readerTitle').textContent = title;
  $('#markdownBody').innerHTML = '<p>Loading preview…</p>';
  const href = `/api/papers/${encodeURIComponent(name)}`;
  $('#downloadPaper').href = `${href}?download=1`;
  $('#downloadPaper').download = name;
  try {
    const response = await fetch(href);
    if (!response.ok) {
      const result = await response.json();
      throw Error(result.error || 'Unable to load paper');
    }
    $('#markdownBody').innerHTML = renderMarkdown(await response.text());
  } catch (error) {
    $('#markdownBody').textContent = error.message;
  }
}

function setPage(path, updateHistory = false) {
  const isLibrary = path === '/library' || path === '/library/';
  $('#analysisPage').classList.toggle('hidden', isLibrary);
  $('#libraryPage').classList.toggle('hidden', !isLibrary);
  $('#newAnalysisNav').classList.toggle('active', !isLibrary);
  $('#libraryNav').classList.toggle('active', isLibrary);
  $('#crumbCurrent').textContent = isLibrary ? 'PAPER LIBRARY' : 'NEW ANALYSIS';
  $('#settingsToggle').classList.toggle('hidden', isLibrary);
  if (updateHistory) history.pushState({}, '', isLibrary ? '/library' : '/');
  if (isLibrary) loadPapers();
}

$('#runForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button = $('#runButton');
  const status = $('#status');
  button.disabled = true;
  status.className = 'status';
  $('#statusTitle').textContent = 'Preparing your analysis';
  $('#statusText').textContent = 'The engine is starting up.';
  const payload = {
    url: $('#url').value,
    provider: $('#provider').value,
    model: $('#model').value,
    max_chars: $('#maxChars').value,
    max_output_tokens: $('#maxTokens').value
  };
  try {
    const { id } = await api('/api/run', { method: 'POST', body: JSON.stringify(payload) });
    while (true) {
      const job = await api(`/api/jobs/${id}`);
      $('#statusTitle').textContent = job.stage;
      $('#statusText').textContent = job.status === 'done'
        ? `Saved ${job.path}`
        : job.status === 'error' ? job.error : 'This may take a moment.';
      if (job.status === 'done') {
        status.classList.add('success');
        await loadPapers();
        break;
      }
      if (job.status === 'error') {
        status.classList.add('error');
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
  } catch (error) {
    $('#statusTitle').textContent = 'Could not start';
    $('#statusText').textContent = error.message;
    status.classList.add('error');
  } finally {
    button.disabled = false;
  }
});

$('#advancedToggle').onclick = () => {
  const advanced = $('#advanced');
  const show = advanced.classList.contains('hidden');
  advanced.classList.toggle('hidden');
  $('#advancedToggle').textContent = show ? '− Advanced options' : '＋ Advanced options';
};
$('#clearUrl').onclick = () => {
  $('#url').value = '';
  $('#url').focus();
};
$('#provider').onchange = providerNote;
$('#settingsToggle').onclick = () => $('#settings').classList.toggle('hidden');
$('#closeSettings').onclick = () => $('#settings').classList.add('hidden');
$('#refreshPapers').onclick = loadPapers;

$('#saveKey').onclick = async () => {
  const feedback = $('#keyFeedback');
  feedback.textContent = 'Saving…';
  try {
    await api('/api/keys', {
      method: 'POST',
      body: JSON.stringify({ provider: $('#keyProvider').value, key: $('#apiKey').value })
    });
    $('#apiKey').value = '';
    feedback.textContent = 'Key saved to keys.json.';
    await loadConfig();
  } catch (error) {
    feedback.textContent = error.message;
  }
};

$('#paperList').addEventListener('click', event => {
  const link = event.target.closest('[data-preview]');
  if (link) {
    event.preventDefault();
    previewPaper(link.dataset.preview, link.dataset.title);
  }
});
$('#closeReader').onclick = () => $('#reader').classList.add('hidden');
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') $('#closeReader').click();
});

for (const link of [$('#newAnalysisNav'), $('#libraryNav')]) {
  link.addEventListener('click', event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setPage(link.getAttribute('href'), true);
  });
}
window.addEventListener('popstate', () => setPage(location.pathname));

setPage(location.pathname);
loadConfig().catch(error => console.error(error));
