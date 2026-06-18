// ==UserScript==
// @name         Projet Voltaire - Correcteur Local Pro
// @namespace    local.voltaire.helper
// @version      4.0.0
// @description  Lit la phrase Projet Voltaire et demande au backend local s'il y a une faute (koboldcpp ou Reverso).
// @match        projet-voltaire.fr/*
// @match        *.projet-voltaire.fr/*
// @connect      127.0.0.1
// @connect      localhost
// @grant        GM_xmlhttpRequest
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const SERVER = 'http://127.0.0.1:8765/check';
  const POLL_MS = 650;
  const STORAGE_POS = 'voltaire-helper-panel-position-v1';
  let running = false;
  let collapsed = false;
  let lastVisibleSignature = '';
  let lastPhrase = '';
  let errorBackoffPhrase = '';
  let errorBackoffUntil = 0;
  let busy = false;
  let requestSeq = 0;

  function isVoltairePage() {
    return /voltaire|projet/i.test(location.href + ' ' + document.title + ' ' + (document.body && document.body.innerText || ''));
  }

  function loadPosition() {
    try { return JSON.parse(localStorage.getItem(STORAGE_POS) || 'null'); }
    catch (_) { return null; }
  }

  function savePosition(left, top) {
    try { localStorage.setItem(STORAGE_POS, JSON.stringify({ left, top })); }
    catch (_) {}
  }

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function makeDraggable(panel, header) {
    let dragging = false;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;

    header.addEventListener('pointerdown', (e) => {
      if (e.target && e.target.closest && e.target.closest('button')) return;
      if (e.button !== 0) return;
      dragging = true;
      panel.setPointerCapture && panel.setPointerCapture(e.pointerId);
      const r = panel.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      startLeft = r.left;
      startTop = r.top;
      panel.style.right = 'auto';
      panel.style.bottom = 'auto';
      panel.style.left = startLeft + 'px';
      panel.style.top = startTop + 'px';
      header.style.cursor = 'grabbing';
      e.preventDefault();
    });

    window.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const w = panel.offsetWidth || 390;
      const h = panel.offsetHeight || 180;
      const left = clamp(startLeft + e.clientX - startX, 0, window.innerWidth - Math.min(80, w));
      const top = clamp(startTop + e.clientY - startY, 0, window.innerHeight - 40);
      panel.style.left = left + 'px';
      panel.style.top = top + 'px';
      e.preventDefault();
    }, true);

    window.addEventListener('pointerup', () => {
      if (!dragging) return;
      dragging = false;
      header.style.cursor = 'grab';
      const r = panel.getBoundingClientRect();
      savePosition(Math.round(r.left), Math.round(r.top));
    }, true);
  }

  function ensurePanel(force) {
    if (!force && !isVoltairePage()) return null;
    let panel = document.getElementById('voltaire-reverso-helper-panel');
    if (panel) return panel;

    panel = document.createElement('div');
    panel.id = 'voltaire-reverso-helper-panel';
    panel.style.cssText = [
      'position:fixed',
      'right:14px',
      'bottom:14px',
      'z-index:2147483647',
      'width:430px',
      'max-width:calc(100vw - 28px)',
      'max-height:70vh',
      'font-family:Arial, sans-serif',
      'font-size:14px',
      'line-height:1.35',
      'background:#111827',
      'color:white',
      'border:2px solid #374151',
      'border-radius:12px',
      'box-shadow:0 12px 35px rgba(0,0,0,.35)',
      'white-space:normal',
      'overflow:hidden',
    ].join(';');

    const pos = loadPosition();
    if (pos && Number.isFinite(pos.left) && Number.isFinite(pos.top)) {
      panel.style.left = clamp(pos.left, 0, window.innerWidth - 80) + 'px';
      panel.style.top = clamp(pos.top, 0, window.innerHeight - 40) + 'px';
      panel.style.right = 'auto';
      panel.style.bottom = 'auto';
    }

    const header = document.createElement('div');
    header.className = 'vh-header';
    header.style.cssText = [
      'cursor:grab',
      'user-select:none',
      'padding:9px 10px',
      'font-weight:700',
      'background:rgba(255,255,255,.08)',
      'display:flex',
      'justify-content:space-between',
      'align-items:center',
      'gap:8px',
    ].join(';');

    const title = document.createElement('span');
    title.textContent = 'Voltaire Helper';
    title.style.cssText = 'white-space:nowrap';

    const controls = document.createElement('div');
    controls.style.cssText = 'display:flex;align-items:center;gap:6px';

    const startBtn = document.createElement('button');
    startBtn.type = 'button';
    startBtn.className = 'vh-start';
    startBtn.style.cssText = 'cursor:pointer;border:1px solid #94a3b8;border-radius:8px;background:#f8fafc;color:#111827;padding:5px 8px;font-weight:700;font-size:12px';
    startBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      running = !running;
      lastVisibleSignature = '';
      updatePanelHeader();
      if (running) {
        collapsed = false;
        updatePanelHeader();
        setPanel('<b>Script démarré.</b><div style="margin-top:6px;opacity:.8">Analyse manuelle en cours...</div>', 'busy');
        tick('manual');
      } else {
        setPanel('<b>Script arrêté.</b><div style="margin-top:6px;opacity:.8">Clique sur Démarrer quand tu veux vérifier la phrase affichée.</div>', 'wait');
      }
    });

    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'vh-toggle';
    toggleBtn.style.cssText = 'cursor:pointer;border:1px solid #94a3b8;border-radius:8px;background:#111827;color:#f8fafc;padding:5px 8px;font-weight:700;font-size:12px';
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      collapsed = !collapsed;
      updatePanelHeader();
    });

    controls.appendChild(startBtn);
    controls.appendChild(toggleBtn);
    header.appendChild(title);
    header.appendChild(controls);

    const body = document.createElement('div');
    body.className = 'vh-body';
    body.style.cssText = 'padding:12px;overflow:auto;max-height:calc(70vh - 44px)';
    body.innerHTML = '<div style="opacity:.75">Script arrêté. Clique sur <b>Démarrer</b> pour vérifier la phrase.</div>';

    panel.appendChild(header);
    panel.appendChild(body);
    document.documentElement.appendChild(panel);
    makeDraggable(panel, header);
    updatePanelHeader();
    return panel;
  }

  function updatePanelHeader() {
    const panel = document.getElementById('voltaire-reverso-helper-panel');
    if (!panel) return;
    const startBtn = panel.querySelector('.vh-start');
    const toggleBtn = panel.querySelector('.vh-toggle');
    const body = panel.querySelector('.vh-body');
    if (startBtn) startBtn.textContent = running ? 'Arrêter' : 'Démarrer';
    if (toggleBtn) toggleBtn.textContent = collapsed ? 'Déplier' : 'Plier';
    if (body) body.style.display = collapsed ? 'none' : 'block';
  }

  function setPanel(html, mode) {
    const panel = ensurePanel(true);
    if (!panel) return;
    const colors = {
      ok: ['#111827', 'transparent'],
      bad: ['#111827', 'transparent'],
      wait: ['#111827', '#64748b'],
      err: ['#111827', '#f59e0b'],
      busy: ['#111827', '#60a5fa'],
    }[mode || 'wait'];
    panel.style.background = colors[0];
    panel.style.borderColor = colors[1];
    const body = panel.querySelector('.vh-body');
    if (body) body.innerHTML = html;
    updatePanelHeader();
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  }

  function getElementText(element) {
    return (element && (element.innerText || element.textContent) || '')
      .replace(/\u00a0|\u202f/g, ' ')
      .replace(/[ \t\n\r]+/g, ' ')
      .trim();
  }

  function normalizeUiText(value) {
    return String(value || '')
      .replace(/\u00a0|\u202f/g, ' ')
      .replace(/[’‘`]/g, "'")
      .replace(/\s+/g, ' ')
      .trim()
      .toUpperCase();
  }

  function isVisibleElement(el) {
    if (!(el instanceof HTMLElement)) return false;
    const s = window.getComputedStyle(el);
    if (!s || s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1 && r.bottom >= 0 && r.right >= 0 && r.top <= (window.innerHeight || 1080) && r.left <= (window.innerWidth || 1920);
  }

  function joinPhraseFragments(parts) {
    const cleaned = parts.map(p => String(p || '').replace(/\u00a0|\u202f/g, ' ').replace(/\s+/g, ' ')).filter(p => p.length > 0);
    let out = '';
    for (const part of cleaned) {
      if (!out) out = part;
      else if (/^[,.;:!?…)\]}»]+$/.test(part)) out += part;
      else if (/[’'\-«([{]$/.test(out)) out += part;
      else if (/^[’'\-]/.test(part)) out += part;
      else out += ' ' + part;
    }
    return out.replace(/\s+([,.;:!?])/g, '$1').trim();
  }

  function isSentenceUiNoise(text) {
    const n = normalizeUiText(text);
    return !n ||
      n.includes('COUP DE POUCE') ||
      n.includes('RETOUR AU MENU') ||
      n.includes('SUIVANT') ||
      n.includes('CONTINUER') ||
      n.includes('VALIDER') ||
      n.includes("IL N'Y A PAS DE FAUTE") ||
      n.includes('PAS DE FAUTE') ||
      n.includes('AUCUNE FAUTE') ||
      n.includes('CLIQUEZ SUR LA FAUTE') ||
      n.includes('SI VOUS VOYEZ UNE FAUTE') ||
      n.includes('PROGRESSION') ||
      n.includes('TEMPS') ||
      n.includes('MENU D\'ACCESSIBILITE') ||
      n.includes('MENU D\'ACCESSIBILITÉ');
  }

  function findNoMistakeButton() {
    const buttons = Array.from(document.querySelectorAll('button, [data-testid="button"], div[role="button"], div[tabindex="0"]')).filter(isVisibleElement);
    return buttons.find(b => normalizeUiText(getElementText(b)).includes("IL N'Y A PAS DE FAUTE")) || null;
  }

  function findQuestionRoot(noMistakeButton) {
    if (!noMistakeButton) return document.body;
    let best = noMistakeButton;
    let cur = noMistakeButton.parentElement;
    while (cur && cur !== document.body && cur !== document.documentElement) {
      const txt = getElementText(cur);
      const n = normalizeUiText(txt);
      if ((n.includes('SI VOUS VOYEZ UNE FAUTE') || n.includes('CLIQUEZ SUR LA FAUTE')) && n.includes("IL N'Y A PAS DE FAUTE")) {
        best = cur;
        if (txt.length > 80 && txt.length < 3000) break;
      }
      cur = cur.parentElement;
    }
    return best;
  }

  function collectClassicSentence() {
    const classic = document.querySelector('.sentence');
    if (classic && isVisibleElement(classic)) {
      const parts = Array.from(classic.childNodes).map(n => n.textContent || '');
      const phrase = joinPhraseFragments(parts);
      if (phrase) return phrase;
    }

    const legacyContainers = Array.from(document.querySelectorAll('.r-18u37iz.r-1w6e6rj.r-1h0z5md.r-1peese0')).filter(isVisibleElement);
    for (const container of legacyContainers) {
      const wordEls = Array.from(container.querySelectorAll('div[dir="auto"].css-146c3p1, span[dir="auto"].css-146c3p1'))
        .filter(isVisibleElement)
        .filter(el => !el.querySelector('svg') && getElementText(el).length > 0 && getElementText(el).length < 80 && !isSentenceUiNoise(getElementText(el)));
      if (wordEls.length >= 2) {
        return joinPhraseFragments(wordEls.map(getElementText));
      }
    }
    return '';
  }

  function extractPhraseFromDom() {
    const classic = collectClassicSentence();
    if (classic) return classic;

    const noMistakeButton = findNoMistakeButton();
    const root = findQuestionRoot(noMistakeButton);
    const candidates = Array.from(root.querySelectorAll('div[dir="auto"].css-146c3p1, span[dir="auto"].css-146c3p1'))
      .filter(isVisibleElement)
      .filter(el => el.id !== 'voltaire-reverso-helper-panel' && !el.closest('#voltaire-reverso-helper-panel'))
      .filter(el => !el.querySelector('svg') && !el.closest('button, [data-testid="button"], div[role="button"]'))
      .filter(el => {
        const text = getElementText(el);
        const style = window.getComputedStyle(el);
        const fontSize = Number.parseFloat(style.fontSize || '0');
        return text.length > 0 && text.length < 80 && fontSize >= 18 && !isSentenceUiNoise(text);
      });

    // Projet Voltaire RNW rend la phrase en mots/fragments cliquables. On se
    // limite au bloc de question (ancêtre du bouton "pas de faute") pour éviter
    // les menus, puis on garde l'ordre DOM qui correspond à l'ordre de lecture.
    const parts = candidates.map(getElementText);
    if (parts.length >= 2) return joinPhraseFragments(parts);

    return '';
  }

  function visibleSnapshot() {
    const rows = [];
    const seen = new Set();
    const vw = window.innerWidth || 1920;
    const vh = window.innerHeight || 1080;

    function visible(el) {
      const s = window.getComputedStyle(el);
      if (!s || s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return false;
      if (r.bottom < 0 || r.right < 0 || r.top > vh || r.left > vw) return false;
      return true;
    }

    for (const el of document.querySelectorAll('main *, [role="main"] *, body *')) {
      if (el.id === 'voltaire-reverso-helper-panel' || el.closest('#voltaire-reverso-helper-panel')) continue;
      if (!visible(el)) continue;
      const txt = (el.innerText || el.textContent || '')
        .replace(/\u00a0/g, ' ')
        .replace(/[ \t]+/g, ' ')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
      if (!txt || txt.length < 2 || txt.length > 1200) continue;
      if (seen.has(txt)) continue;
      seen.add(txt);
      const r = el.getBoundingClientRect();
      rows.push({ text: txt, x: Math.round(r.left), y: Math.round(r.top), area: Math.round(r.width * r.height) });
    }

    rows.sort((a, b) => (a.y - b.y) || (a.x - b.x) || (b.area - a.area));
    const visibleText = rows.map(r => r.text).join('\n');
    const bodyText = (document.body && document.body.innerText || '').replace(/\u00a0/g, ' ').trim();
    const phrase = extractPhraseFromDom();
    const text = ((phrase ? phrase + '\n' : '') + visibleText + '\n' + bodyText).trim();
    return {
      text,
      phrase,
      signature: (phrase + '\n' + rows.slice(0, 80).map(r => r.y + ':' + r.text).join('\n')).slice(0, 12000),
      rows,
    };
  }

  function postToLocalServer(snapshot) {
    return new Promise((resolve, reject) => {
      const payload = JSON.stringify({ text: snapshot.text || '', phrase: snapshot.phrase || '', url: location.href, title: document.title });
      if (typeof GM_xmlhttpRequest === 'function') {
        GM_xmlhttpRequest({
          method: 'POST',
          url: SERVER,
          data: payload,
          headers: { 'Content-Type': 'application/json' },
          timeout: 60000,
          onload: (res) => {
            try {
              const obj = JSON.parse(res.responseText || '{}');
              if (res.status >= 200 && res.status < 300) resolve(obj);
              else reject(new Error(obj.message || obj.error || ('HTTP ' + res.status)));
            } catch (e) { reject(e); }
          },
          onerror: () => reject(new Error('Impossible de joindre le serveur local')),
          ontimeout: () => reject(new Error('Timeout serveur local')),
        });
      } else {
        fetch(SERVER, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        }).then(async r => {
          const obj = await r.json();
          if (r.ok) resolve(obj);
          else reject(new Error(obj.message || obj.error || ('HTTP ' + r.status)));
        }).catch(reject);
      }
    });
  }

  function highlightChangedOriginal(original, corrected) {
    const originalText = String(original || '');
    const correctedText = String(corrected || '');
    const tokenRe = /[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’\-]*/g;
    const originalTokens = [];
    let m;
    while ((m = tokenRe.exec(originalText)) !== null) {
      originalTokens.push({ text: m[0], start: m.index, end: m.index + m[0].length, key: normalizeUiText(m[0]) });
    }
    const correctedKeys = [];
    while ((m = tokenRe.exec(correctedText)) !== null) {
      correctedKeys.push(normalizeUiText(m[0]));
    }
    if (!originalTokens.length || !correctedKeys.length || normalizeUiText(originalText) === normalizeUiText(correctedText)) {
      return escapeHtml(originalText);
    }

    let left = 0;
    while (left < originalTokens.length && left < correctedKeys.length && originalTokens[left].key === correctedKeys[left]) left++;
    let rightOriginal = originalTokens.length - 1;
    let rightCorrected = correctedKeys.length - 1;
    while (rightOriginal >= left && rightCorrected >= left && originalTokens[rightOriginal].key === correctedKeys[rightCorrected]) {
      rightOriginal--;
      rightCorrected--;
    }
    const changed = new Set();
    for (let i = left; i <= rightOriginal; i++) changed.add(i);
    if (!changed.size) return escapeHtml(originalText);

    let html = '';
    let cursor = 0;
    originalTokens.forEach((tok, index) => {
      html += escapeHtml(originalText.slice(cursor, tok.start));
      const escaped = escapeHtml(tok.text);
      html += changed.has(index)
        ? '<strong style="font-weight:900;text-decoration:underline;text-decoration-thickness:2px">' + escaped + '</strong>'
        : escaped;
      cursor = tok.end;
    });
    html += escapeHtml(originalText.slice(cursor));
    return html;
  }

  const VOLTAIRE_HAPPY_IMG = 'data:image/png;base64,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';
  const VOLTAIRE_MAD_IMG = 'data:image/png;base64,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';

  function voltaireFace(mood) {
    const angry = mood === 'angry';
    const src = angry ? VOLTAIRE_MAD_IMG : VOLTAIRE_HAPPY_IMG;
    const label = angry ? 'Voltaire fâché' : 'Voltaire content';
    // Image en position absolute: elle flotte dans le coin du résultat sans
    // participer au flux, donc elle n'agrandit pas la hauteur totale de la box.
    return '<img src="' + src + '" alt="' + label + '" title="' + label + '" style="position:absolute;right:8px;top:-9px;width:48px;height:48px;object-fit:contain;pointer-events:none;filter:drop-shadow(0 2px 2px rgba(0,0,0,.35))">';
  }

  function renderResult(result, elapsedMs) {
    const phrase = highlightChangedOriginal(result.phrase || '', result.corrected || '');
    const corrected = escapeHtml(result.corrected || '');
    const apiJson = escapeHtml(JSON.stringify({
      ok: result.ok,
      has_error: result.has_error,
      result: result.result,
      provider: result.provider,
      phrase: result.phrase,
      corrected: result.corrected,
      error_span: result.error_span,
      explanation: result.explanation,
      confidence: result.confidence,
    }, null, 2));
    const explanation = result.explanation
      ? '<div style="margin-top:10px"><b>Analyse :</b><br><div style="margin-top:4px;padding:8px;background:rgba(255,255,255,.08);border-radius:8px">' + escapeHtml(result.explanation) + '</div></div>'
      : '';
    const common =
      '<div style="font-size:12px;opacity:.75;margin-bottom:8px">maj ' + new Date().toLocaleTimeString() + ' · ' + escapeHtml(result.provider || 'correcteur') + ' ' + elapsedMs + 'ms</div>' +
      '<div style="margin-top:8px"><b>Phrase récupérée :</b><br><div style="margin-top:4px;padding:8px;background:rgba(255,255,255,.08);border-radius:8px">' + phrase + '</div></div>' +
      explanation;
    if (result.has_error) {
      return {
        mode: 'bad',
        html: '<div style="position:relative;padding-right:56px"><b style="font-size:16px">FAUTE PROBABLE</b>' + voltaireFace('angry') + '</div>' + common +
          '<div style="font-size:12px;opacity:.8;margin-top:6px">Le ou les mots soulignés/gras indiquent la zone modifiée par Reverso.</div>' +
          '<div style="margin-top:10px"><b>Correction Reverso :</b><br><div style="margin-top:4px;padding:8px;background:rgba(255,255,255,.08);border-radius:8px">' + corrected + '</div></div>' +
          '<details style="margin-top:10px"><summary>Détails JSON API locale</summary><pre style="white-space:pre-wrap;font-size:12px;background:rgba(0,0,0,.25);padding:8px;border-radius:8px;max-height:180px;overflow:auto">' + apiJson + '</pre></details>'
      };
    }
    return {
      mode: 'ok',
      html: '<div style="position:relative;padding-right:56px"><b style="font-size:16px">IL N\'Y A PAS DE FAUTE</b>' + voltaireFace('happy') + '</div>' + common +
        '<div style="margin-top:10px"><b>Réponse Reverso :</b><br><div style="margin-top:4px;padding:8px;background:rgba(255,255,255,.08);border-radius:8px">' + corrected + '</div></div>' +
        '<details style="margin-top:10px"><summary>Détails JSON API locale</summary><pre style="white-space:pre-wrap;font-size:12px;background:rgba(0,0,0,.25);padding:8px;border-radius:8px;max-height:180px;overflow:auto">' + apiJson + '</pre></details>'
    };
  }

  async function tick(reason) {
    if (!running && reason !== 'manual') return;
    if (busy || !isVoltairePage()) return;
    const snap = visibleSnapshot();
    if (!snap.text || snap.signature === lastVisibleSignature) return;
    lastVisibleSignature = snap.signature;
    if (snap.phrase && snap.phrase === lastPhrase && reason !== 'manual') {
      // Projet Voltaire met à jour timers/progression/animations : ces mutations
      // changent le snapshot mais pas la phrase. Ne rappelle pas Reverso pour ça.
      return;
    }
    if (snap.phrase && snap.phrase === errorBackoffPhrase && Date.now() < errorBackoffUntil && reason !== 'manual') {
      // Si Reverso renvoie une limite temporaire, ne pas marteler l'API à chaque
      // poll/mutation. Le bouton Démarrer force quand même une nouvelle tentative.
      return;
    }

    const seq = ++requestSeq;
    busy = true;
    const started = performance.now();
    setPanel('<b>Analyse en cours...</b><div style="margin-top:6px;opacity:.8">Changement détecté sur la page (' + escapeHtml(reason || 'poll') + ')</div>', 'busy');
    try {
      const result = await postToLocalServer(snap);
      if (seq !== requestSeq) return;
      if (!result.ok) {
        setPanel('<b>Voltaire Helper</b><div style="margin-top:6px">Changement détecté, mais phrase non trouvée.</div><div style="font-size:12px;opacity:.75;margin-top:6px">Clique sur Arrêter puis Démarrer pour relancer une vérification, ou change de question.</div>', 'wait');
        return;
      }
      const elapsed = Math.round(performance.now() - started);
      lastPhrase = result.phrase;
      const rendered = renderResult(result, elapsed);
      setPanel(rendered.html, rendered.mode);
    } catch (e) {
      if (snap.phrase) {
        errorBackoffPhrase = snap.phrase;
        errorBackoffUntil = Date.now() + 60000;
      }
      setPanel(
        '<b>Voltaire Helper</b>' +
        '<div style="margin-top:6px;color:#fed7aa">Serveur local non joignable ou erreur correcteur local.</div>' +
        '<div style="font-size:12px;opacity:.85;margin-top:5px">Si le serveur est lancé, attends 1 minute puis clique sur Arrêter/Démarrer.</div>' +
        '<div style="font-size:12px;opacity:.7;margin-top:5px">' + escapeHtml(e.message || e) + '</div>',
        'err'
      );
    } finally {
      busy = false;
    }
  }

  function schedule(reason) {
    clearTimeout(schedule.timer);
    schedule.timer = setTimeout(() => tick(reason), 150);
  }
  schedule.timer = null;

  ensurePanel();
  console.log('[Voltaire Helper] userscript chargé sur', location.href);
  setInterval(() => tick('poll'), POLL_MS);
  new MutationObserver(() => schedule('mutation')).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true });
  window.addEventListener('hashchange', () => schedule('hashchange'));
  window.addEventListener('popstate', () => schedule('popstate'));
  window.addEventListener('focus', () => schedule('focus'));
  document.addEventListener('click', () => schedule('click'), true);
  tick('initial');
})();
