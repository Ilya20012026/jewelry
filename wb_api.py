import requests
import os
from datetime import datetime, timedelta
from supabase import create_client

# ============================================================
# НАСТРОЙКИ
# ============================================================
# Токен берется из настроек GitHub (или из переменной окружения)
WB_TOKEN = os.environ.get("WB_TOKEN")
headers = {"Authorization": WB_TOKEN}

# Если токена нет (например, при локальном запуске), подставь его вручную:
if not WB_TOKEN:
    WB_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYwOTAzdjEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjMsImVudCI6MSwiZXhwIjoxODA4MjU5NTI0LCJmb3IiOiJzZWxmIiwiaWQiOiIwMWExNThkMi0wZmVkLTdjMjctOTc5OS0yNzE1NzI2NGQzYmQiLCJpaWQiOjExNjkwNTY0LCJvaWQiOjI1MDE1MzQxOSwicyI6MTA3Mzc0NTk2Niwic2lkIjoiOTYzZDIzZDktYjdjZC00YzAzLTg4MTktZjc5YjI5YmU3MTVhIiwidCI6ZmFsc2UsInVpZCI6MTE2OTA1NjR9.oMSbbjgiKf5i4CKCFlabA5LnTqVhMZJ3IcnYKlNiEktetISjH1YJfGo3i1UPh8e8qlBW64YHj9m_vxZa4gBHuA"

# ВОТ ЭТА СТРОКА БЫЛА ПРОПУЩЕНА! Без нее не работает авторизация.
headers = {"Authorization": WB_TOKEN}

SUPABASE_URL = "https://kjiybjmisztrwymkwwsg.supabase.co"
SUPABASE_KEY = "sb_publishable_08SQ7121NYScNVQYffjjyg_mj-VWYv-"

# ============================================================
# ФУНКЦИИ
# ============================================================

def get_fbs_stocks(nm_ids):
    """Получает остатки на складах ПРОДАВЦА (FBS) через seller-analytics-api"""
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/seller-warehouses"
    try:
        response = requests.post(url, headers=headers, json={})
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            result = {str(nm_id): {"qty": 0, "in_way": 0} for nm_id in nm_ids}
            for item in items:
                nm_id = str(item.get('nmId'))
                if nm_id in result:
                    result[nm_id]["qty"] += item.get('quantity', 0)
            return result
        else:
            print(f"❌ Ошибка FBS: {response.status_code} - {response.text}")
            return {}
    except Exception as e:
        print(f"❌ Ошибка FBS: {e}")
        return {}

def get_fbo_stocks(nm_ids):
    """Получает остатки на складах WB (FBO)"""
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"
    try:
        payload = {"nmIds": [int(x) for x in nm_ids]}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            result = {str(nm_id): {"qty": 0, "in_way": 0} for nm_id in nm_ids}
            for item in items:
                nm_id = str(item.get('nmId'))
                if nm_id in result:
                    result[nm_id]["qty"] += item.get('quantity', 0)
                    # Суммируем показатели "в пути" для FBO
                    in_way_to_client = item.get('inWayToClient', 0)
                    in_way_from_client = item.get('inWayFromClient', 0)
                    result[nm_id]["in_way"] += in_way_to_client + in_way_from_client
            return result
        return {}
    except Exception as e:
        print(f"❌ Ошибка FBO: {e}")
        return {}

def save_to_supabase(nm_ids, fbs_stocks, fbo_stocks, cards):
    print("\n⏳ Сохраняем в Supabase...")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        rows = []
        for nm_id in nm_ids:
            article = "N/A"
            title = "Без названия"
            for card in cards:
                if str(card.get('nmID')) == str(nm_id):
                    article = card.get('vendorCode') or "N/A"
                    title = card.get('title') or "Без названия"
                    break
            
            # Получаем данные с учетом новой структуры
            fbs_data = fbs_stocks.get(str(nm_id), {"qty": 0, "in_way": 0})
            fbo_data = fbo_stocks.get(str(nm_id), {"qty": 0, "in_way": 0})
            
            rows.append({
                "nm_id": str(nm_id),
                "article": article,
                "title": title,
                "fbs_quantity": int(fbs_data.get("qty", 0)),
                "fbo_quantity": int(fbo_data.get("qty", 0)),
                "in_way_fbs": int(fbs_data.get("in_way", 0)),
                "in_way_fbo": int(fbo_data.get("in_way", 0)),
                "updated_at": datetime.now().isoformat()
            })
        if rows:
            supabase.table("wb_stocks").upsert(rows).execute()
            print(f"✅ Успешно сохранено! Строк: {len(rows)}")
    except Exception as e:
        print(f"❌ Ошибка Supabase: {e}")

# ============================================================
# ОСНОВНОЙ КОД
# ============================================================
if __name__ == "__main__":
    print("СТАРТ ПРОГРАММЫ")
    
    url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
    payload = {"settings": {"cursor": {"limit": 10}, "filter": {"withPhoto": -1}}}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            cards = response.json().get("cards", [])
            nm_ids = [str(card.get('nmID')) for card in cards if card.get('nmID')]
            
            print("📦 Запрашиваем FBS...")
            fbs_stocks = get_fbs_stocks(nm_ids)
            
            print("📦 Запрашиваем FBO...")
            fbo_stocks = get_fbo_stocks(nm_ids)
            
            print("\n" + "="*70)
            print(f"{'Товар':<35} {'FBS':<10} {'FBO':<10}")
            print("="*70)
            
            for card in cards:
                nm_id = str(card.get('nmID'))
                title = card.get('title', 'Без названия')[:33]
                
                # Безопасно достаем данные из словаря
                fbs_val = fbs_stocks.get(nm_id, {})
                fbs = fbs_val.get('qty', 0) if isinstance(fbs_val, dict) else 0
                
                fbo_val = fbo_stocks.get(nm_id, {})
                fbo = fbo_val.get('qty', 0) if isinstance(fbo_val, dict) else 0
                
                print(f"{title:<35} {fbs:<10} {fbo:<10}")
                
            print("="*70)
            
            save_to_supabase(nm_ids, fbs_stocks, fbo_stocks, cards)
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
