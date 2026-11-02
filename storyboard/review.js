// Storyboard review: Approve / Change + a note per beat, one general note. Every click is saved by server.py into
// review.json next to the page, so Claude reads it when the user says the review is done.
// Keyboard: A approve (then the next open beat), C change (opens the note), O original take, J / K next and previous
// beat, Esc.
// A beat that offers versions (data-options="ABC") has one Approve per version: a click saves approved plus that
// letter, and a second click on the picked letter undoes it. The A key does not approve there: it moves focus to the
// first version button. A beat approved without one of its letters (an old review.json, or a letter the storyboard no
// longer offers) is in the 'pick' state: it counts as not reviewed, and "go" waits for the letter.
// "Pick your look" (optional section #look): every line of it runs only when the page has the section. A saved pick that
// differs from the look the beats are drawn in ("lookPending") turns Done into a review, never a go.
(() => {
  const API = '/api/review';
  const body = document.body;
  const $ = (s) => document.querySelector(s);
  const beats = [...document.querySelectorAll('.beat')];
  const ids = beats.map((b) => b.dataset.beat);
  const byId = Object.fromEntries(beats.map((b) => [b.dataset.beat, b]));
  const total = beats.length;
  const version = Number(body.dataset.version || 1);
  const motion = () => (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');
  let state = { beats: {}, general: { note: '' } };
  let current = ids[0];
  let lookPending = false;       // a saved look pick the beats are not drawn in yet (set by the look section below)
  let lookPaint = () => {};      // no-ops on a page without the section
  let lookInit = () => {};

  const valueOf = (id) => (state.beats[id] || {}).value || null;

  // versions: a beat that offers them lists its letters in data-options ("ABC"); a one-version beat has none
  const optionsOf = (el) => [...(el.dataset.options || '')];
  const pickOf = (id) => (state.beats[id] || {}).option || null;
  // 'approved' | 'change' | 'pick' (approved, but no valid letter yet) | null (not reviewed)
  function stateOf(id) {
    const v = valueOf(id);
    if (v === 'change') return 'change';
    if (v !== 'approved') return null;
    const opts = optionsOf(byId[id]);
    return opts.length && !opts.includes(pickOf(id)) ? 'pick' : 'approved';
  }
  const orList = (a) => (a.length < 2 ? a.join('') : `${a.slice(0, -1).join(', ')} or ${a[a.length - 1]}`);

  // saving
  function tick(el, text, bad) {
    if (!el) return;
    el.textContent = text;
    el.classList.toggle('err', !!bad);
    el.classList.add('on');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('on'), bad ? 4000 : 1400);
  }
  async function post(payload, tickEl) {
    try {
      const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!r.ok) throw new Error(String(r.status));
      state = await r.json();
      tick(tickEl, 'Saved');
      $('#status').textContent = '';
    } catch (e) {
      tick(tickEl, 'Not saved', true);
      $('#status').textContent = 'Not saved. Is the server running?';
    }
    paint();
  }

  // drawing the state
  function markCurrent() {
    for (const el of beats) el.classList.toggle('is-current', el.dataset.beat === current);
    for (const seg of document.querySelectorAll('.seg')) seg.classList.toggle('is-current', seg.dataset.beat === current);
  }
  function paint() {
    let ok = 0, chg = 0, noLetter = 0;
    const picked = [];
    for (const el of beats) {
      const id = el.dataset.beat;
      const s = stateOf(id);
      const opts = optionsOf(el);
      const pick = opts.length && s === 'approved' ? pickOf(id) : null;     // the letter shown as picked
      el.classList.toggle('is-ok', s === 'approved');
      el.classList.toggle('is-chg', s === 'change');
      el.classList.toggle('is-pick', s === 'pick');
      for (const b of el.querySelectorAll('.act.ok')) {
        b.setAttribute('aria-pressed', String(s === 'approved' && (!opts.length || b.dataset.opt === pick)));
      }
      el.querySelector('.act.chg').setAttribute('aria-pressed', String(s === 'change'));
      for (const m of el.querySelectorAll('.mo[data-opt]')) {
        m.classList.toggle('is-picked', !!pick && m.dataset.opt === pick);
        m.classList.toggle('is-other', !!pick && m.dataset.opt !== pick);
      }
      const ta = el.querySelector('.note textarea');
      if (document.activeElement !== ta) { ta.value = (state.beats[id] || {}).note || ''; fit(ta); }
      const seg = document.querySelector(`.seg[data-beat="${id}"]`);
      if (seg) { seg.classList.toggle('is-ok', s === 'approved'); seg.classList.toggle('is-chg', s === 'change'); }
      if (s === 'approved') ok++; else if (s === 'change') chg++; else if (s === 'pick') noLetter++;
      if (pick) picked.push(`${el.dataset.n} ${pick}`);
    }
    markCurrent();
    const rest = total - ok - chg;      // a beat approved without a version counts as not reviewed here
    $('#n-ok').textContent = ok;
    $('#wrap-sum').textContent = `${ok} approved · ${chg} to change · ${rest} not reviewed`
      + (picked.length ? ` · picked ${picked.join(', ')}` : '') + (noLetter ? ` · ${noLetter} without a version` : '');
    const list = $('#wrap-list');
    list.textContent = '';
    for (const el of beats) {
      const id = el.dataset.beat;
      const s = stateOf(id);
      if (s !== 'change' && s !== 'pick') continue;
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = `#b-${id}`;
      a.textContent = el.dataset.n;
      const span = document.createElement('span');
      if (s === 'pick') {
        span.textContent = `Approved without a version: pick ${orList(optionsOf(el))}.`;
      } else {
        span.textContent = (state.beats[id] || {}).note || 'No note yet.';
        if (!(state.beats[id] || {}).note) span.className = 'quiet';
      }
      li.append(a, span);
      list.append(li);
    }
    lookPaint();
    body.classList.toggle('all-ok', ok === total);
    paintDone(ok, chg, rest);
    const g = $('#general');
    if (document.activeElement !== g) g.value = (state.general || {}).note || '';
  }

  // Done: the review goes straight to the Claude session (wait_done.py wakes it), no message in the chat needed
  let armed = false;
  const hhmm = (iso) => (iso || '').slice(11, 16);
  function paintDone(ok, chg, rest) {
    const btn = $('#done'), note = $('#done-note');
    const sub = state.submitted && state.submitted.version === version ? state.submitted : null;
    const editedAfter = sub && state.saved_at && state.saved_at > sub.at;
    const go = ok === total && !lookPending;
    btn.classList.toggle('is-go', go);
    btn.classList.toggle('is-armed', armed && !go);
    btn.classList.toggle('is-sent', !!sub && !editedAfter);
    if (sub && !editedAfter) {
      btn.disabled = true;
      btn.textContent = sub.kind === 'go' ? 'Approved ✓' : 'Sent ✓';
      note.textContent = sub.kind === 'go'
        ? `Sent at ${hhmm(sub.at)}. Claude is starting the edit; you will review the video in the HyperFrames player.`
        : `Sent at ${hhmm(sub.at)}. Claude is making v${version + 1}; this page tells you when it is ready.`;
      return;
    }
    btn.disabled = false;
    if (go) {
      btn.textContent = 'Approve storyboard · start the edit';
      note.textContent = 'Every beat is approved. Claude starts editing as soon as you click.';
    } else if (armed) {
      btn.textContent = `Send anyway (${rest} not reviewed)`;
      note.textContent = 'Beats you did not review stay as they are in the next version.';
    } else {
      btn.textContent = sub ? 'Send the update' : 'Done · send my review';
      note.textContent = `${chg} to change · ${rest} not reviewed. No need to write anything in the chat.`
        + (lookPending ? ' The new look is drawn in the next version.' : '');
    }
  }
  $('#done').addEventListener('click', async () => {
    const approved = ids.filter((id) => stateOf(id) === 'approved').length;
    const reviewed = ids.filter((id) => ['approved', 'change'].includes(stateOf(id))).length;   // 'pick' is not reviewed
    const kind = approved === total && !lookPending ? 'go' : 'review';
    if (kind === 'review' && reviewed < total && !armed) { armed = true; paint(); return; }
    armed = false;
    $('#done').disabled = true;
    try {
      const r = await fetch('/api/submit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind }) });
      if (r.status === 409) {
        const j = await r.json().catch(() => ({}));
        if (j.look_pending) {
          $('#status').textContent = 'The new look is not drawn yet. Click Done again to send a review.';
          paint();
          return;
        }
      }
      if (!r.ok) throw new Error(String(r.status));
      state = await r.json();
      $('#status').textContent = '';
    } catch (e) {
      $('#status').textContent = 'Not sent. Is the server running?';
    }
    paint();
  });

  // a new version is ready: say so (the page never reloads by itself while you type)
  async function checkVersion() {
    try {
      const r = await fetch('/api/version', { cache: 'no-store' });
      const v = (await r.json()).version;
      if (v > version) { $('#newver').hidden = false; return; }
    } catch (e) { /* server down: try again later */ }
    setTimeout(checkVersion, 4000);
  }
  $('#newver-go').addEventListener('click', () => location.reload());
  setTimeout(checkVersion, 4000);

  // deciding
  // opts.option: the version letter of the Approve button clicked (beats that offer versions only)
  function decide(id, value, opts = {}) {
    const el = byId[id];
    if (value === 'approved' && optionsOf(el).length && !opts.option) return;   // a beat with versions needs its letter
    const now = valueOf(id);
    const nowPick = optionsOf(el).length && now === 'approved' ? pickOf(id) : null;
    const same = !opts.option || nowPick === opts.option;   // the letter clicked is already the pick
    const next = opts.keep && now === value && same ? value : now === value && same ? null : value; // a second click undoes
    const option = next === 'approved' && opts.option ? opts.option : null;
    const entry = { ...(state.beats[id] || {}), value: next };
    if (option) entry.option = option; else delete entry.option;
    state.beats[id] = entry;
    armed = false;
    current = id;
    paint();
    if (next !== now || option !== nowPick) {
      post(option ? { beat: id, value: next, option } : { beat: id, value: next }, el.querySelector('.saved-tick'));
    }
    if (next === 'change') setTimeout(() => el.querySelector('.note textarea').focus(), 40);
    if (next === 'approved' && opts.advance) setTimeout(() => nextOpen(id), 420);
  }
  function visible(id) { return byId[id].offsetParent !== null; }
  function goTo(id) {
    current = id;
    markCurrent();
    byId[id].scrollIntoView({ behavior: motion(), block: 'start' });
  }
  function nextOpen(fromId) {
    const i = ids.indexOf(fromId);
    const order = ids.slice(i + 1).concat(ids.slice(0, i));
    const id = order.find((x) => !['approved', 'change'].includes(stateOf(x)) && visible(x));   // 'pick' is still open
    if (id) goTo(id);
    else $('#wrap').scrollIntoView({ behavior: motion(), block: 'start' });
  }
  function step(d) {
    const vis = ids.filter(visible);
    if (!vis.length) return;
    const i = vis.indexOf(current);
    goTo(vis[Math.max(0, Math.min(vis.length - 1, i < 0 ? 0 : i + d))]);
  }

  // notes grow with their text
  function fit(ta) { ta.style.height = 'auto'; ta.style.height = `${Math.max(92, ta.scrollHeight)}px`; }

  function setView(el, v) {
    el.classList.toggle('show-take', v === 'take');
    el.querySelectorAll('.view button').forEach((b) => b.classList.toggle('is-on', b.dataset.v === v));
  }

  for (const el of beats) {
    const id = el.dataset.beat;
    for (const b of el.querySelectorAll('.act.ok')) {
      b.addEventListener('click', () => decide(id, 'approved', { advance: true, option: b.dataset.opt }));
    }
    el.querySelector('.act.chg').addEventListener('click', () => decide(id, 'change'));
    const ta = el.querySelector('.note textarea');
    let t;
    ta.addEventListener('input', () => {
      fit(ta);
      clearTimeout(t);
      t = setTimeout(() => post({ beat: id, note: ta.value }, el.querySelector('.saved-tick')), 500);
    });
    ta.addEventListener('focus', () => { current = id; markCurrent(); });
    // planned edit or original take: the same instants, before and after the edit
    for (const vb of el.querySelectorAll('.view button')) vb.addEventListener('click', () => setView(el, vb.dataset.v));
    // a click on a moment opens the beat's sequence full size, in the view shown
    for (const fr of el.querySelectorAll('.mo-frame')) {
      fr.addEventListener('click', () => {
        const take = el.classList.contains('show-take');
        const mos = [...el.querySelectorAll('.mo')];
        const list = mos.map((m, k) => ({
          src: m.querySelector(take ? '.mo-take' : '.mo-plan').getAttribute('src'),
          label: `${el.dataset.n}${m.dataset.opt ? ` · Version ${m.dataset.opt}` : mos.length > 1 ? ` · ${k + 1} of ${mos.length}` : ''} · `
            + `${take ? 'Original take' : 'Planned edit'} · ${m.querySelector('figcaption').lastChild.textContent}`,
        }));
        openBox(list, Number(fr.closest('.mo').dataset.i));
      });
    }
    const ref = el.querySelector('.ref-thumb');
    if (ref) ref.addEventListener('click', () => openBox([{ src: ref.dataset.src, label: `${el.dataset.n} · Reference` }], 0));
  }

  const general = $('#general');
  let gt;
  general.addEventListener('input', () => {
    clearTimeout(gt);
    gt = setTimeout(() => post({ general: general.value }, null), 500);
  });

  // filter: all, still to review, changes only
  for (const b of document.querySelectorAll('.filter button')) {
    b.addEventListener('click', () => {
      body.dataset.filter = b.dataset.f;
      document.querySelectorAll('.filter button').forEach((x) => x.classList.toggle('is-on', x === b));
    });
  }

  // light or dark, remembered in this browser
  $('#theme').addEventListener('click', () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('sb-theme', root.dataset.theme); } catch (e) { /* private window: not remembered */ }
  });

  // the beat being looked at
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { current = e.target.dataset.beat; markCurrent(); }
  }, { rootMargin: '-28% 0px -62% 0px' });
  beats.forEach((b) => io.observe(b));
  for (const seg of document.querySelectorAll('.seg, .tl-blk')) {
    seg.addEventListener('click', (e) => { e.preventDefault(); if (visible(seg.dataset.beat)) goTo(seg.dataset.beat); });
  }

  // lightbox
  const box = $('#lightbox');
  const boxImg = box.querySelector('img');
  const boxCap = box.querySelector('figcaption');
  let boxList = [], boxIdx = 0;
  function showBox() { boxImg.src = boxList[boxIdx].src; boxCap.textContent = boxList[boxIdx].label; box.classList.toggle('single', boxList.length < 2); }
  function openBox(list, idx) { boxList = list; boxIdx = idx; showBox(); box.hidden = false; }
  function boxStep(d) { if (boxList.length < 2) return; boxIdx = (boxIdx + d + boxList.length) % boxList.length; showBox(); }
  box.addEventListener('click', (e) => {
    if (e.target.closest('.lb-prev')) return boxStep(-1);
    if (e.target.closest('.lb-next')) return boxStep(1);
    if (e.target === boxImg) return boxStep(1);
    box.hidden = true;
  });

  // Pick your look: one doodle style, one text style, an optional free-text request, Save look
  const lookEl = $('#look');
  if (lookEl) {
    const cur = { doodle: lookEl.dataset.curDoodle, type: lookEl.dataset.curType, custom: lookEl.dataset.curCustom || '' };
    const rec = { doodle: lookEl.dataset.recDoodle, type: lookEl.dataset.recType };
    const cards = [...lookEl.querySelectorAll('.look-card')];
    const custom = $('#look-custom');
    const saveBtn = $('#look-save');
    const newEl = $('#look-new');
    const wrapNew = $('#wrap-look');
    let pick = { ...cur, custom: cur.custom };
    let saved = false;            // the pick on screen is the one in review.json
    // same rule as look_pending() in build.py: another doodle or type, or a non-empty request that differs from current
    const differs = (l) => !!l && (l.doodle !== cur.doodle || l.type !== cur.type
      || ((l.custom || '').trim() !== '' && (l.custom || '').trim() !== (cur.custom || '').trim()));

    lookInit = () => {
      if (state.look) { pick = { doodle: state.look.doodle, type: state.look.type, custom: state.look.custom || '' }; saved = true; }
      custom.value = pick.custom;
    };
    lookPaint = () => {
      for (const c of cards) c.querySelector('.look-pick').setAttribute('aria-pressed', String(pick[c.dataset.kind] === c.dataset.id));
      lookPending = differs(state.look);
      const msg = `New look picked: it will be applied in v${version + 1}`;
      for (const el of [newEl, wrapNew]) {
        if (!el) continue;
        el.hidden = !lookPending;
        el.textContent = msg;
      }
      saveBtn.classList.toggle('is-saved', saved);
      saveBtn.textContent = saved ? 'Saved ✓' : 'Save look';
    };
    const edited = () => { saved = false; lookPaint(); };
    for (const c of cards) {
      c.querySelector('.look-pick').addEventListener('click', () => { pick[c.dataset.kind] = c.dataset.id; edited(); });
      const z = c.querySelector('.look-zoom');
      if (z) z.addEventListener('click', () => openBox([{ src: z.dataset.src, label: `${z.dataset.label} · ${c.dataset.id}` }], 0));
    }
    const use = $('#look-use');
    if (use) use.addEventListener('click', () => { pick.doodle = rec.doodle; pick.type = rec.type; edited(); });
    custom.addEventListener('input', () => { pick.custom = custom.value; edited(); });
    saveBtn.addEventListener('click', async () => {
      const tickEl = $('#look-tick');
      try {
        const r = await fetch('/api/look', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doodle: pick.doodle, type: pick.type, custom: pick.custom }) });
        if (!r.ok) throw new Error(String(r.status));
        state = await r.json();
        saved = true;
        tick(tickEl, 'Saved');
        $('#status').textContent = '';
      } catch (e) {
        tick(tickEl, 'Not saved', true);
        $('#status').textContent = 'Not saved. Is the server running?';
      }
      paint();
    });
  }

  // keyboard
  document.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('textarea, input')) {
      if (e.key === 'Escape') e.target.blur();
      return;
    }
    if (!box.hidden) {
      if (e.key === 'Escape') box.hidden = true;
      else if (e.key === 'ArrowRight') boxStep(1);
      else if (e.key === 'ArrowLeft') boxStep(-1);
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === 'a') {
      e.preventDefault();
      const el = byId[current];
      if (optionsOf(el).length) {     // a beat with versions: A does not approve, it goes to the first version button
        el.querySelector('.act.ok').focus();
        tick(el.querySelector('.saved-tick'), 'Pick a version', true);
      } else decide(current, 'approved', { advance: true, keep: true });
    }
    else if (k === 'c') { e.preventDefault(); decide(current, 'change', { keep: true }); }
    else if (k === 'o') { e.preventDefault(); setView(byId[current], byId[current].classList.contains('show-take') ? 'plan' : 'take'); }
    else if (k === 'j') { e.preventDefault(); step(1); }
    else if (k === 'k') { e.preventDefault(); step(-1); }
  });

  fetch(API)
    .then((r) => r.json())
    .then((s) => { state = s; lookInit(); paint(); })
    .catch(() => { $('#status').textContent = 'Not saved. Is the server running?'; paint(); });
})();
