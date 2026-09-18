import os
import time
from datetime import datetime, timedelta, timezone

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
KIS_APP_KEY = os.environ["KIS_APP_KEY"]
KIS_APP_SECRET = os.environ["KIS_APP_SECRET"]

LOOP_MINUTES = int(os.environ.get("LOOP_MINUTES", "0"))
INTERVAL = int(os.environ.get("INTERVAL_SECONDS", "20"))   # 시세 갱신 주기(초)

KIS_BASE = "https://openapi.koreainvestment.com:9443"
KST = timezone(timedelta(hours=9))

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

_token = {"value": None, "expires": 0}


def kis_token():
    """접근토큰 (24시간 유효). 자주 재발급하면 차단되므로 캐싱한다."""
    if _token["value"] and time.time() < _token["expires"]:
        return _token["value"]
    r = requests.post(f"{KIS_BASE}/oauth2/tokenP", json={
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
    }, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"토큰 발급 실패 {r.status_code}: {r.text[:200]}")
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + 60 * 60 * 12
    print("접근토큰 발급 완료")
    return _token["value"]


def kis_quote(code):
    """국내주식 현재가 조회 → (현재가, 전일종가)"""
    r = requests.get(
        f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers={
            "authorization": f"Bearer {kis_token()}",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
            "tr_id": "FHKST01010100",
            "custtype": "P",
        },
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("rt_cd") not in (None, "0"):
        raise RuntimeError(f"{body.get('msg_cd')} {body.get('msg1')}")
    out = body.get("output") or {}
    return float(out.get("stck_prpr") or 0), float(out.get("stck_sdpr") or 0)


def get_stocks():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/stocks?select=code,name",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def is_market_open():
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 15 * 60 + 40


def cleanup_history():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    requests.delete(f"{SUPABASE_URL}/rest/v1/price_history?ts=lt.{cutoff}",
                    headers=HEADERS, timeout=30)


def update_once(stocks, save_history):
    rows, failed = [], 0
    for s in stocks:
        code = s["code"]
        try:
            price, base = kis_quote(code)
            if price <= 0:
                continue
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/stocks?code=eq.{code}",
                headers=HEADERS,
                json={"price": price, "prev_close": base, "updated_at": "now()"},
                timeout=30)
            rows.append({"code": code, "price": price})
        except Exception as e:
            failed += 1
            print(f"  [실패] {code}: {e}")
        time.sleep(0.08)      # 초당 호출 제한 회피

    if rows and save_history:
        requests.post(f"{SUPABASE_URL}/rest/v1/price_history",
                      headers=HEADERS, json=rows, timeout=30)

    return len(rows), failed


def main():
    stocks = get_stocks()
    print(f"대상 종목 {len(stocks)}개 · 갱신 주기 {INTERVAL}초")
    cleanup_history()

    deadline = time.time() + LOOP_MINUTES * 60
    last_history = 0

    while True:
        started = time.time()
        if is_market_open():
            # 차트 기록은 1분에 한 번만 저장
            save_history = (started - last_history) >= 60
            ok, failed = update_once(stocks, save_history)
            if save_history:
                last_history = started
            print(f"[{datetime.now(KST):%H:%M:%S}] {ok}개 갱신"
                  + (f" (실패 {failed})" if failed else ""))
        else:
            print(f"[{datetime.now(KST):%H:%M:%S}] 장 시간이 아닙니다")
            time.sleep(30)

        if LOOP_MINUTES == 0 or time.time() >= deadline:
            break
        time.sleep(max(0, INTERVAL - (time.time() - started)))

    print("종료")


if __name__ == "__main__":
    main()