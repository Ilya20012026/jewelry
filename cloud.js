/* ============================================================
   cloud.js — синхронизация с Supabase (с поддержкой tombstones)
   Требует: db.js
   ============================================================ */

const SUPABASE_URL = 'https://kjiybjmisztrwymkwwsg.supabase.co';
const SUPABASE_KEY = 'sb_publishable_08SQ7121NYScNVQYffjjyg_mj-VWYv-';

const TABLES = ['materials','products','cycles','opokas','batches','stock','archive','tasks','employees','groups','chats','messages','boards','columns','board_tasks','supplies','notifications','settings','shifts'];
const SKIP_FIELDS = ['updated_at', 'updatedAt'];
const TOMBSTONE_TTL_DAYS = 30;

let _sb = null;
let _sbReady = false;
let _sbPromise = null;

/* ---------- Инициализация клиента Supabase ---------- */

async function initCloud() {
  if (_sbReady) return _sb;
  if (_sbPromise) return _sbPromise; // Если уже в процессе подключения — ждем его

  _sbPromise = (async () => {
    try {
      const mod = await import('https://esm.sh/@supabase/supabase-js@2');
      _sb = mod.createClient(SUPABASE_URL, SUPABASE_KEY);
      _sbReady = true;
      console.log('☁️ Supabase подключён');
      return _sb;
    } catch (e) {
      console.error('❌ Не удалось подключить Supabase:', e.message);
      _sbPromise = null; // Сбрасываем при ошибке, чтобы можно было попробовать снова
      return null;
    }
  })();

  return _sbPromise;
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

/* ---------- Очистка строки перед отправкой ---------- */
function cleanRow(row) {
  const out = {};
  for (const k in row) {
    if (SKIP_FIELDS.includes(k)) continue;
    if (row[k] === undefined) continue;
    out[k] = row[k];
  }
  return out;
}

// НОВАЯ ФУНКЦИЯ: Умная отправка (если колонки нет в базе - вырезаем и пробуем снова)
async function safeUpsert(sb, table, rows) {
  let attempts = 0;
  let currentRows = [...rows];
  
  while (attempts < 5) {
    const { error } = await sb.from(table).upsert(currentRows, { onConflict: 'id' });
    
    if (!error) return { ok: true };
    
    // Если ошибка "Could not find the 'xxx' column"
    const match = error.message.match(/Could not find the '([^']+)' column/);
    if (match) {
      const badColumn = match[1];
      console.warn(`⚠️ В таблице ${table} нет колонки '${badColumn}'. Удаляем её из запроса...`);
      currentRows = currentRows.map(r => {
        const copy = { ...r };
        delete copy[badColumn];
        return copy;
      });
      attempts++;
      continue; // Пробуем отправить снова без этой колонки
    }
    
    // Если какая-то другая ошибка - возвращаем её
    return { ok: false, error: error.message };
  }
  return { ok: false, error: 'Слишком много ошибок с колонками' };
}

/* ---------- Очистка строки из облака ---------- */
function stripRow(row) {
  const out = {};
  for (const k in row) {
    if (SKIP_FIELDS.includes(k)) continue;
    out[k] = row[k];
  }
  return out;
}

/* ============================================================
   TOMBSTONES — учёт удалённых объектов
   ============================================================ */

/** Удалить старые tombstones (> TOMBSTONE_TTL_DAYS дней) */
async function cleanupOldTombstones() {
  const sb = await initCloud();
  if (!sb) return;
  const cutoff = new Date(Date.now() - TOMBSTONE_TTL_DAYS * 86400000).toISOString();
  const { error } = await sb.from('deleted').delete().lt('deleted_at', cutoff);
  if (error) console.warn('cleanup tombstones:', error.message);
}

/** Отправить локальные tombstones в облако */
async function pushDeleted(deletedList) {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };

  // deletedList: { tableName: [id1, id2, ...], ... }
  const rows = [];
  for (const tableName in deletedList) {
    for (const id of deletedList[tableName]) {
      rows.push({ table_name: tableName, id: String(id) });
    }
  }
  if (rows.length === 0) return { ok: true, count: 0 };

  const { error } = await sb.from('deleted').upsert(rows, { onConflict: 'table_name,id' });
  if (error) return { ok: false, error: error.message };
  return { ok: true, count: rows.length };
}

/** Скачать tombstones из облака */
async function pullDeleted() {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };

  const { data, error } = await sb.from('deleted').select('table_name, id, deleted_at');
  if (error) return { ok: false, error: error.message };

  const result = {};
  for (const t of TABLES) result[t] = [];
  for (const row of (data || [])) {
    if (!result[row.table_name]) result[row.table_name] = [];
    result[row.table_name].push(String(row.id));
  }
  return { ok: true, data: result };
}

/* ============================================================
   PUSH / PULL основных данных
   ============================================================ */

async function pushAll(localData) {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };

  const summary = {};
  for (const table of TABLES) {
    const rows = (localData[table] || []).map(cleanRow);
    if (rows.length === 0) { summary[table] = 0; continue; }

        const result = await safeUpsert(sb, table, rows);
    if (!result.ok) {
      console.error(`❌ push ${table}:`, result.error);
      summary[table] = `ОШИБКА: ${result.error}`;
      continue;
    }
    summary[table] = rows.length;
  }
  console.log('⬆️ Выгружено в облако:', summary);
  return { ok: true, summary };
}

async function pullAll() {
  const sb = await initCloud();
  if (!sb) return { ok: false, error: 'Нет клиента' };

  const remote = {};
  for (const table of TABLES) {
    const { data, error } = await sb.from(table).select('*');
        if (error) {
      console.error(`❌ pull ${table}:`, error.message);
      remote[table] = [];
      continue;
    }
    remote[table] = (data || []).map(stripRow);
  }
  console.log('⬇️ Скачано из облака:',
    Object.fromEntries(TABLES.map(t => [t, remote[t].length])));
  return { ok: true, data: remote };
}

/* ---------- Merge локальных и облачных данных ---------- */
function mergeData(localData, remoteData) {
  const merged = {};
  for (const table of TABLES) {
    const localArr = localData[table] || [];
    const remoteArr = remoteData[table] || [];
    const map = new Map();
    for (const item of localArr) map.set(String(item.id), item);
    for (const item of remoteArr) {
      const key = String(item.id);
      if (!map.has(key)) map.set(key, item);
    }
    merged[table] = [...map.values()];
  }
  return merged;
}

/* ---------- Полная синхронизация (старый режим, кнопка в UI) ---------- */
async function syncAll(localData) {
  console.log('🔄 Синхронизация...');
  const pushRes = await pushAll(localData);
  if (!pushRes.ok) return { ok: false, error: pushRes.error };

  const pullRes = await pullAll();
  if (!pullRes.ok) return { ok: false, error: pullRes.error };

  const merged = mergeData(localData, pullRes.data);
  console.log('✅ Синхронизация завершена');
  return { ok: true, data: merged };
}

/* ============================================================
   REALTIME — мгновенные обновления
   ============================================================ */

/**
 * Инициализирует подписку на изменения в таблицах Supabase.
 * @param {Function} onDataChanged — коллбэк, вызывается при любом изменении.
 */
async function initRealtime(onDataChanged) {
  const sb = await initCloud();
  if (!sb) {
    console.warn('Realtime: нет клиента Supabase');
    return;
  }

    const tablesToWatch = [
    'materials', 'products', 'cycles', 'opokas',
    'batches', 'stock', 'archive', 'tasks',
    'employees', 'groups', 'chats', 'messages', 'chat_participants', 'notifications'
  ];

  const channel = sb.channel('realtime-sync');

  tablesToWatch.forEach(table => {
    channel.on(
      'postgres_changes',
      { event: '*', schema: 'public', table: table },
      (payload) => {
        console.log(`Realtime [${table}]:`, payload.eventType, payload);
        if (typeof onDataChanged === 'function') {
          onDataChanged(table, payload);
        }
      }
    );
  });

  channel.subscribe((status) => {
    console.log('Realtime статус:', status);
    if (status === 'SUBSCRIBED') {
      console.log('✅ Realtime подключен ко всем таблицам');
    }
  });

  return channel;
}
