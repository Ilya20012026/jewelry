import requests
import os
from datetime import datetime, timedelta
from supabase import create_client

# ============================================================
# НАСТРОЙКИ
# ============================================================
WB_TOKEN = os.environ.get("WB_TOKEN")
if not WB_TOKEN:
    WB_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYwOTAzdjEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjMsImVudCI6MSwiZXhwIjoxODA4MjU5NTI0LCJmb3IiOiJzZWxmIiwiaWQiOiIwMWExNThkMi0wZmVkLTdjMjctOTc5OS0yNzE1NzI2NGQzYmQiLCJpaWQiOjExNjkwNTY0LCJvaWQiOjI1MDE1MzQxOSwicyI6MTA3Mzc0NTk2Niwic2lkIjoiOTYzZDIzZDktYjdjZC00YzAzLTg4MTktZjc5YjI5YmU3MTVhIiwidCI6ZmFsc2UsInVpZCI6MTE2OTA1NjR9.oMSbbjgiKf5i4CKCFlabA5LnTqVhMZJ3IcnYKlNiEktetISjH1YJfGo3i1UPh8e8qlBW64YHj9m_vxZa4gBHuA"

headers = {"Authorization": WB_TOKEN}
SUPABASE_URL = "https://kjiybjmisztrwymkwwsg.supabase.co"
SUPABASE_KEY = "sb_publishable_08SQ7121NYScNVQYffjjyg_mj-VWYv-"

def fetch_funnel(nm_ids):
    print("📊 Получение данных воронки...")
    if not nm_ids:
        print("❌ Нет nm_id для запроса воронки")
        return
    
    date_end = datetime.now().strftime('%Y-%m-%d')
    date_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"
    payload = {
        "selectedPeriod": {"start": date_start, "end": date_end},
        "nmIds": [int(x) for x in nm_ids],
        "limit": 100,
        "offset": 0
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            products = data.get("data", {}).get("products", [])
            
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            rows = []
            for item in products:
                product_info = item.get("product", {})
                stats = item.get("statistic", {}).get("selected", {})
                if not product_info or not stats: continue
                    
                rows.append({
                    "nm_id": str(product_info.get("nmId")),
                    "open_count": stats.get("openCount", 0),
                    "cart_count": stats.get("cartCount", 0),
                    "order_count": stats.get("orderCount", 0),
                    "buyout_count": stats.get("buyoutCount", 0)
                })
            
            if rows:
                supabase.table("wb_funnel").upsert(rows).execute()
                print(f"✅ Воронка сохранена в Supabase: {len(rows)} записей!")
        else:
            print(f"❌ Ошибка воронки: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Ошибка воронки: {e}")

def get_fbs_stocks(nm_ids):
    print("📦 Запрашиваем FBS...")
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
        return {}
    except Exception as e:
        print(f"❌ Ошибка FBS: {e}")
        return {}

def get_fbo_stocks(nm_ids):
    print("📦 Запрашиваем FBO...")
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
            return result
        return {}
    except Exception as e:
        print(f"❌ Ошибка FBO: {e}")
        return {}

def save_to_supabase(nm_ids, fbs_stocks, fbo_stocks):
    print("\n⏳ Сохраняем остатки в Supabase...")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        rows = []
        for nm_id in nm_ids:
            fbs_data = fbs_stocks.get(str(nm_id), {"qty": 0})
            fbo_data = fbo_stocks.get(str(nm_id), {"qty": 0})
            
            rows.append({
                "nm_id": str(nm_id),
                "fbs_quantity": int(fbs_data.get("qty", 0)),
                "fbo_quantity": int(fbo_data.get("qty", 0)),
                "updated_at": datetime.now().isoformat()
            })
        if rows:
            supabase.table("wb_stocks").upsert(rows).execute()
            print(f"✅ Остатки сохранены! Строк: {len(rows)}")
    except Exception as e:
        print(f"❌ Ошибка Supabase: {e}")

if __name__ == "__main__":
    print("СТАРТ ПРОГРАММЫ")
    
    # Берем nm_ids ПРЯМО ИЗ БАЗЫ (карточки там уже есть)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        res = supabase.table("wb_cards").select("nm_id").execute()
        nm_ids = [item["nm_id"] for item in res.data] if res.data else []
    except Exception as e:
        print(f"❌ Ошибка чтения базы: {e}")
        nm_ids = []

    if not nm_ids:
        print("❌ В базе нет карточек! Сначала нужно их скачать.")
    else:
        print(f"📋 Найдено в базе товаров: {len(nm_ids)}")
        
        # 1. Запускаем воронку
        fetch_funnel(nm_ids)
        
        # 2. Запускаем остатки
        fbs_stocks = get_fbs_stocks(nm_ids)
        fbo_stocks = get_fbo_stocks(nm_ids)
        
        # 3. Сохраняем остатки
        save_to_supabase(nm_ids, fbs_stocks, fbo_stocks)
        
    print("✅ Программа завершена")