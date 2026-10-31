import requests
import os
import time
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
    
    # Берем ровно 7 дней
    date_end = datetime.now()
    date_start = date_end - timedelta(days=7)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    current_date = date_start
    while current_date <= date_end:
        day_str = current_date.strftime('%Y-%m-%d')
        print(f"  ⏳ Запрос за {day_str}...")
        
        url = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"
        payload = {
            "selectedPeriod": {"start": day_str, "end": day_str},
            "nmIds": [int(x) for x in nm_ids],
            "limit": 100,
            "offset": 0
        }
        
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    products = data.get("data", {}).get("products", [])
                    
                    rows = []
                    for item in products:
                        product_info = item.get("product", {})
                        stats = item.get("statistic", {}).get("selected", {})
                        if not product_info or not stats: continue
                        
                        rows.append({
                            "nm_id": str(product_info.get("nmId")),
                            "view_count": stats.get("viewCount", 0),
                            "open_count": stats.get("openCount", 0),
                            "cart_count": stats.get("cartCount", 0),
                            "order_count": stats.get("orderCount", 0),
                            "buyout_count": stats.get("buyoutCount", 0),
                            "order_sum": stats.get("orderSum", 0),
                            "avg_price": stats.get("avgPrice", 0),
                            "cancel_count": stats.get("cancelCount", 0),
                            "cancel_sum": stats.get("cancelSum", 0),
                            "date": day_str
                        })
                    
                    if rows:
                        supabase.table("wb_funnel").upsert(rows, on_conflict="nm_id,date").execute()
                        print(f"    ✅ Сохранено: {len(rows)} записей")
                    
                    success = True
                    break # Успех, выходим из цикла попыток
                    
                elif response.status_code == 429:
                    retry_after = response.headers.get('X-Ratelimit-Retry')
                    wait_time = int(retry_after) if retry_after else 20
                    print(f"    ⚠️ 429 (попытка {attempt+1}). Ждем {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    print(f"    ❌ Ошибка API за {day_str}: {response.status_code} - {response.text[:100]}")
                    break
                    
            except Exception as e:
                print(f"    ❌ Ошибка за {day_str}: {e}")
                break
        
        # Если успешно скачали, делаем паузу 20 секунд перед следующим днем
        if success:
            time.sleep(20)
            
        current_date += timedelta(days=1)
        
    print("✅ Воронка обработана за все дни.")

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
        current_date = datetime.now().strftime('%Y-%m-%d')
        for nm_id in nm_ids:
            fbs_data = fbs_stocks.get(str(nm_id), {"qty": 0})
            fbo_data = fbo_stocks.get(str(nm_id), {"qty": 0})
            
            rows.append({
                "nm_id": str(nm_id),
                "fbs_quantity": int(fbs_data.get("qty", 0)),
                "fbo_quantity": int(fbo_data.get("qty", 0)),
                "updated_at": datetime.now().isoformat(),
                "date": current_date
            })
        if rows:
            supabase.table("wb_stocks").upsert(rows, on_conflict="nm_id,date").execute()
            print(f"✅ Остатки сохранены! Строк: {len(rows)}")
    except Exception as e:
        print(f"❌ Ошибка Supabase: {e}")

def fetch_promotions():
    print("🎁 Получение данных о промоакциях...")
    url = "https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions"
    params = {
        "startDateTime": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT00:00:00Z'),
        "endDateTime": (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%dT23:59:59Z'),
        "allPromo": True, # Важно: boolean, а не строка!
        "limit": 1000
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            promotions = data.get("data", {}).get("promoList", [])
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            rows = []
            for promo in promotions:
                rows.append({
                    "id": promo.get("id"),
                    "name": promo.get("name"),
                    "start_date": promo.get("startDate"),
                    "end_date": promo.get("endDate"),
                    "description": promo.get("description"),
                    "in_action": promo.get("inAction", False)
                })
            if rows:
                supabase.table("wb_promotions").upsert(rows, on_conflict="id").execute()
                print(f"✅ Промоакции сохранены: {len(rows)} записей")
        else:
            print(f"⚠️ Акции: {response.status_code} - {response.text[:500]}")
    except Exception as e:
        print(f"❌ Ошибка промоакций: {e}")

def fetch_prices():
    print("💰 Получение данных о ценах...")
    url = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"
    payload = {"limit": 1000, "offset": 0}
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            goods = data.get("data", {}).get("goods", [])
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            rows = []
            for good in goods:
                rows.append({
                    "nm_id": good.get("nmID"),
                    "price": good.get("price"),
                    "discount": good.get("discount"),
                    "discounted_price": good.get("discountedPrice"),
                    "club_discount": good.get("clubDiscount"),
                    "quarantine": good.get("quarantine")
                })
            if rows:
                supabase.table("wb_prices").upsert(rows, on_conflict="nm_id").execute()
                print(f"✅ Цены сохранены: {len(rows)} записей")
        else:
            print(f"⚠️ Цены: {response.status_code} - {response.text[:500]}")
    except Exception as e:
        print(f"❌ Ошибка цен: {e}")

def fetch_penalties():
    print("⚖️ Получение данных о штрафах...")
    print("ℹ️ Штрафы: метод финансовых отчетов требует ID отчета. Пропускаем сбор штрафов, чтобы не ломать синхронизацию.")
    return []

def fetch_returns():
    print("🔄 Получение данных о возвратах...")
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/item-returns"
    params = {
        "dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        "dateTo": datetime.now().strftime('%Y-%m-%d')
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            returns = data.get("data", {}).get("returns", [])
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            rows = []
            for ret in returns:
                rows.append({
                    "nm_id": ret.get("nmID"),
                    "return_date": ret.get("returnDate"),
                    "quantity": ret.get("quantity"),
                    "amount": ret.get("amount"),
                    "reason": ret.get("reason")
                })
            if rows:
                supabase.table("wb_returns").upsert(rows, on_conflict="id").execute()
                print(f"✅ Возвраты сохранены: {len(rows)} записей")
        elif response.status_code == 204:
            print("ℹ️ Возвратов за период нет (204 No Content)")
            return []
        else:
            print(f"⚠️ Возвраты: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"❌ Ошибка возвратов: {e}")

def fetch_ad_stats():
    print("📊 Получение статистики по рекламе...")
    print("⚠️ Реклама: ваш токен WB не имеет прав на чтение кампаний (403). Сгенерируйте новый токен с категорией 'Продвижение' или пропустите этот блок.")
    return []

if __name__ == "__main__":
    print("СТАРТ ПРОГРАММЫ")
    
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
        
        fetch_funnel(nm_ids)
        fetch_promotions()
        fetch_prices()
        fetch_penalties()
        fetch_returns()
        fetch_ad_stats()
        
        fbs_stocks = get_fbs_stocks(nm_ids)
        fbo_stocks = get_fbo_stocks(nm_ids)
        
        save_to_supabase(nm_ids, fbs_stocks, fbo_stocks)
        
    print("✅ Программа завершена")
