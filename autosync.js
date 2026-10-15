/* ============================================================
   autosync.js — автосинхронизация с Supabase
   Работает поверх cloud.js. Требует: db.js, cloud.js.
   Настройки:
   - Задержка после изменения: 5 сек
   - Разрешение конфликтов: побеждает свежее (по updatedAt)
   - Уведомления: тост внизу справа
   ============================================================ */

const AUTOSYNC_DELAY_MS = 5000;    // 5 секунд после последнего изменения
const AUTOSYNC_TABLES = ['materials','products','cycles','opokas','batches','stock','archive'];

let _syncTimer = null;
let _syncInProgress = false;
let _syncPending = false;

/* ---------- Тост-уведомления ---------- */
function showToast(msg, type) {
  const colors = {
    info:    { bg: '#2b6cb0', text: '#fff' },
    success: { bg: '#2f855a', text: '#fff' },
    error:   { bg: '#c53030', text: '#fff' },
    warn:    { bg: '#b7791f', text: '#fff' },
  };
  const c = colors[type] || colors.info;

  let box = document.getElementById('toast_box');
  if (!box) {
    box = document.createElement('div');
    box.id = 'toast_box';
    box.style.cssText = `
      position: fixed; right: 16px; bottom: 16px; z-index: 9999;
      display: flex; flex-direction: column; gap: 8px;
      pointer-events: none; max-width: 320px;
    `;
    document.body.appendChild(box);
  }

  const el = document.createElement('div');
  el.style.cssText = `
    background: ${c.bg}; color: ${c.text};
    padding: 10px 16px; border-radius: 8px;
    font-size: 14px; font-family: Arial, sans-serif;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    opacity: 0; transform: translateY(10px);
    transition: opacity .25s, transform .25s;
    pointer-events: auto;
  `;
  el.textContent = msg;
  box.appendChild(el);

  requestAnimationFrame(() => {
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  });

  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(10px)';
    setTimeout(() => el.remove(), 300);
  }, 2500);
}

/* ---------- Обработка статуса ---------- */
function setCloudIndicator(state) {
  // state: 'online' | 'syncing' | 'offline' | 'error'
  const colors = { online: '#2f855a', syncing: '#b7791f', offline: '#718096', error: '#c53030' };
  const titles = { online: 'Облако: онлайн', syncing: 'Облако: синхронизация…', offline: 'Облако: офлайн', error: 'Облако: ошибка' };
  const el = document.getElementById('cloud_dot');
  if (!el) return;
  el.style.background = colors[state] || colors.offline;
  el.title = titles[state] || '';
}

/* ---------- Проставить updatedAt всем объектам ---------- */
function stampUpdatedAt(data) {
  const now = new Date().toISOString();
  for (const t of AUTOSYNC_TABLES) {
    const arr = data[t] || [];
    for (const item of arr) {
      if (!item.updatedAt) item.updatedAt = now;
    }
  }
  return data;
}

/* ---------- Основная функция синхронизации ---------- */
async function runAutosync(dataGetter, dataSetter) {
  if (_syncInProgress) { _syncPending = true; return; }
  _syncInProgress = true;
  setCloudIndicator('syncing');

  try {
    const local = dataGetter();
    stampUpdatedAt(local);

    // 1) push
    const pushRes = await pushAll(local);
    if (!pushRes.ok) throw new Error('push: ' + pushRes.error);

    // 2) pull
    const pullRes = await pullAll();
    if (!pullRes.ok) throw new Error('pull: ' + pullRes.error);

    // 3) merge — побеждает свежее по updatedAt
    const merged = mergeByUpdatedAt(local, pullRes.data);

    dataSetter(merged);
    await saveData(merged);

    setCloudIndicator('online');
    showToast('✅ Синхронизировано', 'success');
  } catch (e) {
    console.error('Autosync error:', e);
    setCloudIndicator('error');
    showToast('❌ Ошибка синхронизации: ' + e.message, 'error');
  } finally {
    _syncInProgress = false;
    if (_syncPending) {
      _syncPending = false;
      // следующий проход через 1 сек, чтобы не спамить
      setTimeout(() => runAutosync(dataGetter, dataSetter), 1000);
    }
  }
}

/* ---------- Merge по updatedAt ---------- */
function mergeByUpdatedAt(local, remote) {
  const merged = {};
  for (const t of AUTOSYNC_TABLES) {
    const map = new Map();
    for (const item of (local[t] || []))  map.set(String(item.id), item);
    for (const item of (remote[t] || [])) {
      const key = String(item.id);
      const cur = map.get(key);
      if (!cur) { map.set(key, item); continue; }
      const tLocal  = cur.updatedAt ? Date.parse(cur.updatedAt) : 0;
      const tRemote = item.updatedAt ? Date.parse(item.updatedAt) : 0;
      if (tRemote > tLocal) map.set(key, item);
    }
    merged[t] = [...map.values()];
  }
  return merged;
}

/* ---------- Планировщик: вызывается при каждом изменении ---------- */
function scheduleAutosync(dataGetter, dataSetter) {
  if (_syncTimer) clearTimeout(_syncTimer);
  setCloudIndicator('syncing');
  _syncTimer = setTimeout(() => {
    _syncTimer = null;
    runAutosync(dataGetter, dataSetter);
  }, AUTOSYNC_DELAY_MS);
}

/* ---------- Слушаем появление/пропажу интернета ---------- */
window.addEventListener('online',  () => {
  setCloudIndicator('online');
  showToast('🌐 Интернет восстановлен — синхронизирую…', 'info');
  if (window.__scheduleAutosync) window.__scheduleAutosync();
});
window.addEventListener('offline', () => {
  setCloudIndicator('offline');
  showToast('📴 Нет интернета — данные сохранятся локально', 'warn');
});