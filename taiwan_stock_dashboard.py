"""
台股籌碼分析 Streamlit Dashboard
資料來源：FinMind API (https://finmindtrade.com)
"""

import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

st.set_page_config(
    page_title="台股籌碼分析儀表板",
    page_icon="📊",
    layout="wide"
)

# ── 語言設定 ──────────────────────────────────────────────

LANG = {
    "zh": {
        "title": "📊 台股籌碼分析儀表板",
        "caption": "資料來源：FinMind API",
        "settings": "⚙️ 設定",
        "stock_input": "股票代號",
        "stock_placeholder": "例：2330",
        "days_label": "查詢天數（交易日）",
        "reload": "🔄 重新載入資料",
        "loading": "載入資料中...",
        "no_data": "無法取得資料，請確認股票代號是否正確。",
        "tabs": ["K線圖", "三大法人", "融資融券", "外資持股", "基本面", "新聞"],
        "summary": "籌碼摘要",
        "foreign": "外資",
        "trust": "投信",
        "dealer": "自營商",
        "total": "三大法人合計",
        "unit": "張",
        "price": "股價",
        "open": "開盤", "high": "最高", "low": "最低", "close": "收盤",
        "volume": "成交量",
        "chart1_title": "三大法人每日買賣超",
        "chart2_title": "三大法人合計 & 累積",
        "daily": "每日合計",
        "cumulative": "累積",
        "chart3_title": "融資融券餘額",
        "margin_bal": "融資餘額", "short_bal": "融券餘額",
        "margin_chg": "融資增減", "short_chg": "融券增減",
        "chart4_title": "外資持股比例",
        "ratio_label": "持股比例（%）",
        "per_title": "PER / PBR",
        "per": "本益比(PER)", "pbr": "股價淨值比(PBR)", "yield": "殖利率(%)",
        "news_title": "最新相關新聞",
        "no_news": "無新聞資料",
        "raw_data": "📋 原始資料",
        "date": "日期",
        "no_margin": "融資融券資料無法取得",
        "no_foreign": "外資持股比例資料無法取得",
        "no_per": "PER/PBR 資料無法取得",
    },
    "en": {
        "title": "📊 Taiwan Stock Chip Analysis",
        "caption": "Data source: FinMind API",
        "settings": "⚙️ Settings",
        "stock_input": "Stock ID",
        "stock_placeholder": "e.g. 2330",
        "days_label": "Trading Days",
        "reload": "🔄 Reload Data",
        "loading": "Loading data...",
        "no_data": "Unable to fetch data. Please check the stock ID.",
        "tabs": ["Candlestick", "Institutions", "Margin", "Foreign", "Fundamentals", "News"],
        "summary": "Weekly Summary",
        "foreign": "Foreign",
        "trust": "Investment Trust",
        "dealer": "Dealer",
        "total": "3 Institutions",
        "unit": "lots",
        "price": "Price",
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
        "volume": "Volume",
        "chart1_title": "Daily Net Buy/Sell",
        "chart2_title": "Total & Cumulative",
        "daily": "Daily",
        "cumulative": "Cumulative",
        "chart3_title": "Margin Trading Balance",
        "margin_bal": "Margin Bal", "short_bal": "Short Bal",
        "margin_chg": "Margin Chg", "short_chg": "Short Chg",
        "chart4_title": "Foreign Ownership",
        "ratio_label": "Ownership (%)",
        "per_title": "PER / PBR",
        "per": "PER", "pbr": "PBR", "yield": "Dividend Yield(%)",
        "news_title": "Latest News",
        "no_news": "No news available",
        "raw_data": "📋 Raw Data",
        "date": "Date",
        "no_margin": "Margin trading data unavailable",
        "no_foreign": "Foreign ownership data unavailable",
        "no_per": "PER/PBR data unavailable",
    }
}

# ── 資料抓取函數 ──────────────────────────────────────────

def get_start_date(days):
    return (datetime.today() - timedelta(days=days + 14)).strftime("%Y-%m-%d")


@st.cache_data(ttl=3600)
def fetch(dataset, stock_id, start_date):
    try:
        res = requests.get(FINMIND_URL, params={
            "dataset": dataset,
            "data_id": stock_id,
            "start_date": start_date,
        }, timeout=15)
        data = res.json()
        if data.get("status") != 200 or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"{dataset} 錯誤: {e}")
        return pd.DataFrame()


def get_institutional(stock_id, start_date):
    df = fetch("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date)
    if df.empty:
        return pd.DataFrame()
    df["net"] = (df["buy"].astype(float) - df["sell"].astype(float)) / 1000
    name_map = {
        "Foreign_Investor": "foreign",
        "Investment_Trust": "trust",
        "Dealer_self": "dealer",
        "Dealer_Hedging": "dealer",
    }
    result = {}
    for _, row in df.iterrows():
        d = row["date"]
        col = name_map.get(row.get("name", ""))
        if col is None:
            continue
        if d not in result:
            result[d] = {"date": d, "foreign_net": 0.0, "trust_net": 0.0, "dealer_net": 0.0}
        result[d][f"{col}_net"] += row["net"]
    out = pd.DataFrame(list(result.values())).sort_values("date").reset_index(drop=True)
    out["total_net"] = out["foreign_net"] + out["trust_net"] + out["dealer_net"]
    out["date_label"] = out["date"].dt.strftime("%m/%d")
    return out


def get_price(stock_id, start_date):
    df = fetch("TaiwanStockPrice", stock_id, start_date)
    if df.empty:
        return pd.DataFrame()
    df["date_label"] = df["date"].dt.strftime("%m/%d")
    return df


def get_margin(stock_id, start_date):
    df = fetch("TaiwanStockMarginPurchaseShortSale", stock_id, start_date)
    if df.empty:
        return pd.DataFrame()
    df["margin_balance"] = df["MarginPurchaseTodayBalance"].astype(float) / 1000
    df["margin_change"] = (df["MarginPurchaseBuy"].astype(float) - df["MarginPurchaseSell"].astype(float)) / 1000
    df["short_balance"] = df["ShortSaleTodayBalance"].astype(float) / 1000
    df["short_change"] = (df["ShortSaleBuy"].astype(float) - df["ShortSaleSell"].astype(float)) / 1000
    df["date_label"] = df["date"].dt.strftime("%m/%d")
    return df


def get_foreign_holding(stock_id, start_date):
    df = fetch("TaiwanStockShareholding", stock_id, start_date)
    if df.empty:
        return pd.DataFrame()
    df["foreign_ratio"] = (
        df["ForeignInvestmentRemainingShares"].astype(float) /
        df["NumberOfSharesIssued"].astype(float) * 100
    )
    df["date_label"] = df["date"].dt.strftime("%m/%d")
    return df


def get_per(stock_id, start_date):
    df = fetch("TaiwanStockPER", stock_id, start_date)
    if df.empty:
        return pd.DataFrame()
    df["date_label"] = df["date"].dt.strftime("%m/%d")
    return df


def get_news(stock_id, start_date):
    df = fetch("TaiwanStockNews", stock_id, start_date)
    return df


# ── 側邊欄 ────────────────────────────────────────────────

with st.sidebar:
    lang_choice = st.radio("Language / 語言", ["中文", "English"], horizontal=True)
    lang = "zh" if lang_choice == "中文" else "en"
    t = LANG[lang]

    st.header(t["settings"])
    stock_id = st.text_input(t["stock_input"], value="2330",
                             placeholder=t["stock_placeholder"]).strip()
    days = st.slider(t["days_label"], min_value=5, max_value=60, value=7, step=1)
    if st.button(t["reload"], use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption("常用代號：\n2330 台積電\n2317 鴻海\n2454 聯發科\n2882 國泰金\n0050 元大50")

# ── 標題 ──────────────────────────────────────────────────

st.title(t["title"])
st.caption(f"{t['caption']}　｜　股票代號：**{stock_id}**　｜　{datetime.now().strftime('%Y-%m-%d %H:%M')}")

start_date = get_start_date(days)

with st.spinner(t["loading"]):
    inst_df = get_institutional(stock_id, start_date)
    price_df = get_price(stock_id, start_date)
    margin_df = get_margin(stock_id, start_date)
    foreign_df = get_foreign_holding(stock_id, start_date)
    per_df = get_per(stock_id, start_date)
    news_df = get_news(stock_id, start_date)

if inst_df.empty and price_df.empty:
    st.error(t["no_data"])
    st.warning("FinMind API 可能達到請求上限，請點左側「🔄 重新載入資料」或稍後再試。")
    st.stop()

if inst_df.empty:
    st.warning("三大法人資料暫時無法取得，其他資料仍可查看。")
if price_df.empty:
    st.warning("股價資料暫時無法取得，其他資料仍可查看。")

# 截取最近 N 天
def tail_df(df, n):
    return df.tail(n).reset_index(drop=True) if not df.empty else df

inst_df = tail_df(inst_df, days)
price_df = tail_df(price_df, days)
margin_df = tail_df(margin_df, days)
foreign_df = tail_df(foreign_df, days)
per_df = tail_df(per_df, days)

# ── KPI 卡片 ───────────────────────────────────────────────

if not inst_df.empty:
    st.subheader(t["summary"])
    col1, col2, col3, col4 = st.columns(4)
    foreign_sum = inst_df["foreign_net"].sum()
    trust_sum = inst_df["trust_net"].sum()
    dealer_sum = inst_df["dealer_net"].sum()
    total_sum = inst_df["total_net"].sum()

    def kpi_delta(val):
        return f"{val:+,.0f} {t['unit']}"

    col1.metric(t["foreign"], f"{foreign_sum:,.0f} {t['unit']}", kpi_delta(foreign_sum))
    col2.metric(t["trust"], f"{trust_sum:,.0f} {t['unit']}", kpi_delta(trust_sum))
    col3.metric(t["dealer"], f"{dealer_sum:,.0f} {t['unit']}", kpi_delta(dealer_sum))
    col4.metric(t["total"], f"{total_sum:,.0f} {t['unit']}", kpi_delta(total_sum))

    st.divider()

# ── Tabs ──────────────────────────────────────────────────

tabs = st.tabs(t["tabs"])

# ── Tab 1: K 線圖 ──────────────────────────────────────────
with tabs[0]:
    if not price_df.empty:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(
            x=price_df["date_label"],
            open=price_df["open"], high=price_df["max"],
            low=price_df["min"], close=price_df["close"],
            name=t["price"],
            increasing_line_color="#F44336",
            decreasing_line_color="#26A69A",
        ), row=1, col=1)
        vol_colors = ["#F44336" if c >= o else "#26A69A"
                      for c, o in zip(price_df["close"], price_df["open"])]
        fig.add_trace(go.Bar(
            x=price_df["date_label"], y=price_df["Trading_Volume"].astype(float),
            name=t["volume"], marker_color=vol_colors, opacity=0.7
        ), row=2, col=1)
        fig.update_layout(height=500, xaxis_rangeslider_visible=False,
                          legend=dict(orientation="h", y=1.02))
        fig.update_yaxes(title_text=t["price"], row=1, col=1)
        fig.update_yaxes(title_text=t["volume"], row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

        # 最新價格資訊
        latest = price_df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t["open"], f"{float(latest['open']):,.1f}")
        c2.metric(t["high"], f"{float(latest['max']):,.1f}")
        c3.metric(t["low"], f"{float(latest['min']):,.1f}")
        spread = float(latest['spread'])
        c4.metric(t["close"], f"{float(latest['close']):,.1f}",
                  f"{spread:+.1f}")
    else:
        st.info(t["no_data"])

# ── Tab 2: 三大法人 ────────────────────────────────────────
with tabs[1]:
    if not inst_df.empty:
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader(t["chart1_title"])
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(name=t["foreign"], x=inst_df["date_label"],
                                  y=inst_df["foreign_net"], marker_color="#2196F3"))
            fig1.add_trace(go.Bar(name=t["trust"], x=inst_df["date_label"],
                                  y=inst_df["trust_net"], marker_color="#4CAF50"))
            fig1.add_trace(go.Bar(name=t["dealer"], x=inst_df["date_label"],
                                  y=inst_df["dealer_net"], marker_color="#FF9800"))
            fig1.add_hline(y=0, line_dash="dash", line_color="gray")
            fig1.update_layout(barmode="group", yaxis_title=t["unit"], height=380,
                               legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig1, use_container_width=True)

        with col_right:
            st.subheader(t["chart2_title"])
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            bar_colors = ["#F44336" if v >= 0 else "#1E88E5" for v in inst_df["total_net"]]
            fig2.add_trace(go.Bar(name=t["daily"], x=inst_df["date_label"],
                                  y=inst_df["total_net"], marker_color=bar_colors), secondary_y=False)
            fig2.add_trace(go.Scatter(name=t["cumulative"], x=inst_df["date_label"],
                                      y=inst_df["total_net"].cumsum(), mode="lines+markers",
                                      line=dict(color="purple", width=2)), secondary_y=True)
            fig2.add_hline(y=0, line_dash="dash", line_color="gray")
            fig2.update_layout(height=380, legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig2, use_container_width=True)

        with st.expander(t["raw_data"]):
            disp = inst_df[["date_label", "foreign_net", "trust_net", "dealer_net", "total_net"]].copy()
            disp.columns = [t["date"], t["foreign"], t["trust"], t["dealer"], t["total"]]
            st.dataframe(disp, hide_index=True, use_container_width=True)

# ── Tab 3: 融資融券 ────────────────────────────────────────
with tabs[2]:
    if not margin_df.empty:
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        fig3.add_trace(go.Bar(name=t["margin_bal"], x=margin_df["date_label"],
                              y=margin_df["margin_balance"], marker_color="#FF7043",
                              opacity=0.85), secondary_y=False)
        fig3.add_trace(go.Bar(name=t["short_bal"], x=margin_df["date_label"],
                              y=margin_df["short_balance"], marker_color="#26C6DA",
                              opacity=0.85), secondary_y=True)
        fig3.update_yaxes(title_text=t["margin_bal"], secondary_y=False)
        fig3.update_yaxes(title_text=t["short_bal"], secondary_y=True)
        fig3.update_layout(barmode="group", height=380,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig3, use_container_width=True)

        disp = margin_df[["date_label", "margin_balance", "margin_change",
                           "short_balance", "short_change"]].copy()
        disp.columns = [t["date"], t["margin_bal"], t["margin_chg"], t["short_bal"], t["short_chg"]]
        st.dataframe(disp, hide_index=True, use_container_width=True)
    else:
        st.info(t["no_margin"])

# ── Tab 4: 外資持股 ────────────────────────────────────────
with tabs[3]:
    if not foreign_df.empty:
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=foreign_df["date_label"], y=foreign_df["foreign_ratio"],
            mode="lines+markers+text",
            text=[f"{v:.2f}%" for v in foreign_df["foreign_ratio"]],
            textposition="top center",
            line=dict(color="#7B1FA2", width=2),
            fill="tozeroy", fillcolor="rgba(123,31,162,0.08)"
        ))
        fig4.update_layout(yaxis_title=t["ratio_label"], height=380)
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info(t["no_foreign"])

# ── Tab 5: 基本面 ──────────────────────────────────────────
with tabs[4]:
    if not per_df.empty:
        col_left, col_right = st.columns(2)
        with col_left:
            fig5 = go.Figure()
            fig5.add_trace(go.Scatter(x=per_df["date_label"], y=per_df["PER"].astype(float),
                                      mode="lines+markers", name=t["per"],
                                      line=dict(color="#E91E63", width=2)))
            fig5.update_layout(yaxis_title=t["per"], height=350)
            st.plotly_chart(fig5, use_container_width=True)

        with col_right:
            fig6 = go.Figure()
            fig6.add_trace(go.Scatter(x=per_df["date_label"], y=per_df["PBR"].astype(float),
                                      mode="lines+markers", name=t["pbr"],
                                      line=dict(color="#00BCD4", width=2)))
            fig6.update_layout(yaxis_title=t["pbr"], height=350)
            st.plotly_chart(fig6, use_container_width=True)

        latest_per = per_df.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric(t["per"], f"{float(latest_per['PER']):.2f}")
        c2.metric(t["pbr"], f"{float(latest_per['PBR']):.2f}")
        c3.metric(t["yield"], f"{float(latest_per['dividend_yield']):.2f}%")
    else:
        st.info(t["no_per"])

# ── Tab 6: 新聞 ────────────────────────────────────────────
with tabs[5]:
    st.subheader(t["news_title"])
    if not news_df.empty:
        news_show = news_df.sort_values("date", ascending=False).head(20)
        for _, row in news_show.iterrows():
            with st.container():
                st.markdown(f"**[{row['title']}]({row['link']})**")
                col_a, col_b = st.columns([3, 1])
                col_a.caption(row.get("description", "")[:100] + "...")
                col_b.caption(f"{row['date'].strftime('%Y-%m-%d')}　{row.get('source', '')}")
            st.divider()
    else:
        st.info(t["no_news"])
