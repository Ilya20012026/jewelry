/* ============================================================
   cloud.js — синхронизация с Supabase
   Требует: db.js (для локального хранилища)
   ============================================================ */

const SUPABASE_URL = 'https://kjiybjmisztrwymkwwsg.supabase.co';
const SUPABASE_KEY = 'sb_publishable_08SQ7121NYScNVQYffjjyg_mj-VWYv-';

const TABLES = ['materials','products','cycles','opokas','batches','stock','archive'];

/* Поля дат Supabase (не отправляем как есть) */
const SKIP_FIELDS = ['updated_at'];

let _sb = null;
let _sbReady = false;

/* ---------- Инициализация клиента Supabase ---------- */
async function initCloud() {
  if (_sbReady) return _sb;
  try {
    const mod = await import('https://esm.sh/@supabase/supabase-js@2');
    _sb = mod.createClient(SUPABASE_URL, SUPABASE_KEY);
    _sbReady = true;
    console.log('☁️ Supabase подключён');
    return _sb;
  } catch (e) {
    console.error('❌ Не удалось подключить Supabase:', e.message);
    return null;
  }
}

/* ---------- Проверка связи ---------- */
async function cloudStatus() {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };
  try {
    const { error } = await sb.from('materials').select('id').limit(1);
    if (error) return { ok: false, error: error.message };
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/* ---------- Очистка объекта перед отправкой ---------- */
function cleanRow(row) {
  const out = {};
  for (const k in row) {
    if (SKIP_FIELDS.includes(k)) continue;
    if (row[k] === undefined) continue;
    out[k] = row[k];
  }
  return out;
}

/* ---------- Отправить всё локальное в облако ---------- */
async function pushAll(localData) {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };

  const summary = {};
  for (const table of TABLES) {
    const rows = (localData[table] || []).map(cleanRow);
    if (rows.length === 0) { summary[table] = 0; continue; }

    const { error } = await sb.from(table).upsert(rows, { onConflict: 'id' });
    if (error) {
      console.error(`❌ push ${table}:`, error.message);
      return { ok: false, error: `${table}: ${error.message}`, summary };
    }
    summary[table] = rows.length;
  }
  console.log('⬆️ Выгружено в облако:', summary);
  return { ok: true, summary };
}

/* ---------- Скачать всё из облака ---------- */
async function pullAll() {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };

  const remote = {};
  for (const table of TABLES) {
    const { data, error } = await sb.from(table).select('*');
    if (error) {
      console.error(`❌ pull ${table}:`, error.message);
      return { ok: false, error: `${table}: ${error.message}` };
    }
    // Убираем поля Supabase (updated_at), чтобы не путались с локальными
    remote[table] = (data || []).map(r => {
      const out = {};
      for (const k in r) {
        if (SKIP_FIELDS.includes(k)) continue;
        out[k] = r[k];
      }
      return out;
    });
  }
  console.log('⬇️ Скачано из облака:',
    Object.fromEntries(TABLES.map(t => [t, remote[t].length])));
  return { ok: true, data: remote };
}

/* ---------- Объединение локальных и облачных данных ---------- */
/* Правило: побеждает тот, у кого объект новее по времени.
   Локальные объекты, которых нет в облаке, остаются.
   Облачные объекты, которых нет локально, добавляются. */
function mergeData(localData, remoteData) {
  const merged = {};
  for (const table of TABLES) {
    const localArr = localData[table] || [];
    const remoteArr = remoteData[table] || [];

    const map = new Map();
    // Сначала локальные
    for (const item of localArr) map.set(String(item.id), { ...item, _src: 'local' });
    // Затем облачные — если объект уже есть локально, решаем по updated_at (если есть)
    for (const item of remoteArr) {
      const key = String(item.id);
      if (!map.has(key)) {
        map.set(key, { ...item, _src: 'cloud' });
      } else {
        // Оба есть — берём облачный (Supabase всегда хранит последнюю версию)
        map.set(key, { ...item, _src: 'merged' });
      }
    }
    merged[table] = [...map.values()].map(({ _src, ...rest }) => rest);
  }
  return merged;
}

/* ---------- Полная синхронизация: push + pull + merge ---------- */
async function syncAll(localData) {
  console.log('🔄 Синхронизация...');

  // 1. Выгружаем локальное в облако
  const pushRes = await pushAll(localData);
  if (!pushRes.ok) return { ok: false, error: pushRes.error };

  // 2. Скачиваем из облака (уже с учётом выгруженного)
  const pullRes = await pullAll();
  if (!pullRes.ok) return { ok: false, error: pullRes.error };

  // 3. Объединяем
  const merged = mergeData(localData, pullRes.data);

  console.log('✅ Синхронизация завершена');
  return { ok: true, data: merged };
}