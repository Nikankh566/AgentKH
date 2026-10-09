/* Agent KH frontend — bilingual (EN default, FA toggle) */
const $ = id => document.getElementById(id);
const chat = $('chat'), mascot = $('mascot'), statusEl = $('status');
const input = $('input');

let streaming = false;
let LANG = 'en';

const I18N = {
  en: {
    settings: '⚙️ Settings', provider: 'Provider', customApi: 'Custom API (OpenAI-compatible)',
    geminiKey: 'Gemini key', model: 'Model', baseUrl: 'API base URL', apiKey: 'Key',
    autoApprove: 'Auto-approve commands (careful!)', homeOnly: 'Restrict files to user folder',
    language: 'Language', save: 'Save', close: 'Close', personality: '🎭 Agent KH personality (soul.md)',
    savePersonality: 'Save personality', memory: '🧠 Long-term memory',
    memoryHint: 'Things Agent KH learned about you. Saved via the remember tool.',
    memoryEmpty: 'Nothing learned yet 🙂', forget: 'Forget',
    statusReady: 'Ready!', statusThinking: 'Thinking...', statusTalking: 'Speaking...',
    statusWorking: 'Working... 🔧', statusApproval: 'Waiting for your approval 👀',
    statusNeedKey: 'API key needed 🔑',
    inputPh: 'Ask Agent KH to do something...',
    needKey: '👋 Hi! I\'m Agent KH ✨ Open Settings (⚙️) and enter your API key to start.',
    settingsSaved: '✅ Settings saved.', soulSaved: '🎭 Personality updated.',
    newChat: '🧹 New conversation started.',
    toolDenied: ' ✗ denied', toolOk: ' ✓',
    approvalTitle: '⚠️ Approval needed: ', allow: '✅ Allow', deny: '❌ Deny',
    approved: 'Approved ✓', denied: 'Denied ✗',
    errServer: '⚠️ Server connection error: ',
    dir: 'ltr', langAttr: 'en',
  },
  fa: {
    settings: '⚙️ تنظیمات', provider: 'سرویس', customApi: 'API دلخواه (OpenAI-compatible)',
    geminiKey: 'کلید Gemini', model: 'مدل', baseUrl: 'آدرس API', apiKey: 'کلید',
    autoApprove: 'تأیید خودکار دستورات (با احتیاط!)', homeOnly: 'محدود کردن فایل‌ها به پوشه کاربر',
    language: 'زبان', save: 'ذخیره', close: 'بستن', personality: '🎭 شخصیت Agent KH (soul.md)',
    savePersonality: 'ذخیره شخصیت', memory: '🧠 حافظه بلندمدت',
    memoryHint: 'چیزایی که Agent KH درباره‌ت یاد گرفته. با ابزار remember ذخیره می‌شن.',
    memoryEmpty: 'هنوز چیزی یاد نگرفتم 🙂', forget: 'فراموش کن',
    statusReady: 'آماده‌ام!', statusThinking: 'دارم فکر می‌کنم...', statusTalking: 'دارم حرف می‌زنم...',
    statusWorking: 'دارم کاری انجام می‌دم... 🔧', statusApproval: 'منتظر تأیید توام 👀',
    statusNeedKey: 'کلید API لازمه 🔑',
    inputPh: 'به Agent KH بگو چی کار کنه...',
    needKey: '👋 سلام! من Agent KH ام ✨ اول برو توی تنظیمات (⚙️) کلید API رو وارد کن تا شروع کنیم.',
    settingsSaved: '✅ تنظیمات ذخیره شد.', soulSaved: '🎭 شخصیت به‌روز شد.',
    newChat: '🧹 گفتگوی جدید شروع شد.',
    toolDenied: ' ✗ رد شد', toolOk: ' ✓',
    approvalTitle: '⚠️ اجازه لازمه: ', allow: '✅ اجازه بده', deny: '❌ نه',
    approved: 'تأیید شد ✓', denied: 'رد شد ✗',
    errServer: '⚠️ خطا در ارتباط با سرور: ',
    dir: 'rtl', langAttr: 'fa',
  }
};
const t = k => (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;

function applyLang() {
  document.documentElement.lang = t('langAttr');
  document.documentElement.dir = t('dir');
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  input.placeholder = t('inputPh');
  setStatus(t('statusReady'));
}

/* ---------- mascot ---------- */
function setMood(m) { mascot.className = m; }
function setStatus(s) { statusEl.textContent = s; }
function happy(){ setMood('happy'); setTimeout(()=>setMood('idle'), 700); }
function sad(){ setMood('sad'); setTimeout(()=>setMood('idle'), 1200); }

const pupils = document.querySelectorAll('#mascot .pupil');
const sparks = document.querySelectorAll('#mascot .spark');
document.addEventListener('mousemove', e => {
  const r = mascot.getBoundingClientRect();
  const cx = r.left + r.width/2, cy = r.top + r.height/2;
  const dx = Math.max(-6, Math.min(6, (e.clientX-cx)/40));
  const dy = Math.max(-4, Math.min(4, (e.clientY-cy)/40));
  pupils.forEach(p => p.style.transform = `translate(${dx}px,${dy}px)`);
  sparks.forEach(p => p.style.transform = `translate(${dx}px,${dy}px)`);
});

/* ---------- chat rendering ---------- */
function addMsg(role, text) {
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
  return d;
}
function addNotice(text, cls='notice') {
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.textContent = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}
function addToolLine(name, ok) {
  const d = document.createElement('div');
  d.className = 'tool-line' + (ok === true ? ' ok' : ok === false ? ' denied' : '');
  d.textContent = '🔧 ' + name + (ok === true ? t('toolOk') : ok === false ? t('toolDenied') : ' …');
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
  return d;
}
function addApproval(call_id, name, args) {
  const d = document.createElement('div');
  d.className = 'approval';
  const pretty = typeof args === 'object' ? JSON.stringify(args, null, 2) : String(args);
  d.innerHTML = `<h4>${esc(t('approvalTitle'))}${esc(name)}</h4><pre>${esc(pretty)}</pre>
    <div class="btns"><button class="allow">${esc(t('allow'))}</button><button class="deny">${esc(t('deny'))}</button></div>`;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
  const done = approved => {
    fetch('/api/decision', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({call_id, approved})});
    d.querySelector('.btns').innerHTML = `<span style="font-size:13px;color:${approved?'var(--good)':'var(--bad)'}">${approved?esc(t('approved')):esc(t('denied'))}</span>`;
  };
  d.querySelector('.allow').onclick = () => done(true);
  d.querySelector('.deny').onclick = () => done(false);
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;'); }

/* ---------- send ---------- */
async function send() {
  const text = input.value.trim();
  if (!text || streaming) return;
  input.value = '';
  addMsg('user', text);
  streaming = true;
  setMood('thinking'); setStatus(t('statusThinking'));

  const botDiv = addMsg('bot', '');
  botDiv.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  let started = false, toolLines = {};

  try {
    const res = await fetch('/api/chat', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: text})});
    if (!res.ok && (res.headers.get('content-type')||'').includes('json')) {
      const j = await res.json();
      botDiv.remove();
      if (j.notice) addNotice(j.notice);
      streaming = false; setMood('idle'); setStatus(t('statusReady'));
      return;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '', evName = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, i); buf = buf.slice(i+2);
        let data = '';
        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) evName = line.slice(6).trim();
          else if (line.startsWith('data:')) data += line.slice(5).trim();
        }
        handleEvent(evName, data, botDiv, toolLines, () => started, v => started = v);
      }
    }
  } catch(e) {
    botDiv.textContent = t('errServer') + e.message;
    sad();
  }
  streaming = false;
  if (mascot.className === 'talking' || mascot.className === 'thinking') setMood('idle');
  setStatus(t('statusReady'));
}

function handleEvent(ev, data, botDiv, toolLines, getStarted, setStarted) {
  let p = {};
  try { p = JSON.parse(data); } catch(e) { p = data; }
  if (ev === 'token') {
    if (!getStarted()) { botDiv.textContent = ''; setStarted(true); setMood('talking'); setStatus(t('statusTalking')); }
    botDiv.textContent += p;
    chat.scrollTop = chat.scrollHeight;
  } else if (ev === 'tool_start') {
    toolLines[p.name] = addToolLine(p.name, null);
    setMood('thinking'); setStatus(t('statusWorking'));
  } else if (ev === 'tool_end') {
    const el = toolLines[p.name];
    if (el) { el.classList.add(p.denied ? 'denied' : 'ok'); el.textContent += p.denied ? t('toolDenied') : t('toolOk'); }
    p.denied ? sad() : happy();
  } else if (ev === 'approval') {
    addApproval(p.call_id, p.name, p.args);
    setStatus(t('statusApproval'));
  } else if (ev === 'error') {
    if (!getStarted()) botDiv.remove();
    addNotice('⚠️ ' + p, 'error'); sad();
  } else if (ev === 'end') {
    if (!getStarted() && !botDiv.textContent.trim()) botDiv.remove();
  }
}

$('send').onclick = send;
input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

/* ---------- language ---------- */
async function setLang(l, save) {
  LANG = (l === 'fa') ? 'fa' : 'en';
  applyLang();
  if (save) {
    await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({lang: LANG})});
  }
}
$('btn-lang').onclick = () => setLang(LANG === 'en' ? 'fa' : 'en', true);

/* ---------- settings ---------- */
const sModal = $('settings-modal');
$('btn-settings').onclick = async () => {
  const cfg = await (await fetch('/api/config')).json();
  $('set-provider').value = cfg.provider || 'gemini';
  $('set-gemini-key').value = cfg.gemini_key || '';
  $('set-gemini-model').value = cfg.gemini_model || 'gemini-3.5-flash';
  $('set-custom-url').value = cfg.custom_base_url || '';
  $('set-custom-key').value = cfg.custom_key || '';
  $('set-custom-model').value = cfg.custom_model || '';
  $('set-auto-approve').checked = !!cfg.auto_approve;
  $('set-home-only').checked = cfg.home_only !== false;
  $('set-lang').value = cfg.lang || 'en';
  toggleProvider();
  const soul = await (await fetch('/api/soul')).json();
  $('soul-text').value = soul.soul || '';
  sModal.classList.remove('hidden');
};
function toggleProvider() {
  const c = $('set-provider').value === 'custom';
  $('custom-fields').classList.toggle('hidden', !c);
  $('gemini-fields').classList.toggle('hidden', c);
}
$('set-provider').onchange = toggleProvider;
$('set-close').onclick = () => sModal.classList.add('hidden');
$('set-save').onclick = async () => {
  const l = $('set-lang').value;
  await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      provider: $('set-provider').value,
      gemini_key: $('set-gemini-key').value.trim(),
      gemini_model: $('set-gemini-model').value.trim(),
      custom_base_url: $('set-custom-url').value.trim(),
      custom_key: $('set-custom-key').value.trim(),
      custom_model: $('set-custom-model').value.trim(),
      auto_approve: $('set-auto-approve').checked,
      home_only: $('set-home-only').checked,
      lang: l,
    })});
  await setLang(l, false);
  addNotice(t('settingsSaved'));
  sModal.classList.add('hidden');
};
$('soul-save').onclick = async () => {
  await fetch('/api/soul', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({soul: $('soul-text').value})});
  addNotice(t('soulSaved'));
};

/* ---------- memory panel ---------- */
const mModal = $('memory-modal');
$('btn-memory').onclick = async () => {
  const j = await (await fetch('/api/memory')).json();
  const ul = $('memory-list'); ul.innerHTML = '';
  (j.facts || []).forEach(f => {
    const li = document.createElement('li');
    li.innerHTML = `<span>${esc(f)}</span>`;
    const b = document.createElement('button'); b.textContent = '🗑️'; b.title = t('forget');
    b.onclick = async () => {
      await fetch('/api/forget', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({fact: f})});
      li.remove();
    };
    li.appendChild(b); ul.appendChild(li);
  });
  if (!(j.facts||[]).length) ul.innerHTML = `<li>${esc(t('memoryEmpty'))}</li>`;
  mModal.classList.remove('hidden');
};
$('memory-close').onclick = () => mModal.classList.add('hidden');

/* ---------- clear ---------- */
$('btn-clear').onclick = async () => {
  await fetch('/api/clear', {method:'POST'});
  chat.innerHTML = '';
  addNotice(t('newChat'));
};

/* ---------- init ---------- */
(async () => {
  let cfg = {};
  try { cfg = await (await fetch('/api/config')).json(); } catch(e) {}
  await setLang(cfg.lang || 'en', false);
  const h = await (await fetch('/api/history')).json();
  (h.messages || []).forEach(m => {
    if (m.role === 'user') addMsg('user', m.content);
    else if (m.role === 'assistant') addMsg('bot', m.content);
  });
  const keyOk = cfg.provider === 'custom' ? cfg.custom_key && cfg.custom_model
                                          : cfg.gemini_key;
  if (!keyOk) {
    addNotice(t('needKey'));
    setStatus(t('statusNeedKey'));
  }
})();
