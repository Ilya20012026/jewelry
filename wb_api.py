import requests
from datetime import datetime
from supabase import create_client

# ============================================================
# НАСТРОЙКИ
# ============================================================
WB_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYwOTAzdjEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjMsImVudCI6MSwiZXhwIjoxODA4MjU5NTI0LCJmb3IiOiJzZWxmIiwiaWQiOiIwMWExNThkMi0wZmVkLTdjMjctOTc5OS0yNzE1NzI2NGQzYmQiLCJpaWQiOjExNjkwNTY0LCJvaWQiOjI1MDE1MzQxOSwicyI6MTA3Mzc0NTk2Niwic2lkIjoiOTYzZDIzZDktYjdjZC00YzAzLTg4MTktZjc5YjI5YmU3MTVhIiwidCI6ZmFsc2UsInVpZCI6MTE2OTA1NjR9.oMSbbjgiKf5i4CKCFlabA5LnTqVhMZJ3IcnYKlNiEktetISjH1YJfGo3i1UPh8e8qlBW64YHj9m_vxZa4gBHuA"
headers = {"Authorization": WB_TOKEN}

SUPABASE_URL = "https://kjiybjmisztrwymkwwsg.supabase.co"
SUPABASE_KEY = "sb_publishable_08SQ7121NYScNVQYffjjyg_mj-VWYv-"

# ============================================================
# ФУНКЦИИ
# ============================================================
def get_fbs_stocks(nm_ids):
    """Получает остатки на складах ПРОДАВЦА (FBS)"""
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/seller-warehouses"
    try:
        response = requests.post(url, headers=headers, json={})
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            result = {str(nm_id): 0 for nm_id in nm_ids}
            for item in items:
                nm_id = str(item.get('nmId'))
                if nm_id in result:
                    result[nm_id] += item.get('quantity', 0)
            return result
        return {}
    except Exception as e:
        print(f"❌ Ошибка FBS: {e}")
        return {}

def get_fbo_stocks(nm_ids):
    """Получает остатки на складах WB (FBO)"""
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"
    try:
        # Для FBO нужно передать список nmIds
        payload = {"nmIds": [int(x) for x in nm_ids]}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            result = {str(nm_id): 0 for nm_id in nm_ids}
            for item in items:
                nm_id = str(item.get('nmId'))
                if nm_id in result:
                    result[nm_id] += item.get('quantity', 0)
            return result
        return {}
    except Exception as e:
        print(f"❌ Ошибка FBO: {e}")
        return {}

def save_to_supabase(nm_ids, fbs_stocks, fbo_stocks):
    print("\n⏳ Сохраняем в Supabase...")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        rows = []
        for nm_id in nm_ids:
            rows.append({
                "nm_id": str(nm_id),
                "fbs_quantity": int(fbs_stocks.get(str(nm_id), 0)),
                "fbo_quantity": int(fbo_stocks.get(str(nm_id), 0)),
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
    
    # Получаем список товаров
    url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
    payload = {"settings": {"cursor": {"limit": 10}, "filter": {"withPhoto": -1}}}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            cards = response.json().get("cards", [])
            nm_ids = [str(card.get('nmID')) for card in cards if card.get('nmID')]
            
            # Получаем остатки
            print("📦 Запрашиваем FBS...")
            fbs_stocks = get_fbs_stocks(nm_ids)
            
            print("📦 Запрашиваем FBO...")
            fbo_stocks = get_fbo_stocks(nm_ids)
            
            # Выводим таблицу
            print("\n" + "="*70)
            print(f"{'Товар':<35} {'FBS':<10} {'FBO':<10}")
            print("="*70)
            for card in cards:
                nm_id = str(card.get('nmID'))
                title = card.get('title', 'Без названия')[:33]
                fbs = fbs_stocks.get(nm_id, 0)
                fbo = fbo_stocks.get(nm_id, 0)
                print(f"{title:<35} {fbs:<10} {fbo:<10}")
            print("="*70)
            
            # Сохраняем в базу
            save_to_supabase(nm_ids, fbs_stocks, fbo_stocks)
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")