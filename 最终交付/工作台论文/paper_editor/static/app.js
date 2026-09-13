/* Local, single-block editor. Source validation and atomic writes live on the server. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = {
    document: null, token: '', selected: null, selectRequest: 0,
    drafts: new Map(), proposals: new Map(), mode: 'simplify', panel: 'edit',
    busy: false, aiBusy: false, aiConfigured: false, building: false,
    pdfUrl: '', lastBuildKey: '', diff: null, diffView: 'session',
    refreshPromise: null, refreshAgain: false, refreshTimer: null,
    events: null, toastTimer: null, buildTimer: null, mathNotice: false
  };
  const labels = {
    heading: '标题', paragraph: '正文', caption: '图注', 'table-caption': '表注',
    'list-item': '列表项', equation: '公式', figure: '图片', table: '表格', code: '代码', list: '列表',
    manual: '手动编辑', 'ai-accept': '接受 AI 建议', undo: '撤销'
  };
  const instructions = {
    simplify: '精简当前块，删除重复和冗余表达，保留全部实质信息及限定条件。',
    academic: '将当前块润色为准确、克制的学术论文表达。',
    natural: '去除当前块中空泛、模板化的 AI 式表达，使文字自然、具体、简洁。',
    split: '拆分当前块中的过长句子，使句意清晰、衔接自然。',
    logic: '增强当前块内部的逻辑衔接，不引入新的假设、证据或结论。',
    polish: '在保持原意、论证关系与全部限定条件的前提下润色当前块。',
    custom: ''
  };

  async function api(path, options = {}) {
    const headers = {Accept: 'application/json', ...options.headers};
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (state.token) headers['X-Paper-Token'] = state.token;
    let response;
    try {
      response = await fetch(path, {...options, headers, credentials: 'same-origin', cache: 'no-store'});
    } catch (_) {
      throw new Error('无法连接本地服务。请确认工作台仍在运行，再重试。');
    }
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('json') ? await response.json() : {detail: await response.text()};
    if (!response.ok) {
      const detail = data.detail ?? data.message ?? data.error ?? `请求失败（${response.status}）`;
      let message = typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2);
      if (response.status === 409) message = '源码版本已变化，已阻止覆盖。请保留当前草稿，重新选择此块后比较最新源码。\n' + message;
      const error = new Error(message);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }
  function toast(message, error = false) {
    clearTimeout(state.toastTimer);
    $('toast').textContent = message;
    $('toast').classList.toggle('error', error);
    $('toast').hidden = false;
    state.toastTimer = setTimeout(() => {$('toast').hidden = true;}, error ? 7000 : 3800);
  }
  function message(text, kind = 'success') {
    $('operation-message').textContent = text;
    $('operation-message').className = `operation-message ${kind}`;
    $('operation-message').hidden = !text;
  }
  function connected(ok, text) {
    $('connection-status').textContent = text || (ok ? '本地服务已连接' : '连接中断');
    $('connection-status').className = `connection-status ${ok ? 'connected' : 'error'}`;
  }
  function setBusy(value) {
    state.busy = value;
    updateControls();
  }
  function blockElement(id) {
    return $('reader').querySelector(`[data-block-id="${CSS.escape(id)}"]`);
  }
  function highlight(id) {
    $('reader').querySelectorAll('.selected-block').forEach((el) => el.classList.remove('selected-block'));
    const el = id && blockElement(id);
    if (el) el.classList.add('selected-block');
  }
  function sectionText(value) {
    if (Array.isArray(value)) return value.join(' / ');
    return value || '论文正文';
  }
  function isStructural(block = state.selected) {
    return !!block && ['figure', 'table'].includes(block.type);
  }
  function canEdit(block = state.selected) {
    if (!block || isStructural(block) || block.protected_conclusion) return false;
    if (block.type === 'equation') return $('edit-equation').checked;
    return !block.readonly;
  }
  function saveDraft() {
    const b = state.selected;
    if (!b) return;
    const content = $('block-editor').value;
    if (content !== b.content) state.drafts.set(b.id, {content, version: b.version});
    else state.drafts.delete(b.id);
  }
  function updateControls() {
    const b = state.selected;
    const editable = canEdit();
    const dirty = !!b && $('block-editor').value !== b.content;
    $('block-editor').readOnly = !editable || state.busy;
    $('save-block').disabled = !editable || !dirty || state.busy;
    $('save-block').textContent = state.busy ? '正在保存…' : '保存此块';
    $('reset-draft').disabled = !dirty || state.busy;
    $('draft-state').textContent = dirty ? '未保存草稿' : '未修改';
    $('draft-state').style.color = dirty ? 'var(--amber)' : '';
    $('edit-equation').disabled = !b || b.type !== 'equation' || state.busy;
    const aiEditable = !!b && !b.readonly && !b.protected_conclusion && !isStructural(b) && b.type !== 'equation';
    const customEmpty = state.mode === 'custom' && !$('ai-instruction').value.trim();
    $('generate-ai').disabled = !state.aiConfigured || !aiEditable || state.aiBusy || state.busy || customEmpty;
    $('generate-ai').textContent = state.aiBusy ? '正在生成建议…' : '生成修改建议';
    const proposal = b && state.proposals.get(b.id);
    const validProposal = proposal && proposal.validation?.ok === true && proposal.version === b.version;
    $('accept-ai').disabled = !validProposal || state.busy || state.aiBusy;
    $('undo-block').disabled = !b || state.busy || $('undo-block').dataset.available !== 'true';
    $('open-diff').disabled = !state.document;
    $('build-pdf').disabled = !state.document || state.building;
    $('build-pdf').textContent = state.building ? 'PDF 构建中…' : '构建 PDF';
    $('readonly-message').hidden = !b || editable;
    if (b && !editable) {
      $('readonly-message').textContent = b.protected_conclusion ? '本块属于受保护的 Q1 / Q2 定理、证明或结论，采用整块只读保护。'
        : isStructural(b)
        ? '图片与表格本体仅定位，不在此编辑。点击对应图注或表注可修改文字。'
        : b.type === 'equation' ? '公式默认只读。明确需要修改时，请勾选“编辑公式”。' : '此源码块为只读。';
    }
  }
  function configureAI(ai = {}) {
    state.aiConfigured = ai.configured === true;
    $('ai-status').textContent = state.aiConfigured ? `AI 已配置${ai.model ? ' · ' + ai.model : ''}` : 'AI 未配置 · 可手动编辑';
    $('ai-status').classList.toggle('ready', state.aiConfigured);
    $('ai-config-note').textContent = state.aiConfigured
      ? 'AI 建议只作用于当前块。数学内容、数值、引用和结论均按保护规则校验。'
      : 'AI 尚未配置；手动编辑、撤销、diff 与 PDF 构建均可使用。后续按运行说明配置本地 AI 环境变量并重启服务，即可启用。';
    updateControls();
  }

  function lineDiff(before, after) {
    if (before === after) return '尚无修改。';
    const a = String(before).split('\n');
    const b = String(after).split('\n');
    if (a.length * b.length > 350000) return '--- 当前源码\n+++ 替换内容\n' + a.map((x) => '- ' + x).join('\n') + '\n' + b.map((x) => '+ ' + x).join('\n');
    const dp = Array.from({length: a.length + 1}, () => new Uint32Array(b.length + 1));
    for (let i = a.length - 1; i >= 0; i--) {
      for (let j = b.length - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? 1 + dp[i + 1][j + 1] : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
    const out = ['--- 当前源码', '+++ 替换内容'];
    let i = 0, j = 0;
    while (i < a.length || j < b.length) {
      if (i < a.length && j < b.length && a[i] === b[j]) {out.push('  ' + a[i]); i++; j++;}
      else if (j < b.length && (i === a.length || dp[i][j + 1] > dp[i + 1][j])) out.push('+ ' + b[j++]);
      else out.push('- ' + a[i++]);
    }
    return out.join('\n');
  }
  function renderDiff(element, text) {
    element.replaceChildren();
    const lines = String(text || '暂无差异。').split('\n');
    for (const line of lines) {
      const span = document.createElement('span');
      span.className = /^(---|\+\+\+|@@|diff |index )/.test(line) ? 'diff-heading' : line.startsWith('+') ? 'diff-added' : line.startsWith('-') ? 'diff-removed' : 'diff-context';
      span.textContent = line || ' ';
      element.append(span);
    }
  }
  function updateManualDiff() {
    const b = state.selected;
    if (b) renderDiff($('manual-diff'), lineDiff(b.content, $('block-editor').value));
    updateControls();
  }
  function renderProposal() {
    const b = state.selected;
    const p = b && state.proposals.get(b.id);
    $('ai-proposal').hidden = !p;
    if (!p) {updateControls(); return;}
    $('ai-before').textContent = p.before ?? b.content;
    $('ai-after').value = p.after || '';
    renderDiff($('ai-diff'), p.diff || lineDiff(p.before ?? b.content, p.after || ''));
    const stale = p.version !== b.version;
    const ok = p.validation?.ok === true && !stale;
    $('ai-validation').className = `notice ${ok ? 'success' : 'error'}`;
    $('ai-validation').textContent = stale ? '源码版本已变化，此建议不能接受。请基于当前块重新生成。' : ok ? '保护校验通过。请阅读差异；点击“接受并保存此块”才会写入源码。' : '已阻止写入：' + (p.validation?.message || p.validation?.reason || '保护校验未通过。');
    updateControls();
  }
  async function selectBlock(id, options = {}) {
    if (!id) return;
    saveDraft();
    const seq = ++state.selectRequest;
    try {
      const b = await api(`/api/block/${encodeURIComponent(id)}`);
      if (seq !== state.selectRequest) return;
      b.id = b.id || id;
      state.selected = b;
      $('selection-empty').hidden = true;
      $('selection-panel').hidden = false;
      $('selected-section').textContent = sectionText(b.section);
      $('selected-id').textContent = b.id;
      $('selected-source').textContent = b.source || b.source_path || '';
      $('type-badge').textContent = labels[b.type] || b.type;
      $('original-source').textContent = b.content;
      $('edit-equation').checked = false;
      const draft = state.drafts.get(b.id);
      $('block-editor').value = draft?.content ?? b.content;
      $('equation-mode-row').hidden = b.type !== 'equation';
      $('protection-note').hidden = !b.frozen;
      $('protection-note').textContent = b.protected_conclusion
        ? 'Q1 / Q2 结论保护：此块包含定理、证明或数学结论，采用整块只读保护，避免润色改变含义。'
        : 'Q1 / Q2 冻结保护：普通修改保留公式、常数、最优点、D*、引用及定理结论。';
      highlight(b.id);
      renderProposal();
      updateManualDiff();
      if (!options.keepMessage) message('');
      if (draft && draft.version !== b.version) message('该块存在未保存草稿，且源码版本已变化。草稿已保留在编辑框，请与“当前源码”比较；保存前请先重新整理内容。', 'info');
      if (state.panel === 'history') loadHistory();
      if (options.scroll) blockElement(id)?.scrollIntoView({behavior: 'smooth', block: 'center'});
    } catch (error) {
      message(error.message, 'error');
      toast('无法读取所选源码块', true);
    }
  }
  function setPanel(panel) {
    state.panel = panel;
    document.querySelectorAll('.editor-tab').forEach((button) => {
      const active = button.dataset.panel === panel;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', String(active));
    });
    for (const name of ['edit', 'ai', 'history']) $(name + '-panel').hidden = name !== panel;
    if (panel === 'history' && state.selected) loadHistory();
  }
  function getScrollAnchor() {
    const viewport = $('html-view');
    const top = viewport.getBoundingClientRect().top;
    const nodes = $('reader').querySelectorAll('[data-block-id]');
    for (const el of nodes) {
      const rect = el.getBoundingClientRect();
      if (rect.bottom > top + 12 && rect.top < top + viewport.clientHeight) return {id: el.dataset.blockId, offset: rect.top - top, scrollTop: viewport.scrollTop};
    }
    return {scrollTop: viewport.scrollTop};
  }
  function restoreScroll(anchor) {
    const viewport = $('html-view');
    const el = anchor.id && blockElement(anchor.id);
    if (el) viewport.scrollTop += el.getBoundingClientRect().top - viewport.getBoundingClientRect().top - anchor.offset;
    else viewport.scrollTop = anchor.scrollTop;
  }
  function renderTOC() {
    const nav = $('toc');
    nav.replaceChildren();
    const headings = $('reader').querySelectorAll('h1,h2,h3');
    for (const heading of headings) {
      const block = heading.closest('[data-block-id]') || heading.querySelector('[data-block-id]');
      if (!block) continue;
      const button = document.createElement('button');
      button.textContent = heading.textContent.trim();
      button.dataset.level = heading.tagName.slice(1);
      button.addEventListener('click', () => {
        $('toc').hidden = true;
        $('toc-toggle').setAttribute('aria-expanded', 'false');
        selectBlock(block.dataset.blockId, {scroll: true});
      });
      nav.append(button);
    }
    if (!nav.childElementCount) {
      const p = document.createElement('p'); p.className = 'empty-note'; p.textContent = '当前文档暂无可导航标题。'; nav.append(p);
    }
  }
  async function typesetMath(doc) {
    if (!window.MathJax?.typesetPromise) {
      if (!state.mathNotice) {
        state.mathNotice = true;
        message('本地 MathJax 未成功加载，公式暂时显示 LaTeX。请检查本地公式资源；正文编辑仍可使用。', 'info');
      }
      return;
    }
    try {
      await MathJax.startup.promise;
      const macros = doc.math_macros || {};
      const definitions = [];
      for (const [rawName, value] of Object.entries(macros)) {
        const name = rawName.replace(/^\\/, '');
        if (!/^[a-zA-Z]+$/.test(name)) continue;
        const definition = Array.isArray(value) ? value[0] : value;
        const count = Array.isArray(value) ? Number(value[1] || 0) : 0;
        if (typeof definition !== 'string' || count < 0 || count > 9) continue;
        definitions.push(`\\gdef\\${name}${Array.from({length: count}, (_, i) => '#' + (i + 1)).join('')}{${definition}}`);
      }
      if (definitions.length) {
        const span = document.createElement('span');
        span.className = 'math-macro-definitions';
        span.setAttribute('aria-hidden', 'true');
        span.textContent = '\\(' + definitions.join('') + '\\)';
        $('reader').prepend(span);
      }
      await MathJax.typesetPromise([$('reader')]);
    } catch (error) {
      message('部分公式渲染未完成：' + error.message, 'info');
    }
  }
  async function refreshDocument(force = false) {
    if (state.refreshPromise) {state.refreshAgain = true; return state.refreshPromise;}
    state.refreshPromise = (async () => {
      const doc = await api('/api/document');
      if (doc.csrf_token) state.token = doc.csrf_token;
      const revisionSame = !force && state.document && doc.revision != null && doc.revision === state.document.revision;
      state.document = doc;
      configureAI(doc.ai || {});
      $('canonical-source').textContent = doc.source_root || doc.canonical_source || doc.main_path || '最终交付 / 工作台论文 / paper / main.tex + source/*.tex';
      $('canonical-source').title = $('canonical-source').textContent;
      $('document-revision').textContent = doc.revision ? '版本 ' + String(doc.revision).slice(0, 10) : '';
      document.title = (doc.title || '论文') + ' · 微调工作台';
      connected(true);
      if (revisionSame) return;
      const anchor = getScrollAnchor();
      if (window.MathJax?.typesetClear) MathJax.typesetClear([$('reader')]);
      // HTML is produced and escaped by our local renderer, never by an AI response.
      $('reader').innerHTML = doc.html || '<p>当前论文暂无可阅读内容。</p>';
      $('block-count').textContent = `${$('reader').querySelectorAll('[data-block-id]').length} 个源码块`;
      highlight(state.selected?.id);
      renderTOC();
      restoreScroll(anchor);
      await typesetMath(doc);
      restoreScroll(anchor);
      const imagePromises = [...$('reader').querySelectorAll('img')].filter((img) => !img.complete).map((img) => new Promise((resolve) => {
        img.addEventListener('load', resolve, {once: true});
        img.addEventListener('error', resolve, {once: true});
      }));
      if (imagePromises.length) Promise.all(imagePromises).then(() => restoreScroll(anchor));
      if (state.selected) await selectBlock(state.selected.id, {keepMessage: true});
    })();
    try {await state.refreshPromise;}
    catch (error) {connected(false); message(error.message, 'error');}
    finally {
      state.refreshPromise = null;
      updateControls();
      if (state.refreshAgain) {state.refreshAgain = false; scheduleRefresh();}
    }
  }
  function scheduleRefresh() {
    clearTimeout(state.refreshTimer);
    state.refreshTimer = setTimeout(() => refreshDocument(), 180);
  }
  function startEvents() {
    state.events = new EventSource('/api/events');
    state.events.onopen = () => connected(true);
    state.events.addEventListener('document_changed', scheduleRefresh);
    state.events.addEventListener('build_updated', () => pollBuild());
    state.events.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'document_changed' || data.event === 'document_changed') scheduleRefresh();
        if (data.type === 'build_updated') pollBuild();
      } catch (_) { /* A heartbeat does not need to change the interface. */ }
    };
    state.events.onerror = () => connected(false, '实时连接重连中');
  }
  async function commitBlock(operation = 'manual') {
    const b = state.selected;
    if (!b || state.busy) return;
    const proposal = operation === 'ai-accept' && state.proposals.get(b.id);
    if (proposal && (proposal.validation?.ok !== true || proposal.version !== b.version)) return;
    if (!proposal && !canEdit()) return;
    const content = proposal ? proposal.after : $('block-editor').value;
    const draft = state.drafts.get(b.id);
    if (!proposal && draft && draft.version !== b.version) {
      message('保存已阻止：当前草稿基于旧版本。请先复制需保留的文字，再点击“还原编辑框”，在最新源码基础上修改。', 'error');
      return;
    }
    const equation = operation === 'manual' && $('edit-equation').checked;
    const payload = {content, expected_version: b.version, operation, edit_equation: equation, allow_math_changes: equation};
    if (proposal) payload.proposal_id = proposal.proposal_id;
    setBusy(true);
    try {
      await api(`/api/block/${encodeURIComponent(b.id)}`, {method: 'POST', body: JSON.stringify(payload)});
      state.drafts.delete(b.id);
      state.proposals.delete(b.id);
      if (state.selected?.id === b.id) {
        state.selected.content = content;
        $('block-editor').value = content;
      }
      await refreshDocument(true);
      message(`已保存 ${b.id}。HTML 已刷新；未触发 PDF 编译。`);
      toast('当前源码块已保存');
      if (state.panel === 'history') await loadHistory();
    } catch (error) {
      message(error.message, 'error');
      toast('未写入源码', true);
      if (error.status === 409) scheduleRefresh();
    } finally {setBusy(false);}
  }
  async function generateAI() {
    const b = state.selected;
    if (!b || state.aiBusy || !state.aiConfigured) return;
    const extra = $('ai-instruction').value.trim();
    const instruction = [instructions[state.mode], extra].filter(Boolean).join('\n');
    if (!instruction) return;
    state.aiBusy = true;
    updateControls();
    message('正在为当前源码块生成建议。生成过程不会修改文件。', 'info');
    try {
      const result = await api(`/api/ai-rewrite/${encodeURIComponent(b.id)}`, {method: 'POST', body: JSON.stringify({instruction, mode: state.mode, expected_version: b.version})});
      result.version = result.version ?? b.version;
      result.before = result.before ?? b.content;
      state.proposals.set(b.id, result);
      if (state.selected?.id === b.id) renderProposal();
      message(result.validation?.ok === true ? '建议已生成，尚未写入源码。请审阅 before / after diff。' : '建议触发保护规则，已阻止接受。', result.validation?.ok === true ? 'info' : 'error');
    } catch (error) {message(error.message, 'error');}
    finally {state.aiBusy = false; updateControls();}
  }
  async function loadHistory() {
    const b = state.selected;
    if (!b) return;
    $('history-list').textContent = '正在读取…';
    try {
      const data = await api(`/api/history?block_id=${encodeURIComponent(b.id)}`);
      if (state.selected?.id !== b.id) return;
      const items = Array.isArray(data) ? data : data.items || data.history || data.records || [];
      $('history-list').replaceChildren();
      $('undo-block').dataset.available = String(items.length > 0);
      if (!items.length) {
        const p = document.createElement('p'); p.className = 'empty-note'; p.textContent = '此块暂无修改记录。'; $('history-list').append(p);
      }
      const sorted = [...items].sort((a, z) => String(z.timestamp || z.time || '').localeCompare(String(a.timestamp || a.time || '')));
      for (const item of sorted) {
        const row = document.createElement('article'); row.className = 'history-item';
        const heading = document.createElement('div'); heading.className = 'history-item-heading';
        const time = document.createElement('time');
        const rawTime = item.timestamp || item.time || '';
        const date = new Date(rawTime);
        time.textContent = rawTime && !Number.isNaN(date.getTime()) ? date.toLocaleString('zh-CN', {hour12: false}) : rawTime;
        const op = document.createElement('span'); op.textContent = labels[item.operation || item.operation_type] || item.operation || item.operation_type || '修改';
        heading.append(time, op);
        const preview = document.createElement('p'); preview.className = 'history-item-preview'; preview.textContent = item.after || '';
        const details = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = '查看此次差异';
        const diff = document.createElement('pre'); diff.className = 'diff-code'; renderDiff(diff, lineDiff(item.before || '', item.after || ''));
        details.append(summary, diff); row.append(heading, preview, details); $('history-list').append(row);
      }
      updateControls();
    } catch (error) {$('history-list').textContent = error.message; $('undo-block').dataset.available = 'false'; updateControls();}
  }
  async function undoBlock() {
    const b = state.selected;
    if (!b || state.busy) return;
    if ($('block-editor').value !== b.content) {
      message('当前块有未保存草稿。请先保存或还原编辑框，再撤销最近一次已保存修改。', 'info');
      return;
    }
    setBusy(true);
    try {
      await api(`/api/block/${encodeURIComponent(b.id)}/undo`, {method: 'POST', body: JSON.stringify({expected_version: b.version})});
      state.drafts.delete(b.id); state.proposals.delete(b.id);
      await refreshDocument(true);
      await loadHistory();
      message(`已撤销 ${b.id} 最近一次修改，HTML 已刷新。`);
      toast('已撤销当前块最近一次修改');
    } catch (error) {message(error.message, 'error');}
    finally {setBusy(false);}
  }
  async function openDiff() {
    $('source-diff').textContent = '正在读取源码差异…';
    $('diff-dialog').showModal();
    try {
      state.diff = await api('/api/diff');
      showDiffView(state.diffView);
    } catch (error) {$('source-diff').textContent = error.message; $('diff-context').textContent = '无法读取 diff。';}
  }
  function showDiffView(view) {
    state.diffView = view;
    $('session-diff-tab').classList.toggle('active', view === 'session');
    $('git-diff-tab').classList.toggle('active', view === 'git');
    const data = state.diff;
    if (!data) return;
    if (view === 'git') {
      $('diff-context').textContent = data.git_available === false ? '当前目录不在 Git 仓库中；可切换到本轮源码修改查看启动基线差异。' : 'Git 对正式论文源码的实际差异。';
      renderDiff($('source-diff'), data.git_text || data.git_diff || 'Git 当前无源码差异。');
    } else {
      $('diff-context').textContent = typeof data.baseline === 'string' ? '比较基线：' + data.baseline : '当前正式论文源码与本轮工作台基线的差异。';
      renderDiff($('source-diff'), data.text || data.diff || '本轮尚无源码修改。');
    }
  }
  function showView(view) {
    const html = view === 'html';
    $('html-tab').classList.toggle('active', html); $('html-tab').setAttribute('aria-selected', String(html));
    $('pdf-tab').classList.toggle('active', !html); $('pdf-tab').setAttribute('aria-selected', String(!html));
    $('html-view').hidden = !html; $('pdf-view').hidden = html;
    $('toc-toggle').hidden = !html; $('toc').hidden = true;
    $('toc-toggle').setAttribute('aria-expanded', 'false');
    if (!html && state.pdfUrl) {
      if ($('pdf-frame').dataset.loadedUrl !== state.pdfUrl) {$('pdf-frame').src = state.pdfUrl; $('pdf-frame').dataset.loadedUrl = state.pdfUrl;}
      $('pdf-frame').hidden = false; $('pdf-empty').hidden = true;
    }
  }
  function renderBuild(data) {
    const raw = String(data.status || 'idle').toLowerCase();
    const running = ['queued', 'running', 'building', 'pending', 'starting'].includes(raw);
    const success = ['success', 'succeeded', 'complete', 'completed', 'done'].includes(raw);
    const failed = ['failed', 'failure', 'error'].includes(raw);
    state.building = running;
    if (raw === 'idle' && !data.pdf_path) {updateControls(); return;}
    $('build-result').hidden = false;
    $('build-status').textContent = running ? '构建中' : success ? '成功' : failed ? '失败' : raw;
    $('build-status').className = `badge ${success ? 'success' : failed ? 'error' : ''}`;
    $('build-path').textContent = data.pdf_path || (running ? '正在运行正式 LaTeX 构建链…' : '尚未生成 PDF');
    $('build-log').textContent = [data.error, Array.isArray(data.log_summary) ? data.log_summary.join('\n') : data.log_summary || data.log_tail].filter(Boolean).join('\n\n') || (running ? '等待编译日志…' : '暂无日志摘要。');
    if (failed) $('build-log-details').open = true;
    if (success && data.pdf_url) {
      const key = data.job_id || data.finished_at || data.completed_at || data.pdf_path || 'latest';
      if (key !== state.lastBuildKey) {
        state.lastBuildKey = key;
        state.pdfUrl = data.pdf_url + (data.pdf_url.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(key);
      }
      $('pdf-download').href = state.pdfUrl; $('pdf-download').hidden = false;
      if (!$('pdf-view').hidden) showView('pdf');
    }
    updateControls();
  }
  async function pollBuild() {
    clearTimeout(state.buildTimer);
    try {
      const data = await api('/api/build-pdf/status');
      renderBuild(data);
      if (state.building) state.buildTimer = setTimeout(pollBuild, 1300);
    } catch (error) {
      if (state.building) {message('读取构建状态失败：' + error.message, 'error'); state.buildTimer = setTimeout(pollBuild, 4000);}
    }
  }
  async function startBuild() {
    if (state.building) return;
    state.building = true; updateControls();
    $('build-result').hidden = false; $('build-status').textContent = '正在启动'; $('build-status').className = 'badge';
    $('build-path').textContent = '编译当前已保存的正式论文源码。';
    $('build-log').textContent = '正在启动 LaTeX 构建…';
    try {
      const result = await api('/api/build-pdf', {method: 'POST', body: JSON.stringify({})});
      renderBuild(result);
      await pollBuild();
    } catch (error) {
      state.building = false;
      renderBuild({status: 'failed', error: error.message});
      message(error.message, 'error');
    }
  }

  $('reader').addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : event.target.parentElement;
    if (target.closest('summary') && !target.closest('summary').hasAttribute('data-block-id')) return;
    const block = target.closest('[data-block-id]');
    if (!block || !$('reader').contains(block)) return;
    if (target.closest('a.asset-original')) return;
    if (target.closest('a')) event.preventDefault();
    event.stopPropagation();
    selectBlock(block.dataset.blockId);
  });
  $('reader').addEventListener('keydown', (event) => {
    if (!['Enter', ' '].includes(event.key) || event.target.tagName === 'SUMMARY') return;
    const block = event.target.closest('[data-block-id]');
    if (block) {event.preventDefault(); event.stopPropagation(); selectBlock(block.dataset.blockId);}
  });
  $('block-editor').addEventListener('input', () => {saveDraft(); updateManualDiff();});
  $('edit-equation').addEventListener('change', updateControls);
  $('save-block').addEventListener('click', () => commitBlock());
  $('reset-draft').addEventListener('click', () => {
    if (!state.selected) return;
    state.drafts.delete(state.selected.id); $('block-editor').value = state.selected.content;
    updateManualDiff(); message('编辑框已还原为当前源码，尚未修改文件。', 'info');
  });
  $('block-editor').addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {event.preventDefault(); if (!$('save-block').disabled) commitBlock();}
  });
  document.querySelectorAll('.editor-tab').forEach((button) => button.addEventListener('click', () => setPanel(button.dataset.panel)));
  document.querySelectorAll('.mode-button').forEach((button) => button.addEventListener('click', () => {
    state.mode = button.dataset.mode;
    document.querySelectorAll('.mode-button').forEach((el) => el.classList.toggle('active', el === button));
    if (state.mode === 'custom') $('ai-instruction').focus();
    updateControls();
  }));
  $('ai-instruction').addEventListener('input', updateControls);
  $('generate-ai').addEventListener('click', generateAI);
  $('accept-ai').addEventListener('click', () => commitBlock('ai-accept'));
  $('discard-ai').addEventListener('click', () => {if (state.selected) state.proposals.delete(state.selected.id); renderProposal(); message('建议已丢弃，源码未变化。', 'info');});
  $('undo-block').addEventListener('click', undoBlock);
  $('open-diff').addEventListener('click', openDiff);
  $('close-diff').addEventListener('click', () => $('diff-dialog').close());
  $('session-diff-tab').addEventListener('click', () => showDiffView('session'));
  $('git-diff-tab').addEventListener('click', () => showDiffView('git'));
  $('build-pdf').addEventListener('click', startBuild);
  $('html-tab').addEventListener('click', () => showView('html'));
  $('pdf-tab').addEventListener('click', () => showView('pdf'));
  $('toc-toggle').addEventListener('click', () => {$('toc').hidden = !$('toc').hidden; $('toc-toggle').setAttribute('aria-expanded', String(!$('toc').hidden));});
  document.addEventListener('click', (event) => {if (!$('toc').contains(event.target) && !$('toc-toggle').contains(event.target)) {$('toc').hidden = true; $('toc-toggle').setAttribute('aria-expanded', 'false');}});
  window.addEventListener('beforeunload', (event) => {if (state.drafts.size) {event.preventDefault(); event.returnValue = '';}});
  window.addEventListener('online', () => refreshDocument());

  async function initialize() {
    await refreshDocument(true);
    if (!state.document) return;
    startEvents();
    pollBuild();
    try {
      const status = await api('/api/status');
      if (status.ai) configureAI(status.ai);
      const source = status.source_root || status.canonical_source || status.paper_root;
      if (source) {$('canonical-source').textContent = source; $('canonical-source').title = source;}
    } catch (_) { /* The document endpoint contains everything needed for editing. */ }
  }
  initialize();
})();
