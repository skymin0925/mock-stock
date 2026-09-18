import os
import requests
import yfinance as yf

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

def get_stocks():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stocks?select=code,yf_symbol",
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    return [s for s in r.json() if s.get("yf_symbol")]

def update_stock(code, price, prev_close):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/stocks?code=eq.{code}",
        headers=HEADERS,
        json={
            "price": round(float(price), 2),
            "prev_close": round(float(prev_close), 2),
            "updated_at": "now()",
        },
        timeout=30,
    )
    r.raise_for_status()

def main():
    stocks = get_stocks()
    symbols = [s["yf_symbol"] for s in stocks]
    print(f"종목 {len(symbols)}개 시세 조회 중...")

    data = yf.download(
        symbols, period="5d", interval="1d",
        group_by="ticker", progress=False, auto_adjust=False, threads=False,
    )

    ok, fail = 0, 0
    for s in stocks:
        code, symbol = s["code"], s["yf_symbol"]
        try:
            closes = data[symbol]["Close"].dropna() if len(symbols) > 1 else data["Close"].dropna()
            if len(closes) < 1:
                raise ValueError("데이터 없음")
            price = closes.iloc[-1]
            prev = closes.iloc[-2] if len(closes) >= 2 else price
            update_stock(code, price, prev)
            print(f"  {code} {symbol}: {price:,.0f} (전일 {prev:,.0f})")
            ok += 1
        except Exception as e:
            print(f"  [실패] {code} {symbol}: {e}")
            fail += 1

    print(f"완료 — 성공 {ok}건, 실패 {fail}건")
    if ok == 0:
        raise SystemExit("모든 종목 갱신에 실패했습니다")

if __name__ == "__main__":
    main()