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
warnings.filterwarnings('ignore')

STOCK_ID = "2330"

st.set_page_config(
    page_title="TSMC 籌碼分析",
    page_icon="📊",
    layout="wide"
)

# ── 資料抓取函數 ──────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_institutional_investors(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("stat") != "OK":
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
    except:
        return None


@st.cache_data(ttl=3600)
def get_margin_trading(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
    try:
        res = requests.get(url, timeout=10)
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
        res = requests.get(url, timeout=10)
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
    # 若今天是週末，從上週五開始往回數
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return dates[::-1]


# ── UI ────────────────────────────────────────────────────

st.title("📊 TSMC (2330) 籌碼分析儀表板")
st.caption(f"資料來源：台灣證券交易所 (TWSE)　｜　更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 側邊欄設定
with st.sidebar:
    st.header("⚙️ 設定")
    days = st.slider("查詢天數（交易日）", min_value=5, max_value=20, value=7, step=1)
    if st.button("🔄 重新載入資料", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 載入資料
trading_dates = get_trading_dates(days)

with st.spinner("載入資料中..."):
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
    st.error("無法取得資料，TWSE 資料尚未更新，請明天再試。")
    st.stop()

inst_df = pd.DataFrame(inst_list)
inst_df["date_dt"] = pd.to_datetime(inst_df["date"], format="%Y%m%d")
inst_df["date_label"] = inst_df["date_dt"].dt.strftime("%m/%d")

# ── KPI 卡片 ───────────────────────────────────────────────
st.subheader("一週籌碼摘要")
col1, col2, col3, col4 = st.columns(4)

foreign_sum = inst_df["foreign_net"].sum()
trust_sum = inst_df["trust_net"].sum()
dealer_sum = inst_df["dealer_net"].sum()
total_sum = inst_df["total_net"].sum()

def kpi_delta(val):
    return f"{val:+,.0f} 張"

col1.metric("外資合計", f"{foreign_sum:,.0f} 張", kpi_delta(foreign_sum))
col2.metric("投信合計", f"{trust_sum:,.0f} 張", kpi_delta(trust_sum))
col3.metric("自營商合計", f"{dealer_sum:,.0f} 張", kpi_delta(dealer_sum))
col4.metric("三大法人合計", f"{total_sum:,.0f} 張", kpi_delta(total_sum))

st.divider()

# ── 圖1 + 圖2 ─────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("三大法人每日買賣超")
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name="外資", x=inst_df["date_label"], y=inst_df["foreign_net"], marker_color="#2196F3"))
    fig1.add_trace(go.Bar(name="投信", x=inst_df["date_label"], y=inst_df["trust_net"], marker_color="#4CAF50"))
    fig1.add_trace(go.Bar(name="自營商", x=inst_df["date_label"], y=inst_df["dealer_net"], marker_color="#FF9800"))
    fig1.add_hline(y=0, line_dash="dash", line_color="gray")
    fig1.update_layout(barmode="group", yaxis_title="張", height=380,
                       legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig1, use_container_width=True)

with col_right:
    st.subheader("三大法人合計 & 累積買賣超")
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    bar_colors = ["#F44336" if v >= 0 else "#1E88E5" for v in inst_df["total_net"]]
    fig2.add_trace(go.Bar(name="每日合計", x=inst_df["date_label"], y=inst_df["total_net"],
                          marker_color=bar_colors), secondary_y=False)
    fig2.add_trace(go.Scatter(name="累積買賣超", x=inst_df["date_label"],
                              y=inst_df["total_net"].cumsum(), mode="lines+markers",
                              line=dict(color="purple", width=2)), secondary_y=True)
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    fig2.update_yaxes(title_text="每日（張）", secondary_y=False)
    fig2.update_yaxes(title_text="累積（張）", secondary_y=True)
    fig2.update_layout(height=380, legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig2, use_container_width=True)

# ── 圖3 + 圖4 ─────────────────────────────────────────────
has_margin = len(margin_list) > 0
has_foreign = len(foreign_list) > 0

if has_margin or has_foreign:
    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.subheader("融資融券餘額")
        if has_margin:
            margin_df = pd.DataFrame(margin_list)
            margin_df["date_dt"] = pd.to_datetime(margin_df["date"], format="%Y%m%d")
            margin_df["date_label"] = margin_df["date_dt"].dt.strftime("%m/%d")

            fig3 = make_subplots(specs=[[{"secondary_y": True}]])
            fig3.add_trace(go.Bar(name="融資餘額", x=margin_df["date_label"],
                                  y=margin_df["margin_balance"], marker_color="#FF7043",
                                  opacity=0.85), secondary_y=False)
            fig3.add_trace(go.Bar(name="融券餘額", x=margin_df["date_label"],
                                  y=margin_df["short_balance"], marker_color="#26C6DA",
                                  opacity=0.85), secondary_y=True)
            fig3.update_yaxes(title_text="融資（張）", secondary_y=False)
            fig3.update_yaxes(title_text="融券（張）", secondary_y=True)
            fig3.update_layout(barmode="group", height=380,
                               legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig3, use_container_width=True)

            # 融資融券增減表
            disp = margin_df[["date_label", "margin_balance", "margin_change",
                               "short_balance", "short_change"]].copy()
            disp.columns = ["日期", "融資餘額", "融資增減", "融券餘額", "融券增減"]
            st.dataframe(disp, hide_index=True, use_container_width=True)
        else:
            st.info("融資融券資料無法取得")

    with col_right2:
        st.subheader("外資持股比例")
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
            fig4.update_layout(yaxis_title="持股比例（%）", height=380)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("外資持股比例資料無法取得")

# ── 原始資料表 ─────────────────────────────────────────────
with st.expander("📋 查看三大法人原始資料"):
    disp = inst_df[["date_label", "foreign_net", "trust_net", "dealer_net", "total_net"]].copy()
    disp.columns = ["日期", "外資（張）", "投信（張）", "自營商（張）", "合計（張）"]
    st.dataframe(disp, hide_index=True, use_container_width=True)
