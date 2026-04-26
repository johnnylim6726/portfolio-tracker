#!/usr/bin/env python3
"""
Portfolio Tracker — Streamlit Web App
Password-protected dashboard. Moomoo + Standard Chartered Bank.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be the very first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD GATE
# ─────────────────────────────────────────────────────────────────────────────
def check_password():
    if st.session_state.get("authenticated"):
        return True
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("## 🔒 Portfolio Tracker")
        st.write("Enter your password to continue.")
        pwd = st.text_input("Password", type="password", placeholder="Password",
                            label_visibility="collapsed")
        if st.button("Login", use_container_width=True, type="primary"):
            if pwd == st.secrets.get("password", ""):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password. Try again.")
    return False

if not check_password():
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO DATA
# ─────────────────────────────────────────────────────────────────────────────
MOOMOO_STOCKS = [
    ("MSFT",  45,       377.73),
    ("QQQ",   19,       584.11),
    ("IBIT",  215,       41.74),
    ("MA",    20,       501.58),
    ("MU",    19,       361.82),
    ("VOO",   14,       601.14),
    ("META",  13,       600.98),
    ("IAUM",  172,       46.25),
    ("NVDA",  2.1254,   208.27),
    ("ISRG",  8,        458.12),
    ("GOOG",  11,       290.27),
    ("AMZN",  10,       262.41),
    ("BRK-B", 3,        478.56),
]

# Each contract = 100-share multiplier
MOOMOO_OPTIONS = [
    ("MSFT Call Jun 2027 $340", 1,  75.00, 116.13),
    ("MSFT Call Dec 2026 $375", 1,  46.34,  76.64),
    ("MSFT Call Jun 2028 $450", 1,  71.15,  81.33),
    ("QQQ  Call Dec 2026 $670", 1,  43.87,  54.82),
    ("IBIT Call Dec 2027 $38",  2,  13.60,  15.84),
    ("NVDA Call Jan 2028 $215", 1,  53.80,  51.25),
]

SCB_STOCKS = [
    ("MSFT", 40,  431.40),
    ("META", 15,  676.87),
    ("MU",   20,  475.49),
    ("TSM",  25,  381.75),
    ("NVDA", 25,  202.64),
    ("AMZN", 15,  255.66),
    ("GOOG",  5,  339.75),
    ("AVGO",  5,  428.06),
    ("MA",    3,  523.95),
    ("NOW",  10,  100.73),
]

CATEGORIES = {
    "Tech":           {"MSFT", "META", "NVDA", "MU", "GOOG", "AVGO", "NOW", "TSM", "ISRG"},
    "Broad Mkt ETFs": {"QQQ", "VOO"},
    "Financials":     {"MA", "BRK-B", "AMZN"},
    "Crypto ETF":     {"IBIT"},
    "Gold ETF":       {"IAUM"},
}

COMBINED_EXPOSURES = [
    ("NVDA", [(2.1254, "Moomoo (fractional)"), (25.0,  "SCB")]),
    ("MSFT", [(45.0,   "Moomoo"),              (40.0,  "SCB")]),
    ("META", [(13.0,   "Moomoo"),              (15.0,  "SCB")]),
    ("MA",   [(20.0,   "Moomoo"),              (3.0,   "SCB")]),
    ("AMZN", [(10.0,   "Moomoo"),              (15.0,  "SCB")]),
]

# ─────────────────────────────────────────────────────────────────────────────
# PRICE FETCH  (cached 5 minutes)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(tickers: tuple) -> dict:
    data = yf.download(list(tickers), period="2d", progress=False, auto_adjust=True)
    if data.empty:
        return {t: None for t in tickers}
    close = data["Close"]
    prices = {}
    for t in tickers:
        try:
            col = (close if len(tickers) == 1 else close[t]).dropna()
            prices[t] = float(col.iloc[-1]) if len(col) else None
        except Exception:
            prices[t] = None
    return prices

# ─────────────────────────────────────────────────────────────────────────────
# DATA BUILDERS
# ─────────────────────────────────────────────────────────────────────────────
def build_stock_df(positions, prices):
    rows = []
    for ticker, shares, avg_cost in positions:
        price = prices.get(ticker)
        cost  = shares * avg_cost
        if price is None:
            rows.append(dict(Ticker=ticker, Shares=shares, AvgCost=avg_cost,
                             LivePrice=None, MarketValue=None, CostBasis=cost,
                             PnL=None, PnLPct=None))
            continue
        mv  = shares * price
        pnl = mv - cost
        pct = pnl / cost * 100 if cost else 0.0
        rows.append(dict(Ticker=ticker, Shares=shares, AvgCost=avg_cost,
                         LivePrice=price, MarketValue=mv, CostBasis=cost,
                         PnL=pnl, PnLPct=pct))
    return pd.DataFrame(rows)

def build_options_df():
    rows = []
    for desc, contracts, cost_sh, val_sh in MOOMOO_OPTIONS:
        mult = contracts * 100
        cost = mult * cost_sh
        mv   = mult * val_sh
        pnl  = mv - cost
        pct  = pnl / cost * 100 if cost else 0.0
        rows.append(dict(Description=desc, Contracts=contracts,
                         CostPerSh=cost_sh, ValPerSh=val_sh,
                         TotalCost=cost, TotalMV=mv, PnL=pnl, PnLPct=pct))
    return pd.DataFrame(rows)

def stock_totals(df):
    valid = df.dropna(subset=["MarketValue"])
    cost  = valid["CostBasis"].sum()
    mv    = valid["MarketValue"].sum()
    pnl   = valid["PnL"].sum()
    pct   = pnl / cost * 100 if cost else 0.0
    return cost, mv, pnl, pct

def option_totals(df):
    cost = df["TotalCost"].sum()
    mv   = df["TotalMV"].sum()
    pnl  = df["PnL"].sum()
    pct  = pnl / cost * 100 if cost else 0.0
    return cost, mv, pnl, pct

# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────
GREEN = "#2ecc71"
RED   = "#e74c3c"

def _color_signed(col):
    return [f"color: {GREEN}" if v > 0 else f"color: {RED}" if v < 0 else ""
            for v in col]

def show_stock_table(df):
    display = df[["Ticker","Shares","AvgCost","LivePrice","MarketValue","PnL","PnLPct"]].copy()
    display.columns = ["Ticker", "Shares", "Avg Cost", "Live Price",
                       "Market Value", "P&L ($)", "P&L (%)"]
    styled = (
        display.style
        .apply(_color_signed, subset=["P&L ($)", "P&L (%)"])
        .format({
            "Shares":       "{:.4f}",
            "Avg Cost":     "${:,.2f}",
            "Live Price":   "${:,.2f}",
            "Market Value": "${:,.2f}",
            "P&L ($)":      "${:+,.2f}",
            "P&L (%)":      "{:+.2f}%",
        }, na_rep="N/A")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

def show_options_table(df):
    display = df[["Description","Contracts","CostPerSh","ValPerSh",
                  "TotalCost","TotalMV","PnL","PnLPct"]].copy()
    display.columns = ["Description", "Contracts", "Cost/Share", "Val/Share",
                       "Total Cost", "Total MV", "P&L ($)", "P&L (%)"]
    styled = (
        display.style
        .apply(_color_signed, subset=["P&L ($)", "P&L (%)"])
        .format({
            "Cost/Share": "${:,.2f}",
            "Val/Share":  "${:,.2f}",
            "Total Cost": "${:,.2f}",
            "Total MV":   "${:,.2f}",
            "P&L ($)":    "${:+,.2f}",
            "P&L (%)":    "{:+.2f}%",
        })
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

def show_metrics(cost, mv, pnl, pct, labels=None):
    if labels is None:
        labels = ["Cost Basis", "Market Value", "P&L ($)", "P&L (%)"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(labels[0], f"${cost:,.2f}")
    c2.metric(labels[1], f"${mv:,.2f}")
    c3.metric(labels[2], f"${pnl:+,.2f}")
    c4.metric(labels[3], f"{pct:+.2f}%")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

# ── Header ───────────────────────────────────────────────────────────────────
h1, h2, h3 = st.columns([5, 1, 1])
with h1:
    st.title("📈 Portfolio Tracker")
    st.caption(f"Prices cached for 5 min · Page loaded: {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
with h2:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with h3:
    st.write("")
    if st.button("🔒 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

st.divider()

# ── Fetch prices ─────────────────────────────────────────────────────────────
all_tickers = tuple(sorted({t for t, *_ in MOOMOO_STOCKS + SCB_STOCKS}))
with st.spinner("Fetching live prices…"):
    prices = fetch_prices(all_tickers)

failed = [t for t, p in prices.items() if p is None]
if failed:
    st.warning(f"⚠ Could not fetch price for: {', '.join(failed)}")

# ── Pre-compute all numbers ───────────────────────────────────────────────────
mm_df  = build_stock_df(MOOMOO_STOCKS, prices)
scb_df = build_stock_df(SCB_STOCKS, prices)
opt_df = build_options_df()

mm_st_cost, mm_st_mv, mm_st_pnl, mm_st_pct = stock_totals(mm_df)
op_cost,    op_mv,    op_pnl,    op_pct     = option_totals(opt_df)
scb_cost,   scb_mv,   scb_pnl,   scb_pct   = stock_totals(scb_df)

mm_cost = mm_st_cost + op_cost
mm_mv   = mm_st_mv   + op_mv
mm_pnl  = mm_st_pnl  + op_pnl
mm_pct  = mm_pnl / mm_cost * 100 if mm_cost else 0.0

comb_cost = mm_cost + scb_cost
comb_mv   = mm_mv   + scb_mv
comb_pnl  = mm_pnl  + scb_pnl
comb_pct  = comb_pnl / comb_cost * 100 if comb_cost else 0.0

# ── MOOMOO ───────────────────────────────────────────────────────────────────
st.header("🟦 Account 1 — Moomoo")

with st.expander("**Stocks**", expanded=True):
    show_stock_table(mm_df)
    st.caption("Subtotal")
    show_metrics(mm_st_cost, mm_st_mv, mm_st_pnl, mm_st_pct)

st.write("")

with st.expander("**Options** (static pricing — no live feed)", expanded=True):
    show_options_table(opt_df)
    st.caption("Subtotal")
    show_metrics(op_cost, op_mv, op_pnl, op_pct)

st.write("")
st.markdown("##### Moomoo Account Total")
show_metrics(mm_cost, mm_mv, mm_pnl, mm_pct)
st.divider()

# ── SCB ──────────────────────────────────────────────────────────────────────
st.header("🟩 Account 2 — Standard Chartered Bank")

with st.expander("**Stocks**", expanded=True):
    show_stock_table(scb_df)
    st.caption("Subtotal")
    show_metrics(scb_cost, scb_mv, scb_pnl, scb_pct)

st.divider()

# ── COMBINED SUMMARY ──────────────────────────────────────────────────────────
st.header("📊 Combined Portfolio Summary")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Cost Basis",   f"${comb_cost:,.2f}")
c2.metric("Total Market Value", f"${comb_mv:,.2f}")
c3.metric("Total P&L ($)",      f"${comb_pnl:+,.2f}")
c4.metric("Total P&L (%)",      f"{comb_pct:+.2f}%")

st.write("")
ca, cb = st.columns(2)
with ca:
    st.metric("Moomoo — Market Value", f"${mm_mv:,.2f}",
              f"{mm_mv/comb_mv*100:.1f}% of portfolio  ·  P&L {mm_pct:+.2f}%")
with cb:
    st.metric("SCB — Market Value", f"${scb_mv:,.2f}",
              f"{scb_mv/comb_mv*100:.1f}% of portfolio  ·  P&L {scb_pct:+.2f}%")

st.divider()

# ── SECTOR WEIGHTS ────────────────────────────────────────────────────────────
st.header("🗂 Sector / Category Weights")

ticker_mv = {}
for ticker, shares, _ in MOOMOO_STOCKS + SCB_STOCKS:
    p = prices.get(ticker)
    if p:
        ticker_mv[ticker] = ticker_mv.get(ticker, 0.0) + shares * p

cat_rows = []
for cat, tickers in CATEGORIES.items():
    cat_mv_val = sum(ticker_mv.get(t, 0.0) for t in tickers)
    present    = sorted(tickers & ticker_mv.keys())
    w = cat_mv_val / comb_mv * 100 if comb_mv else 0.0
    cat_rows.append({"Category": cat, "Market Value ($)": cat_mv_val,
                     "Weight (%)": round(w, 1), "Constituents": ", ".join(present)})

opt_w = op_mv / comb_mv * 100 if comb_mv else 0.0
cat_rows.append({"Category": "Options Cluster", "Market Value ($)": op_mv,
                 "Weight (%)": round(opt_w, 1),
                 "Constituents": "MSFT ×3, QQQ ×1, IBIT ×2, NVDA ×1"})

cat_df = pd.DataFrame(cat_rows).sort_values("Market Value ($)", ascending=False)

# Bar chart (Category weights)
chart_df = cat_df.set_index("Category")[["Weight (%)"]].sort_values("Weight (%)")
st.bar_chart(chart_df, y_label="Weight (%)")

# Table
styled_cat = (
    cat_df.style
    .format({"Market Value ($)": "${:,.2f}", "Weight (%)": "{:.1f}%"})
    .background_gradient(subset=["Weight (%)"], cmap="Blues")
)
st.dataframe(styled_cat, use_container_width=True, hide_index=True)
st.divider()

# ── CONCENTRATION FLAGS ───────────────────────────────────────────────────────
st.header("⚠️ Concentration Flags")
st.caption("Single stock positions exceeding 15% of combined portfolio")

flags = [(t, mv) for t, mv in ticker_mv.items() if mv / comb_mv * 100 > 15.0]
if flags:
    for t, mv in sorted(flags, key=lambda x: -x[1]):
        w = mv / comb_mv * 100
        st.error(f"**{t}** — Market Value: **${mv:,.2f}** — Portfolio Weight: **{w:.1f}%** (threshold: 15%)")
else:
    st.success("✅  No single stock position exceeds 15% of combined portfolio.")

st.divider()

# ── MSFT CLUSTER ──────────────────────────────────────────────────────────────
st.header("🔍 MSFT Cluster Analysis")
st.caption("Shares across both accounts + all MSFT option contracts")

msft_p     = prices.get("MSFT") or 0.0
msft_mm_mv = 45 * msft_p
msft_sc_mv = 40 * msft_p
msft_op_mv = sum(c * 100 * v for d, c, _, v in MOOMOO_OPTIONS if "MSFT" in d)
msft_total = msft_mm_mv + msft_sc_mv + msft_op_mv
msft_w     = msft_total / comb_mv * 100 if comb_mv else 0.0

mc1, mc2, mc3, mc4 = st.columns(4)
mc1.metric("Moomoo (45 shares)",   f"${msft_mm_mv:,.2f}")
mc2.metric("SCB (40 shares)",      f"${msft_sc_mv:,.2f}")
mc3.metric("Options (3 contracts)",f"${msft_op_mv:,.2f}",
           "Jun27 $340 + Dec26 $375 + Jun28 $450")
mc4.metric("Cluster Total MV",     f"${msft_total:,.2f}",
           f"{msft_w:.1f}% of combined portfolio")

st.divider()

# ── COMBINED EXPOSURES ────────────────────────────────────────────────────────
st.header("🔗 Combined Stock Exposures")

cols = st.columns(len(COMBINED_EXPOSURES))
for i, (ticker, legs) in enumerate(COMBINED_EXPOSURES):
    p = prices.get(ticker) or 0.0
    total_sh = sum(sh for sh, _ in legs)
    total_mv_e = total_sh * p
    w = total_mv_e / comb_mv * 100 if comb_mv else 0.0
    with cols[i]:
        st.markdown(f"**{ticker}**")
        st.markdown(f"@ ${p:,.2f}")
        for sh, label in legs:
            st.markdown(f"• {label}:  \n  `{sh:.4f} sh = ${sh*p:,.2f}`")
        st.markdown("---")
        st.markdown(f"**Total: ${total_mv_e:,.2f}**  \n`{w:.1f}% of portfolio`")

st.divider()
st.caption(f"Data provided by Yahoo Finance via yfinance · {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
