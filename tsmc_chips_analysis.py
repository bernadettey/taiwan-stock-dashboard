"""
TSMC (2330) 籌碼分析 - 過去一週
分析三大法人買賣超、融資融券、外資持股比例
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang TC', 'Heiti TC']
plt.rcParams['axes.unicode_minus'] = False

STOCK_ID = "2330"


def get_institutional_investors(date_str):
    """取得三大法人買賣超"""
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
    except Exception as e:
        print(f"  [{date_str}] 三大法人資料錯誤: {e}")
        return None


def get_margin_trading(date_str):
    """取得融資融券餘額"""
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("stat") != "OK":
            return None
        # 融資在 data，融券在 data2
        margin_bal, short_bal, margin_chg, short_chg = None, None, None, None
        for table_key, fields_key in [("data", "fields"), ("data2", "fields2")]:
            if table_key not in data:
                continue
            cols = data.get(fields_key, [])
            df = pd.DataFrame(data[table_key], columns=cols)
            col_name = "股票代號" if "股票代號" in df.columns else (cols[0] if cols else None)
            if col_name is None:
                continue
            df = df[df[col_name] == STOCK_ID]
            if df.empty:
                continue
            row = df.iloc[0]
            vals = [v.replace(",", "") for v in row.values]
            if table_key == "data":
                # 融資：餘額(張) index 4, 增減(張) index 3
                margin_bal = int(vals[4])
                margin_chg = int(vals[3])
            else:
                # 融券：餘額(張) index 4, 增減(張) index 3
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
    except Exception as e:
        print(f"  [{date_str}] 融資融券資料錯誤: {e}")
        return None


def get_foreign_holding(date_str):
    """取得外資持股比例"""
    url = f"https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("stat") != "OK":
            return None
        df = pd.DataFrame(data["data"], columns=data["fields"])
        # 欄位名稱可能含空格
        code_col = [c for c in df.columns if "代號" in c or "代碼" in c]
        if not code_col:
            return None
        df = df[df[code_col[0]].str.strip() == STOCK_ID]
        if df.empty:
            return None
        row = df.iloc[0]
        # 找持股比例欄位
        ratio_col = [c for c in df.columns if "%" in c or "比率" in c or "比例" in c]
        if not ratio_col:
            return None
        ratio = float(row[ratio_col[0]].replace(",", "").replace("%", ""))
        return {"date": date_str, "foreign_ratio": ratio}
    except Exception as e:
        print(f"  [{date_str}] 外資持股資料錯誤: {e}")
        return None


def get_trading_dates(days=7):
    """取得過去 N 個交易日（跳過週末）"""
    dates = []
    d = datetime.today()
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return dates[::-1]


def print_table(title, df, col_map):
    print(f"\n【{title}】")
    print("-" * 65)
    display = df[list(col_map.keys())].copy()
    display.columns = list(col_map.values())
    if "日期" in display.columns:
        display["日期"] = pd.to_datetime(display["日期"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    print(display.to_string(index=False))


def main():
    print("=" * 55)
    print(f"  TSMC ({STOCK_ID}) 籌碼分析 - 過去一週")
    print("=" * 55)

    trading_dates = get_trading_dates(7)
    print(f"\n查詢日期: {trading_dates[0]} ~ {trading_dates[-1]}\n")

    inst_list, margin_list, foreign_list = [], [], []

    for date in trading_dates:
        print(f"取得 {date} 資料...")
        r = get_institutional_investors(date)
        if r:
            inst_list.append(r)
        r = get_margin_trading(date)
        if r:
            margin_list.append(r)
        r = get_foreign_holding(date)
        if r:
            foreign_list.append(r)

    if not inst_list:
        print("\n無法取得資料（可能為假日或資料尚未更新）")
        return

    inst_df = pd.DataFrame(inst_list)
    inst_df["date_dt"] = pd.to_datetime(inst_df["date"], format="%Y%m%d")

    # --- 文字輸出 ---
    print_table("三大法人買賣超（張）", inst_df, {
        "date": "日期", "foreign_net": "外資", "trust_net": "投信",
        "dealer_net": "自營商", "total_net": "合計"
    })
    print(f"\n  一週外資淨買: {inst_df['foreign_net'].sum():,.0f} 張")
    print(f"  一週投信淨買: {inst_df['trust_net'].sum():,.0f} 張")
    print(f"  一週自營商淨買: {inst_df['dealer_net'].sum():,.0f} 張")
    print(f"  一週三大法人合計: {inst_df['total_net'].sum():,.0f} 張")

    if margin_list:
        margin_df = pd.DataFrame(margin_list)
        margin_df["date_dt"] = pd.to_datetime(margin_df["date"], format="%Y%m%d")
        print_table("融資融券餘額（張）", margin_df, {
            "date": "日期",
            "margin_balance": "融資餘額", "margin_change": "融資增減",
            "short_balance": "融券餘額", "short_change": "融券增減",
        })

    if foreign_list:
        foreign_df = pd.DataFrame(foreign_list)
        foreign_df["date_dt"] = pd.to_datetime(foreign_df["date"], format="%Y%m%d")
        print_table("外資持股比例（%）", foreign_df, {
            "date": "日期", "foreign_ratio": "持股比例(%)"
        })

    # --- 繪圖 (2x2) ---
    has_margin = len(margin_list) > 0
    has_foreign = len(foreign_list) > 0
    nrows = 2 if (has_margin or has_foreign) else 1
    fig, axes = plt.subplots(nrows, 2, figsize=(14, 5 * nrows))
    fig.suptitle(f"TSMC ({STOCK_ID}) 籌碼分析 - 過去一週", fontsize=14, fontweight='bold')

    if nrows == 1:
        axes = [axes]

    x = list(range(len(inst_df)))
    xlabels = inst_df["date_dt"].dt.strftime("%m/%d").tolist()

    # 圖1: 三大法人每日買賣超
    ax1 = axes[0][0]
    w = 0.25
    ax1.bar([i - w for i in x], inst_df["foreign_net"], width=w, label="外資", color="#2196F3")
    ax1.bar(x, inst_df["trust_net"], width=w, label="投信", color="#4CAF50")
    ax1.bar([i + w for i in x], inst_df["dealer_net"], width=w, label="自營商", color="#FF9800")
    ax1.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax1.set_xticks(x); ax1.set_xticklabels(xlabels)
    ax1.set_title("三大法人每日買賣超"); ax1.set_ylabel("張")
    ax1.legend(); ax1.grid(axis="y", alpha=0.3)

    # 圖2: 三大法人合計 & 累積
    ax2 = axes[0][1]
    cumsum = inst_df["total_net"].cumsum()
    bar_colors = ["#F44336" if v >= 0 else "#2196F3" for v in inst_df["total_net"]]
    ax2.bar(x, inst_df["total_net"], color=bar_colors, label="每日合計")
    ax2.plot(x, cumsum.values, color="purple", marker="o", linewidth=2, label="累積")
    ax2.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax2.set_xticks(x); ax2.set_xticklabels(xlabels)
    ax2.set_title("三大法人合計 & 累積買賣超"); ax2.set_ylabel("張")
    ax2.legend(); ax2.grid(axis="y", alpha=0.3)

    if nrows == 2:
        # 圖3: 融資融券餘額
        ax3 = axes[1][0]
        if has_margin:
            mx = list(range(len(margin_df)))
            mxlabels = margin_df["date_dt"].dt.strftime("%m/%d").tolist()
            ax3_twin = ax3.twinx()
            ax3.bar([i - 0.2 for i in mx], margin_df["margin_balance"], width=0.35,
                    label="融資餘額", color="#FF7043", alpha=0.8)
            ax3_twin.bar([i + 0.2 for i in mx], margin_df["short_balance"], width=0.35,
                         label="融券餘額", color="#26C6DA", alpha=0.8)
            ax3.set_xticks(mx); ax3.set_xticklabels(mxlabels)
            ax3.set_title("融資融券餘額")
            ax3.set_ylabel("融資餘額（張）", color="#FF7043")
            ax3_twin.set_ylabel("融券餘額（張）", color="#26C6DA")
            lines1, labels1 = ax3.get_legend_handles_labels()
            lines2, labels2 = ax3_twin.get_legend_handles_labels()
            ax3.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
            ax3.grid(axis="y", alpha=0.3)
        else:
            ax3.set_visible(False)

        # 圖4: 外資持股比例
        ax4 = axes[1][1]
        if has_foreign:
            fx = list(range(len(foreign_df)))
            fxlabels = foreign_df["date_dt"].dt.strftime("%m/%d").tolist()
            ax4.plot(fx, foreign_df["foreign_ratio"], color="#7B1FA2", marker="o",
                     linewidth=2, markersize=6)
            ax4.fill_between(fx, foreign_df["foreign_ratio"],
                             min(foreign_df["foreign_ratio"]) - 0.1,
                             alpha=0.15, color="#7B1FA2")
            ax4.set_xticks(fx); ax4.set_xticklabels(fxlabels)
            ax4.set_title("外資持股比例")
            ax4.set_ylabel("持股比例（%）")
            ax4.grid(alpha=0.3)
            # 標記最新值
            ax4.annotate(f"{foreign_df['foreign_ratio'].iloc[-1]:.2f}%",
                         xy=(fx[-1], foreign_df["foreign_ratio"].iloc[-1]),
                         xytext=(5, 5), textcoords="offset points", fontsize=10,
                         color="#7B1FA2", fontweight="bold")
        else:
            ax4.set_visible(False)

    plt.tight_layout()
    output_path = "/Users/bernadette/Desktop/LLMtest/tsmc_chips_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\n圖表已儲存: {output_path}")
    plt.show()


if __name__ == "__main__":
    main()
