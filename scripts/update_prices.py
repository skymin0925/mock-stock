import os
import time
from datetime import datetime, timedelta, timezone

import requests
import yfinance as yf

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
LOOP_MINUTES = int(os.environ.get("LOOP_MINUTES", "0"))  # 0이면 1회만 실행

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}
KST = timezone(timedelta(hours=9))


def get_stocks():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/stocks?select=code,yf_symbol",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [s for s in r.json() if s.get("yf_symbol")]


def is_market_open():
    now = datetime.now(KST)
    if now.weekday() >= 5:           # 토·일
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 15 * 60 + 40


def cleanup_history():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    requests.delete(f"{SUPABASE_URL}/rest/v1/price_history?ts=lt.{cutoff}",
                    headers=HEADERS, timeout=30)


def fetch_prev_closes(symbols):
    """전일 종가 (등락률 계산용)"""
    result = {}
    data = yf.download(symbols, period="7d", interval="1d", group_by="ticker",
                       progress=False, auto_adjust=False, threads=False)
    for sym in symbols:
        try:
            closes = (data[sym]["Close"] if len(symbols) > 1 else data["Close"]).dropna()
            if len(closes) >= 2:
                result[sym] = float(closes.iloc[-2])
            elif len(closes) == 1:
                result[sym] = float(closes.iloc[-1])
        except Exception as e:
            print(f"  [전일종가 실패] {sym}: {e}")
    return result


def fetch_prices(symbols):
    """1분봉 기준 최신가"""
    result = {}
    data = yf.download(symbols, period="1d", interval="1m", group_by="ticker",
                       progress=False, auto_adjust=False, threads=False)
    for sym in symbols:
        try:
            closes = (data[sym]["Close"] if len(symbols) > 1 else data["Close"]).dropna()
            if len(closes) >= 1:
                result[sym] = float(closes.iloc[-1])
        except Exception as e:
            print(f"  [시세 실패] {sym}: {e}")
    return result


def save(stocks, prices, prev_closes):
    rows = []
    for s in stocks:
        code, sym = s["code"], s["yf_symbol"]
        price = prices.get(sym)
        if not price:
            continue
        body = {"price": round(price, 2), "updated_at": "now()"}
        if sym in prev_closes:
            body["prev_close"] = round(prev_closes[sym], 2)
        requests.patch(f"{SUPABASE_URL}/rest/v1/stocks?code=eq.{code}",
                       headers=HEADERS, json=body, timeout=30)
        rows.append({"code": code, "price": round(price, 2)})

    if rows:   # 차트용 기록은 한 번에 저장
        requests.post(f"{SUPABASE_URL}/rest/v1/price_history",
                      headers=HEADERS, json=rows, timeout=30)
    return len(rows)


def main():
    stocks = get_stocks()
    symbols = [s["yf_symbol"] for s in stocks]
    print(f"대상 종목 {len(symbols)}개")

    cleanup_history()
    prev_closes = fetch_prev_closes(symbols)
    print(f"전일 종가 {len(prev_closes)}개 확보")

    deadline = time.time() + LOOP_MINUTES * 60
    while True:
        started = time.time()
        if is_market_open():
            try:
                prices = fetch_prices(symbols)
                n = save(stocks, prices, prev_closes)
                print(f"[{datetime.now(KST):%H:%M:%S}] {n}개 갱신")
            except Exception as e:
                print(f"[{datetime.now(KST):%H:%M:%S}] 갱신 실패: {e}")
        else:
            print(f"[{datetime.now(KST):%H:%M:%S}] 장 시간이 아닙니다")

        if LOOP_MINUTES == 0 or time.time() >= deadline:
            break
        time.sleep(max(0, 60 - (time.time() - started)))

    print("종료")


if __name__ == "__main__":
    main()