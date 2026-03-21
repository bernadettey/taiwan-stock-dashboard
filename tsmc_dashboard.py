"""
TSMC (2330) 籌碼分析 Streamlit Dashboard
"""

import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta
import warnings
import urllib3
warnings.filterwarnings('ignore')
# TWSE 憑證缺少 Subject Key Identifier，為已知政府網站憑證問題
# 資料為公開市場資料，僅針對 TWSE domain 停用 SSL 驗證
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STOCK_ID = "2330"

st.set_page_config(
    page_title="TSMC Chip Analysis",
    page_icon="📊",
    layout="wide"
)

# ── 語言設定 ──────────────────────────────────────────────

LANG = {
    "zh": {
        "title": "📊 TSMC (2330) 籌碼分析儀表板",
        "caption": "資料來源：台灣證券交易所 (TWSE)",
        "settings": "⚙️ 設定",
        "language": "語言",
        "days_label": "查詢天數（交易日）",
        "reload": "🔄 重新載入資料",
        "loading": "載入資料中...",
        "no_data": "無法取得資料，TWSE 資料尚未更新，請明天再試。",
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
        "caption": "Data source: Taiwan Stock Exchange (TWSE)",
        "settings": "⚙️ Settings",
        "language": "Language",
        "days_label": "Trading Days",
        "reload": "🔄 Reload Data",
        "loading": "Loading data...",
        "no_data": "No data available. TWSE may not have published data yet. Please try again tomorrow.",
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

# ── 資料抓取函數 ──────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_institutional_investors(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        res = requests.get(url, timeout=10, verify=False)
        data = res.json()
        if data.get("stat") != "OK":
            print(f"[{date_str}] stat={data.get('stat')}, msg={data.get('msg','')}")
            return None
        df = pd.DataFrame(data["data"], columns=data["fields"])
        df = df[df["證券代號"] == STOCK_ID]
        if df.empty:
            return None
        row = df.iloc[0]
        return {
            "date": date_str,
            "foreign_net": int(row["外陸資買賣超股數(不含外資自營商)"].replace(",", "")) / 1000,
            "trust_net": int(row["投信買賣超股數"].replace(",", "")) / 1000,
            "dealer_net": int(row["自營商買賣超股數"].replace(",", "")) / 1000,
            "total_net": int(row["三大法人買賣超股數"].replace(",", "")) / 1000,
        }
    except Exception as e:
        print(f"[{date_str}] 三大法人錯誤: {e}")
        return None


@st.cache_data(ttl=3600)
def get_margin_trading(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
    try:
        res = requests.get(url, timeout=10, verify=False)
        data = res.json()
        if data.get("stat") != "OK":
            return None
        margin_bal, short_bal, margin_chg, short_chg = None, None, None, None
        for table_key, fields_key in [("data", "fields"), ("data2", "fields2")]:
            if table_key not in data:
                continue
            cols = data.get(fields_key, [])
            df = pd.DataFrame(data[table_key], columns=cols)
            col_name = [c for c in df.columns if "代號" in c or "代碼" in c]
            if not col_name:
                continue
            df = df[df[col_name[0]].str.strip() == STOCK_ID]
            if df.empty:
                continue
            row = df.iloc[0]
            vals = [str(v).replace(",", "") for v in row.values]
            if table_key == "data":
                margin_bal = int(vals[4])
                margin_chg = int(vals[3])
            else:
                short_bal = int(vals[4])
                short_chg = int(vals[3])
        if margin_bal is None and short_bal is None:
            return None
        return {
            "date": date_str,
            "margin_balance": margin_bal or 0,
            "margin_change": margin_chg or 0,
            "short_balance": short_bal or 0,
            "short_change": short_chg or 0,
        }
    except:
        return None


@st.cache_data(ttl=3600)
def get_foreign_holding(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        res = requests.get(url, timeout=10, verify=False)
        data = res.json()
        if data.get("stat") != "OK":
            return None
        df = pd.DataFrame(data["data"], columns=data["fields"])
        code_col = [c for c in df.columns if "代號" in c or "代碼" in c]
        if not code_col:
            return None
        df = df[df[code_col[0]].str.strip() == STOCK_ID]
        if df.empty:
            return None
        row = df.iloc[0]
        ratio_col = [c for c in df.columns if "%" in c or "比率" in c or "比例" in c]
        if not ratio_col:
            return None
        ratio = float(str(row[ratio_col[0]]).replace(",", "").replace("%", ""))
        return {"date": date_str, "foreign_ratio": ratio}
    except:
        return None


def get_trading_dates(days):
    dates = []
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return dates[::-1]


# ── UI ────────────────────────────────────────────────────

# 側邊欄
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

# 載入資料
trading_dates = get_trading_dates(days)

with st.spinner(t["loading"]):
    inst_list, margin_list, foreign_list = [], [], []
    progress = st.progress(0)
    for i, date in enumerate(trading_dates):
        r = get_institutional_investors(date)
        if r:
            inst_list.append(r)
        r = get_margin_trading(date)
        if r:
            margin_list.append(r)
        r = get_foreign_holding(date)
        if r:
            foreign_list.append(r)
        progress.progress((i + 1) / len(trading_dates))
    progress.empty()

if not inst_list:
    # 診斷模式：直接顯示 API 回應
    import traceback
    try:
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={trading_dates[-1]}&selectType=ALLBUT0999&response=json"
        res = requests.get(url, timeout=10, verify=False)
        st.error(f"HTTP {res.status_code} | 回應內容: {res.text[:300]}")
    except Exception as e:
        st.error(f"連線失敗: {e}")
    st.stop()

inst_df = pd.DataFrame(inst_list)
inst_df["date_dt"] = pd.to_datetime(inst_df["date"], format="%Y%m%d")
inst_df["date_label"] = inst_df["date_dt"].dt.strftime("%m/%d")

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
has_margin = len(margin_list) > 0
has_foreign = len(foreign_list) > 0

if has_margin or has_foreign:
    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.subheader(t["chart3_title"])
        if has_margin:
            margin_df = pd.DataFrame(margin_list)
            margin_df["date_dt"] = pd.to_datetime(margin_df["date"], format="%Y%m%d")
            margin_df["date_label"] = margin_df["date_dt"].dt.strftime("%m/%d")

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
            foreign_df = pd.DataFrame(foreign_list)
            foreign_df["date_dt"] = pd.to_datetime(foreign_df["date"], format="%Y%m%d")
            foreign_df["date_label"] = foreign_df["date_dt"].dt.strftime("%m/%d")

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
