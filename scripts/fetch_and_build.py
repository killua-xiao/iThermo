#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取并计算全球主要宽基指数估值，输出 public/data/data.json
- A股（上证指数、沪深300）优先使用 Tushare / AkShare（可拓展）；
- 海外（标普500、纳斯达克100、恒生、恒生科技）用 yfinance 近似（PE/PB可能受限，以替代方案计算历史分位）。
注意：请在运行环境配置 TUSHARE_TOKEN 环境变量。
"""
import os, sys, json, time, math, datetime as dt
from pathlib import Path

# 第三方库（在 Netlify Build 中通过 requirements.txt 安装）
try:
    import yfinance as yf
except Exception as e:
    print("yfinance not available:", e)

try:
    import tushare as ts
except Exception as e:
    ts = None
    print("tushare not available:", e)

DATA_PATH = Path(__file__).resolve().parents[1] / 'public' / 'data' / 'data.json'

INDEX_DEFS = [
    {"code":"000001.SS","name":"上证指数","market":"cn"},
    {"code":"000300.SH","name":"沪深300","market":"cn"},
    {"code":"^GSPC","name":"标普500","market":"us"},
    {"code":"^NDX","name":"纳斯达克100","market":"us"},
    {"code":"^HSI","name":"恒生指数","market":"hk"},
    {"code":"^HSTECH","name":"恒生科技指数","market":"hk"},
]

# 海外指数使用 ETF 代理以尝试获取估值口径（若不可用则回退为价格分位）
ETF_PROXY = {
    "^GSPC": "SPY",      # 标普500 -> SPDR S&P 500 ETF
    "^NDX": "QQQ",       # 纳指100 -> Invesco QQQ Trust
    "^HSI": "2800.HK",   # 恒生指数 -> 追踪HSI的ETF
    "^HSTECH": "3067.HK" # 恒生科技 -> iShares Hang Seng TECH ETF（或 3033.HK）
}


def percentile_of_latest(series):
    """给定一个时间序列（list 或 pd.Series），计算最新值在历史中的分位（0-1）。
    若数据不足返回 None。
    """
    try:
        arr = [x for x in series if x is not None and not (isinstance(x, float) and math.isnan(x))]
        if len(arr) < 10:
            return None
        latest = arr[-1]
        sorted_arr = sorted(arr)
        # 近似分位：位置/长度
        idx = max(0, min(len(sorted_arr)-1, sorted_arr.index(latest)))
        return round(idx / max(1, (len(sorted_arr)-1)), 4)
    except Exception:
        return None


def determine_status(pe_pct, pb_pct):
    """根据分位判定估值状态（低估/中性/高估）。规则可调整。"""
    vals = [v for v in [pe_pct, pb_pct] if v is not None]
    if not vals:
        return 'neutral'
    avg = sum(vals) / len(vals)
    if avg <= 0.3:
        return 'low'
    if avg >= 0.7:
        return 'high'
    return 'neutral'


def fetch_price_yf(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.history(period='1mo', interval='1d')
        if info is None or info.empty:
            return None
        return float(info['Close'].iloc[-1])
    except Exception:
        return None


def fetch_cn_index_tushare(ts_code):
    """示例：获取沪深指数的日线点位；估值指标需要更复杂计算（留接口）。"""
    if ts is None:
        return None, None
    pro = ts.pro_api(os.getenv('TUSHARE_TOKEN',''))
    try:
        daily = pro.index_daily(ts_code=ts_code, start_date='20120101')
        price = float(daily['close'].iloc[-1]) if len(daily)>0 else None
        return price, daily
    except Exception:
        return None, None


def fetch_cn_index_valuation_series(ts_code):
    """获取沪深指数的估值时间序列（pe、pe_ttm、pb）。优先用于上证综指与沪深300。"""
    if ts is None:
        return None
    pro = ts.pro_api(os.getenv('TUSHARE_TOKEN',''))
    try:
        df = pro.index_dailybasic(ts_code=ts_code, start_date='20120101', fields='ts_code,trade_date,pe,pe_ttm,pb')
        if df is None or len(df) == 0:
            # 个别场景沪深300可能在 399300.SZ，可尝试备用代码
            alt = '399300.SZ' if ts_code == '000300.SH' else None
            if alt:
                df = pro.index_dailybasic(ts_code=alt, start_date='20120101', fields='ts_code,trade_date,pe,pe_ttm,pb')
        if df is None or len(df) == 0:
            return None
        # 按日期升序
        df = df.sort_values('trade_date')
        return df
    except Exception:
        return None


def build_percentile_history_from_df(df):
    """基于包含 trade_date, pe_ttm, pb 的 DataFrame 计算每日的历史分位（从起始到当日）。"""
    try:
        if df is None or len(df) < 30:
            return [], None, None, None, None
        pe_series = []
        pb_series = []
        hist = []
        pe_vals = []
        pb_vals = []
        dates = list(df['trade_date'])
        for i in range(len(df)):
            pe_val = df['pe_ttm'].iloc[i]
            pb_val = df['pb'].iloc[i]
            # 记录完整估值数列便于输出当前值
            pe_vals.append(None if pe_val is None or (isinstance(pe_val, float) and math.isnan(pe_val)) else float(pe_val))
            pb_vals.append(None if pb_val is None or (isinstance(pb_val, float) and math.isnan(pb_val)) else float(pb_val))
            # 计算分位（截至当日）
            pe_series.append(percentile_of_latest([x for x in pe_vals if x is not None]))
            pb_series.append(percentile_of_latest([x for x in pb_vals if x is not None]))
            hist.append({
                "date": str(dates[i]),
                "pe_percentile": pe_series[-1],
                "pb_percentile": pb_series[-1]
            })
        latest_pe = pe_vals[-1]
        latest_pb = pb_vals[-1]
        latest_pe_pct = pe_series[-1]
        latest_pb_pct = pb_series[-1]
        return hist[-365:], latest_pe_pct, latest_pb_pct, latest_pe, latest_pb
    except Exception:
        return [], None, None, None, None


def build_history_percentiles(prices):
    # 使用价格替代估值分位，作为演示（真实生产应换为 PE/PB 时间序列）
    if prices is None or len(prices) < 30:
        return [], None, None
    closes = list(prices['close']) if hasattr(prices, '__getitem__') and 'close' in prices else [float(x) for x in prices]
    dates = list(prices['trade_date']) if hasattr(prices, '__getitem__') and 'trade_date' in prices else []
    hist = []
    pe_series = []
    pb_series = []
    for i in range(len(closes)):
        window = closes[:i+1]
        pe_series.append(percentile_of_latest(window))
        pb_series.append(percentile_of_latest(window))
        d = dates[i] if i < len(dates) else ''
        hist.append({"date": str(d), "pe_percentile": pe_series[-1], "pb_percentile": pb_series[-1]})
    pe_pct = pe_series[-1]
    pb_pct = pb_series[-1]
    return hist[-365:], pe_pct, pb_pct


def main():
    output = {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "indexes": []}
    for item in INDEX_DEFS:
        code = item['code']
        name = item['name']
        price = None
        history = []
        pe_pct = None
        pb_pct = None
        pe_ttm = None
        pb = None

        if item['market'] == 'cn' and ts is not None:
            # 转换 tushare 指数代码
            ts_code = '000300.SH' if code=='000300.SH' else ('000001.SH' if code=='000001.SS' else None)
            if ts_code:
                price, daily = fetch_cn_index_tushare(ts_code)
                # 真实估值序列（pe/pb）
                val_df = fetch_cn_index_valuation_series(ts_code)
                if val_df is not None and len(val_df) > 0:
                    hist, pe_pct, pb_pct, pe_ttm, pb = build_percentile_history_from_df(val_df)
                    history = hist
                elif daily is not None and len(daily)>0:
                    # 回退：价格分位
                    hist, pe_pct, pb_pct = build_history_percentiles(daily)
                    history = hist
        # 海外与兜底使用 yfinance 获取点位，并用收盘价历史近似分位
        if price is None:
            price = fetch_price_yf(code)
            try:
                t = yf.Ticker(code)
                h = t.history(period='5y', interval='1d')
                if h is not None and not h.empty:
                    closes = list(h['Close'].fillna(method='ffill'))
                    dates = [d.date().isoformat() for d in h.index]
                    tmp = []
                    pe_series = []
                    pb_series = []
                    for i in range(len(closes)):
                        window = closes[:i+1]
                        pe_series.append(percentile_of_latest(window))
                        pb_series.append(percentile_of_latest(window))
                        tmp.append({"date": dates[i], "pe_percentile": pe_series[-1], "pb_percentile": pb_series[-1]})
                    history = tmp[-365:]
                    pe_pct = pe_series[-1]
                    pb_pct = pb_series[-1]
            except Exception:
                pass

        # 对于海外指数，尝试通过 ETF 代理补充当前 PE/PB（若可用）
        if item['market'] in ('us','hk'):
            proxy = ETF_PROXY.get(code)
            if proxy:
                try:
                    etf = yf.Ticker(proxy)
                    info = getattr(etf, 'info', None) or {}
                    if isinstance(info, dict) and info:
                        if pe_ttm is None:
                            pe_ttm = info.get('trailingPE') or info.get('trailingPe') or info.get('trailingP/E')
                        if pb is None:
                            pb = info.get('priceToBook') or info.get('priceToBookMRQ')
                except Exception:
                    pass

        status = determine_status(pe_pct, pb_pct)
        output['indexes'].append({
            "code": code,
            "name": name,
            "price": price,
            "valuation_status": status,
            "pe_ttm": pe_ttm,
            "pb": pb,
            "pe_percentile": pe_pct,
            "pb_percentile": pb_pct,
            "history": history,
            "trend_text": None
        })

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("wrote", DATA_PATH)

if __name__ == '__main__':
    main()