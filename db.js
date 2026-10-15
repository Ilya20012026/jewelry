/* ============================================================
   db.js — локальная база данных (IndexedDB)
   Хранит те же данные, что раньше были в localStorage,
   но надёжнее и с запасом под синхронизацию.
   ============================================================ */

const DB_NAME = "jewelry_local";
const DB_VERSION = 1;
const STORE = "kv"; // key-value хранилище
const DATA_KEY = "appdata"; // ключ, под которым лежит весь объект data

let _db = null;

function openDB() {
  return new Promise((resolve, reject) => {
    if (_db) return resolve(_db);
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    req.onsuccess = e => { _db = e.target.result; resolve(_db); };
    req.onerror = e => reject(e.target.error);
  });
}

async function dbGet(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function dbSet(key, value) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const req = tx.objectStore(STORE).put(value, key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function dbDelete(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const req = tx.objectStore(STORE).delete(key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

/* ---------- Публичные функции для приложения ---------- */

/** Загружает объект data из IndexedDB (или null, если пусто) */
async function loadData() {
  const raw = await dbGet(DATA_KEY);
  if (!raw) return null;
  try {
    return typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (e) {
    console.error("Ошибка чтения данных:", e);
    return null;
  }
}

/** Сохраняет объект data в IndexedDB */
async function saveData(data) {
  await dbSet(DATA_KEY, data);
}

/** Удаляет все данные */
async function clearData() {
  await dbDelete(DATA_KEY);
}

/* ---------- Миграция из localStorage (один раз) ---------- */
async function migrateFromLocalStorage() {
  const existing = await loadData();
  if (existing) return existing; // уже мигрировали

  const old = localStorage.getItem("jewelry_v2");
  if (!old) return null; // и мигрировать нечего

  try {
    const parsed = JSON.parse(old);
    await saveData(parsed);
    console.log("✅ Данные перенесены из localStorage в IndexedDB");
    return parsed;
  } catch (e) {
    console.error("Ошибка миграции:", e);
    return null;
  }
}