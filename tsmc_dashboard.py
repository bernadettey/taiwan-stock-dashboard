"""
TSMC (2330) 籌碼分析 Streamlit Dashboard
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

STOCK_ID = "2330"
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

st.set_page_config(
    page_title="TSMC Chip Analysis",
    page_icon="📊",
    layout="wide"
)

# ── 語言設定 ──────────────────────────────────────────────

LANG = {
    "zh": {
        "title": "📊 TSMC (2330) 籌碼分析儀表板",
        "caption": "資料來源：FinMind API",
        "settings": "⚙️ 設定",
        "days_label": "查詢天數（交易日）",
        "reload": "🔄 重新載入資料",
        "loading": "載入資料中...",
        "no_data": "無法取得資料，請稍後再試。",
        "summary": "籌碼摘要",
        "foreign": "外資",
        "trust": "投信",
        "dealer": "自營商",
        "total": "三大法人合計",
        "unit": "張",
        "chart1_title": "三大法人每日買賣超",
        "chart2_title": "三大法人合計 & 累積買賣超",
        "daily": "每日合計",
        "cumulative": "累積買賣超",
        "chart3_title": "融資融券餘額",
        "margin_bal": "融資餘額",
        "short_bal": "融券餘額",
        "margin_chg": "融資增減",
        "short_chg": "融券增減",
        "margin_unit": "融資（張）",
        "short_unit": "融券（張）",
        "chart4_title": "外資持股比例",
        "ratio_label": "持股比例（%）",
        "raw_data": "📋 查看三大法人原始資料",
        "date": "日期",
        "no_margin": "融資融券資料無法取得",
        "no_foreign": "外資持股比例資料無法取得",
    },
    "en": {
        "title": "📊 TSMC (2330) Chip Flow Dashboard",
        "caption": "Data source: FinMind API",
        "settings": "⚙️ Settings",
        "days_label": "Trading Days",
        "reload": "🔄 Reload Data",
        "loading": "Loading data...",
        "no_data": "Unable to fetch data. Please try again later.",
        "summary": "Weekly Summary",
        "foreign": "Foreign",
        "trust": "Investment Trust",
        "dealer": "Dealer",
        "total": "3 Institutions Total",
        "unit": "lots",
        "chart1_title": "Daily Net Buy/Sell by Institution",
        "chart2_title": "Total & Cumulative Net Buy/Sell",
        "daily": "Daily Total",
        "cumulative": "Cumulative",
        "chart3_title": "Margin Trading Balance",
        "margin_bal": "Margin Balance",
        "short_bal": "Short Balance",
        "margin_chg": "Margin Change",
        "short_chg": "Short Change",
        "margin_unit": "Margin (lots)",
        "short_unit": "Short (lots)",
        "chart4_title": "Foreign Ownership Ratio",
        "ratio_label": "Ownership (%)",
        "raw_data": "📋 View Raw Institutional Data",
        "date": "Date",
        "no_margin": "Margin trading data unavailable",
        "no_foreign": "Foreign ownership data unavailable",
    }
}

# ── 資料抓取函數（每種只打 1 次 API）────────────────────────

def get_start_date(days):
    d = datetime.today() - timedelta(days=days + 14)
    return d.strftime("%Y-%m-%d")


@st.cache_data(ttl=3600)
def get_institutional_investors(start_date):
    try:
        res = requests.get(FINMIND_URL, params={
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": STOCK_ID,
            "start_date": start_date,
        }, timeout=15)
        data = res.json()
        if data.get("status") != 200 or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
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
    except Exception as e:
        print(f"三大法人錯誤: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_margin_trading(start_date):
    try:
        res = requests.get(FINMIND_URL, params={
            "dataset": "TaiwanStockMarginPurchaseShortSale",
            "data_id": STOCK_ID,
            "start_date": start_date,
        }, timeout=15)
        data = res.json()
        if data.get("status") != 200 or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df["margin_balance"] = df["MarginPurchaseTodayBalance"].astype(float) / 1000
        df["margin_change"] = (df["MarginPurchaseBuy"].astype(float) - df["MarginPurchaseSell"].astype(float)) / 1000
        df["short_balance"] = df["ShortSaleTodayBalance"].astype(float) / 1000
        df["short_change"] = (df["ShortSaleBuy"].astype(float) - df["ShortSaleSell"].astype(float)) / 1000
        df["date_label"] = df["date"].dt.strftime("%m/%d")
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"融資融券錯誤: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_foreign_holding(start_date):
    try:
        res = requests.get(FINMIND_URL, params={
            "dataset": "TaiwanStockShareholding",
            "data_id": STOCK_ID,
            "start_date": start_date,
        }, timeout=15)
        data = res.json()
        if data.get("status") != 200 or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df["foreign_ratio"] = (
            df["ForeignInvestmentRemainingShares"].astype(float) /
            df["NumberOfSharesIssued"].astype(float) * 100
        )
        df["date_label"] = df["date"].dt.strftime("%m/%d")
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"外資持股錯誤: {e}")
        return pd.DataFrame()


# ── UI ────────────────────────────────────────────────────

with st.sidebar:
    lang_choice = st.radio("Language / 語言", ["中文", "English"], horizontal=True)
    lang = "zh" if lang_choice == "中文" else "en"
    t = LANG[lang]

    st.header(t["settings"])
    days = st.slider(t["days_label"], min_value=5, max_value=20, value=7, step=1)
    if st.button(t["reload"], use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.title(t["title"])
st.caption(f"{t['caption']}　｜　{datetime.now().strftime('%Y-%m-%d %H:%M')}")

start_date = get_start_date(days)

with st.spinner(t["loading"]):
    inst_df = get_institutional_investors(start_date)
    margin_df = get_margin_trading(start_date)
    foreign_df = get_foreign_holding(start_date)

if inst_df.empty:
    st.error(t["no_data"])
    st.stop()

inst_df = inst_df.tail(days).reset_index(drop=True)
if not margin_df.empty:
    margin_df = margin_df.tail(days).reset_index(drop=True)
if not foreign_df.empty:
    foreign_df = foreign_df.tail(days).reset_index(drop=True)

# ── KPI 卡片 ───────────────────────────────────────────────
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

# ── 圖1 + 圖2 ─────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader(t["chart1_title"])
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name=t["foreign"], x=inst_df["date_label"], y=inst_df["foreign_net"], marker_color="#2196F3"))
    fig1.add_trace(go.Bar(name=t["trust"], x=inst_df["date_label"], y=inst_df["trust_net"], marker_color="#4CAF50"))
    fig1.add_trace(go.Bar(name=t["dealer"], x=inst_df["date_label"], y=inst_df["dealer_net"], marker_color="#FF9800"))
    fig1.add_hline(y=0, line_dash="dash", line_color="gray")
    fig1.update_layout(barmode="group", yaxis_title=t["unit"], height=380,
                       legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig1, use_container_width=True)

with col_right:
    st.subheader(t["chart2_title"])
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    bar_colors = ["#F44336" if v >= 0 else "#1E88E5" for v in inst_df["total_net"]]
    fig2.add_trace(go.Bar(name=t["daily"], x=inst_df["date_label"], y=inst_df["total_net"],
                          marker_color=bar_colors), secondary_y=False)
    fig2.add_trace(go.Scatter(name=t["cumulative"], x=inst_df["date_label"],
                              y=inst_df["total_net"].cumsum(), mode="lines+markers",
                              line=dict(color="purple", width=2)), secondary_y=True)
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    fig2.update_yaxes(title_text=t["unit"], secondary_y=False)
    fig2.update_yaxes(title_text=t["unit"], secondary_y=True)
    fig2.update_layout(height=380, legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig2, use_container_width=True)

# ── 圖3 + 圖4 ─────────────────────────────────────────────
has_margin = not margin_df.empty
has_foreign = not foreign_df.empty

if has_margin or has_foreign:
    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.subheader(t["chart3_title"])
        if has_margin:
            fig3 = make_subplots(specs=[[{"secondary_y": True}]])
            fig3.add_trace(go.Bar(name=t["margin_bal"], x=margin_df["date_label"],
                                  y=margin_df["margin_balance"], marker_color="#FF7043",
                                  opacity=0.85), secondary_y=False)
            fig3.add_trace(go.Bar(name=t["short_bal"], x=margin_df["date_label"],
                                  y=margin_df["short_balance"], marker_color="#26C6DA",
                                  opacity=0.85), secondary_y=True)
            fig3.update_yaxes(title_text=t["margin_unit"], secondary_y=False)
            fig3.update_yaxes(title_text=t["short_unit"], secondary_y=True)
            fig3.update_layout(barmode="group", height=380,
                               legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig3, use_container_width=True)

            disp = margin_df[["date_label", "margin_balance", "margin_change",
                               "short_balance", "short_change"]].copy()
            disp.columns = [t["date"], t["margin_bal"], t["margin_chg"], t["short_bal"], t["short_chg"]]
            st.dataframe(disp, hide_index=True, use_container_width=True)
        else:
            st.info(t["no_margin"])

    with col_right2:
        st.subheader(t["chart4_title"])
        if has_foreign:
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

# ── 原始資料表 ─────────────────────────────────────────────
with st.expander(t["raw_data"]):
    disp = inst_df[["date_label", "foreign_net", "trust_net", "dealer_net", "total_net"]].copy()
    disp.columns = [t["date"], f"{t['foreign']} ({t['unit']})", f"{t['trust']} ({t['unit']})",
                    f"{t['dealer']} ({t['unit']})", f"{t['total']} ({t['unit']})"]
    st.dataframe(disp, hide_index=True, use_container_width=True)
