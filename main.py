from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import time

app = FastAPI()

# 允許你的 App (跨網域) 存取後台
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 在記憶體中建立多幣別快取字典 (In-Memory Cache)
cached_data = {}
ONE_DAY_SECONDS = 86400  # 24 小時的秒數
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

def fetch_rates_from_providers(base: str):
    base = base.upper()
    """多重備案獲取匯率"""
    urls = [
        "https://open.er-api.com/v6/latest/USD",
        "https://api.frankfurter.app/latest?from=USD",
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
    ]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                # 兼容不同第三方 API 的 key 格式
                rates = data.get("rates") or data.get(base.lower())
                if rates:
                    return rates
        except Exception:
            continue
    return None


@app.get("/api/rates")
def get_rates(base: str = Query("USD", description="請傳入基準幣別，例如 TWD, USD, HKD")):
    global cached_data
    base = base.upper()
    current_time = time.time()

    # 檢查該幣別是否有快取，且快取距離上次更新時間未超過 24 小時
    if base in cached_data:
        cache_entry = cached_data[base]
        if (current_time - cache_entry["timestamp"]) < ONE_DAY_SECONDS:
            return {
                "status": "success",
                "source": "cache",
                "base": base,
                "timestamp": cache_entry["timestamp"],
                "rates": cache_entry["rates"]
            }

    # 若無快取或快取過期，去外部抓取最新匯率
    fresh_rates = fetch_rates_from_providers(base)
    if fresh_rates:
        cached_data[base] = {
            "timestamp": current_time,
            "rates": fresh_rates
        }
        return {
            "status": "success",
            "source": "live",
            "base": base,
            "timestamp": current_time,
            "rates": fresh_rates
        }

    # 降級容錯：如果外部 API 全掛了，但記憶體有舊資料，至少先吐出舊資料給用戶
    if base in cached_data:
        return {
            "status": "warning",
            "message": "Fetch failed, serving stale cache",
            "base": base,
            "timestamp": cached_data[base]["timestamp"],
            "rates": cached_data[base]["rates"]
        }

    return {"status": "error", "message": "無法取得即時匯率數據"}
