import os
from typing import Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import add_trade, close_trade, get_all_trades, init_db

st.set_page_config(
    page_title="Futures PnL Tracker",
    page_icon="📈",
    layout="wide",
)

init_db()

BINANCE_FUTURES_TICKER_PRICE = "https://fapi.binance.com/fapi/v1/ticker/price"
OKX_SWAP_INSTRUMENTS = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"
OKX_SWAP_TICKERS = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"

LOGIN_USERNAME = st.secrets.get("APP_USERNAME", os.getenv("APP_USERNAME", "rahim"))
LOGIN_PASSWORD = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", "rahim123"))

REQUEST_TIMEOUT = 20
AUTO_REFRESH_MS = 3000
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def get_http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 FuturesPnLTracker/1.3",
            "Accept": "application/json",
        }
    )
    return session


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .main > div {
                padding-top: 1.2rem;
            }
            .block-container {
                padding-top: 1.2rem;
                padding-bottom: 2rem;
            }
            .app-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 18px;
                padding: 1.15rem 1.15rem 1rem 1.15rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
                margin-bottom: 1rem;
            }
            .big-title {
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.25rem;
                color: #0f172a;
            }
            .muted {
                color: #6b7280;
                font-size: 0.97rem;
            }
            .metric-box {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 1rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
                min-height: 108px;
            }
            .trade-pill {
                display: inline-block;
                padding: 0.25rem 0.65rem;
                border-radius: 999px;
                font-size: 0.8rem;
                font-weight: 700;
                margin-right: 0.45rem;
                margin-bottom: 0.5rem;
            }
            .long-pill {
                background: rgba(34, 197, 94, 0.12);
                color: #15803d;
            }
            .short-pill {
                background: rgba(239, 68, 68, 0.12);
                color: #b91c1c;
            }
            .open-pill {
                background: rgba(59, 130, 246, 0.12);
                color: #1d4ed8;
            }
            .closed-pill {
                background: rgba(107, 114, 128, 0.12);
                color: #374151;
            }
            .pnl-profit {
                color: #15803d;
                font-weight: 800;
            }
            .pnl-loss {
                color: #b91c1c;
                font-weight: 800;
            }
            .small-label {
                color: #6b7280;
                font-size: 0.84rem;
            }
            .trade-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 18px;
                padding: 1rem;
                margin-bottom: 0.9rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            }
            .source-badge {
                display: inline-block;
                margin-top: 0.4rem;
                padding: 0.25rem 0.65rem;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 700;
                background: rgba(99, 102, 241, 0.12);
                color: #4338ca;
            }
            div[data-testid="stMetric"] {
                background: #ffffff;
                border-radius: 12px;
                padding: 0.1rem 0.1rem 0.1rem 0;
            }
            div[data-testid="stForm"] {
                border: none !important;
                padding: 0 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=2, show_spinner=False)
def fetch_binance_ticker_prices() -> Dict[str, float]:
    session = get_http_session()
    response = session.get(BINANCE_FUTURES_TICKER_PRICE, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    prices: Dict[str, float] = {}
    if isinstance(payload, list):
        for item in payload:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            try:
                prices[symbol] = float(item.get("price", 0))
            except (TypeError, ValueError):
                continue

    return prices


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_okx_symbols() -> List[str]:
    session = get_http_session()
    response = session.get(OKX_SWAP_INSTRUMENTS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    symbols: List[str] = []
    for item in payload.get("data", []):
        inst_id = item.get("instId", "")
        if inst_id.endswith("-USDT-SWAP") and item.get("state") == "live":
            symbols.append(inst_id.replace("-", ""))

    return sorted(symbols)


@st.cache_data(ttl=2, show_spinner=False)
def fetch_okx_ticker_prices() -> Dict[str, float]:
    session = get_http_session()
    response = session.get(OKX_SWAP_TICKERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    prices: Dict[str, float] = {}
    for item in payload.get("data", []):
        inst_id = item.get("instId", "")
        if not inst_id.endswith("-USDT-SWAP"):
            continue

        symbol = inst_id.replace("-", "")
        raw_price = item.get("last") or item.get("markPx")
        try:
            prices[symbol] = float(raw_price)
        except (TypeError, ValueError):
            continue

    return prices


@st.cache_data(ttl=2, show_spinner=False)
def load_market_data() -> Tuple[List[str], Dict[str, float], str, str]:
    try:
        prices = fetch_binance_ticker_prices()
        symbols = sorted(prices.keys())
        if symbols:
            return (
                symbols,
                prices,
                "Binance Futures",
                "Live futures prices from Binance ticker endpoint.",
            )
        raise requests.RequestException("No Binance futures prices were returned.")
    except requests.RequestException as binance_error:
        try:
            symbols = fetch_okx_symbols()
            prices = fetch_okx_ticker_prices()
            if symbols:
                return (
                    symbols,
                    prices,
                    "OKX Swap Fallback",
                    f"Binance was unavailable ({binance_error}). Using OKX perpetual swap prices instead.",
                )
            raise requests.RequestException("No OKX swap symbols were returned.")
        except requests.RequestException as okx_error:
            return (
                DEFAULT_SYMBOLS,
                {},
                "Offline Fallback",
                f"Binance failed: {binance_error}. OKX also failed: {okx_error}",
            )


def format_money(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:,.4f}"
    return f"{value:,.8f}"


def pnl_for_trade(side: str, quantity: float, entry_price: float, current_price: float) -> float:
    if side == "LONG":
        return (current_price - entry_price) * quantity
    return (entry_price - current_price) * quantity


def pnl_class(value: float) -> str:
    return "pnl-profit" if value >= 0 else "pnl-loss"


def show_login() -> None:
    left, center, right = st.columns([1, 1.1, 1])

    with center:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("<div class='big-title'>Futures PnL Tracker</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Login with your requested demo credentials.</div>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="rahim")
            password = st.text_input("Password", type="password", placeholder="rahim123")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["page"] = "dashboard"
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.markdown("</div>", unsafe_allow_html=True)


def top_bar(data_source: str, source_message: str) -> None:
    col1, col2, col3 = st.columns([4, 1.2, 1])

    with col1:
        st.markdown("<div class='big-title'>Futures Portfolio Tracker</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Live perpetual-price based PnL with automatic market-data fallback.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='source-badge'>Source: {data_source}</div>", unsafe_allow_html=True)
        st.caption(source_message)

    with col2:
        if st.button("Open Trade History", use_container_width=True):
            st.session_state["page"] = "history"
            st.rerun()

    with col3:
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def render_trade_form(symbols: List[str], prices: Dict[str, float], data_source: str) -> None:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.subheader("Add New Trade")
    st.caption(f"Available symbols loaded from {data_source}.")

    if "trade_search" not in st.session_state:
        st.session_state["trade_search"] = ""
    if "selected_symbol" not in st.session_state:
        st.session_state["selected_symbol"] = "BTCUSDT" if "BTCUSDT" in symbols else symbols[0]
    if "manual_entry_price" not in st.session_state:
        initial_symbol = st.session_state["selected_symbol"]
        st.session_state["manual_entry_price"] = float(prices.get(initial_symbol, 100.0))

    search_text = st.text_input(
        "Search Futures Symbol",
        placeholder="Type BTC, ETH, SOL, XRP...",
        key="trade_search",
    ).strip().upper()

    filtered_symbols = [s for s in symbols if search_text in s] if search_text else symbols
    if not filtered_symbols:
        st.warning("No matching symbol found. Showing full symbol list.")
        filtered_symbols = symbols

    if st.session_state["selected_symbol"] not in filtered_symbols:
        st.session_state["selected_symbol"] = filtered_symbols[0]

    current_market_price = float(prices.get(st.session_state["selected_symbol"], 0.0))

    with st.form("new_trade_form", clear_on_submit=False):
        c1, c2, c3, c4, c5 = st.columns([2.0, 1.0, 1.0, 1.1, 1.1])

        with c1:
            symbol = st.selectbox(
                "Symbol",
                options=filtered_symbols,
                index=filtered_symbols.index(st.session_state["selected_symbol"]),
            )

        with c2:
            side = st.selectbox("Side", options=["LONG", "SHORT"], index=0)

        with c3:
            quantity = st.number_input(
                "Quantity",
                min_value=0.00000001,
                value=0.001,
                format="%.8f",
            )

        with c4:
            st.markdown("**Live Price**")
            st.write(format_money(float(prices.get(symbol, 0.0))))

        with c5:
            entry_price = st.number_input(
                "Entry Price",
                min_value=0.00000001,
                value=float(st.session_state["manual_entry_price"]),
                format="%.8f",
                key="entry_price_input",
            )

        submitted = st.form_submit_button("Add Trade", use_container_width=True)

    st.session_state["selected_symbol"] = symbol
    st.session_state["manual_entry_price"] = entry_price

    if submitted:
        add_trade(
            symbol=symbol,
            side=side,
            quantity=float(quantity),
            entry_price=float(entry_price),
        )
        st.success(f"{side} trade added for {symbol}.")
        st.session_state["manual_entry_price"] = float(prices.get(symbol, entry_price))
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def summarize_open_trades(trades: List[dict], prices: Dict[str, float]) -> None:
    open_trades = [t for t in trades if t["status"] == "OPEN"]

    open_count = len(open_trades)
    total_unrealized = 0.0
    exposure = 0.0
    win_count = 0

    for trade in open_trades:
        current_price = prices.get(trade["symbol"])
        if current_price is None:
            continue

        quantity = float(trade["quantity"])
        entry_price = float(trade["entry_price"])

        pnl = pnl_for_trade(trade["side"], quantity, entry_price, current_price)
        total_unrealized += pnl
        exposure += quantity * entry_price

        if pnl > 0:
            win_count += 1

    cols = st.columns(4)
    metric_values = [
        ("Open Trades", str(open_count)),
        ("Unrealized PnL", format_money(total_unrealized)),
        ("Entry Exposure", format_money(exposure)),
        ("Trades in Profit", str(win_count)),
    ]

    for col, (label, value) in zip(cols, metric_values):
        with col:
            st.markdown("<div class='metric-box'>", unsafe_allow_html=True)
            st.markdown(f"<div class='small-label'>{label}</div>", unsafe_allow_html=True)

            if label == "Unrealized PnL":
                st.markdown(
                    f"<div class='{pnl_class(total_unrealized)}' style='font-size:1.6rem; margin-top:0.45rem;'>{value}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='font-size:1.6rem; font-weight:800; margin-top:0.45rem;'>{value}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)


def render_trade_card(trade: dict, prices: Dict[str, float], allow_close: bool) -> None:
    symbol = trade["symbol"]
    side = trade["side"]
    quantity = float(trade["quantity"])
    entry_price = float(trade["entry_price"])
    status = trade["status"]

    close_key = f"close_manual_{trade['id']}"
    if close_key not in st.session_state:
        current_price = prices.get(symbol)
        st.session_state[close_key] = float(current_price if current_price is not None else entry_price)

    st.markdown("<div class='trade-card'>", unsafe_allow_html=True)

    pill_side_class = "long-pill" if side == "LONG" else "short-pill"
    pill_status_class = "open-pill" if status == "OPEN" else "closed-pill"

    st.markdown(
        f"<span class='trade-pill {pill_side_class}'>{side}</span>"
        f"<span class='trade-pill {pill_status_class}'>{status}</span>"
        f"<span style='font-weight:800; font-size:1.1rem;'>{symbol}</span>",
        unsafe_allow_html=True,
    )

    cols = st.columns([1.1, 1.1, 1.1, 1.2, 1.4])
    cols[0].metric("Quantity", format_money(quantity))
    cols[1].metric("Entry Price", format_money(entry_price))

    if status == "OPEN":
        current_price = prices.get(symbol)
        current_display = "N/A" if current_price is None else format_money(current_price)
        pnl_value = 0.0 if current_price is None else pnl_for_trade(side, quantity, entry_price, current_price)

        cols[2].metric("Current Price", current_display)
        cols[3].markdown(
            f"<div class='small-label'>Live PnL</div>"
            f"<div class='{pnl_class(pnl_value)}' style='font-size:1.45rem; margin-top:0.35rem;'>{format_money(pnl_value)}</div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='small-label'>Opened</div>"
            f"<div style='font-weight:600; margin-top:0.35rem;'>{trade['created_at']}</div>",
            unsafe_allow_html=True,
        )

        if allow_close:
            with st.expander(f"Close trade #{trade['id']}"):
                st.caption(f"Live market price: {current_display}")

                with st.form(f"close_form_{trade['id']}"):
                    close_price = st.number_input(
                        "Close Price",
                        min_value=0.00000001,
                        value=float(st.session_state[close_key]),
                        format="%.8f",
                        key=f"close_price_{trade['id']}",
                    )
                    submitted = st.form_submit_button("Confirm Close", use_container_width=True)

                st.session_state[close_key] = close_price

                if submitted:
                    close_trade(int(trade["id"]), float(close_price))
                    st.success(f"Trade #{trade['id']} closed.")
                    st.session_state.pop(close_key, None)
                    st.rerun()

    else:
        close_price = float(trade["close_price"] or 0)
        realized_pnl = float(trade["realized_pnl"] or 0)

        cols[2].metric("Close Price", format_money(close_price))
        cols[3].markdown(
            f"<div class='small-label'>Final PnL</div>"
            f"<div class='{pnl_class(realized_pnl)}' style='font-size:1.45rem; margin-top:0.35rem;'>{format_money(realized_pnl)}</div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='small-label'>Closed</div>"
            f"<div style='font-weight:600; margin-top:0.35rem;'>{trade['closed_at'] or '-'}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def dashboard_page(symbols: List[str], prices: Dict[str, float], data_source: str, source_message: str) -> None:
    st_autorefresh(interval=AUTO_REFRESH_MS, key="dashboard_refresh")

    top_bar(data_source, source_message)
    render_trade_form(symbols, prices, data_source)

    trades = get_all_trades()
    summarize_open_trades(trades, prices)

    st.markdown("### Ongoing Trades")
    open_trades = [t for t in trades if t["status"] == "OPEN"]

    if not open_trades:
        st.info("No open trades yet.")
        return

    for trade in open_trades:
        render_trade_card(trade, prices, allow_close=True)


def history_page(prices: Dict[str, float], data_source: str, source_message: str) -> None:
    st_autorefresh(interval=AUTO_REFRESH_MS, key="history_refresh")

    head1, head2 = st.columns([4, 1.2])

    with head1:
        st.markdown("<div class='big-title'>Trade History</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Compact table view for all trades.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='source-badge'>Source: {data_source}</div>", unsafe_allow_html=True)
        st.caption(source_message)

    with head2:
        if st.button("Back to Dashboard", use_container_width=True):
            st.session_state["page"] = "dashboard"
            st.rerun()

    trades = get_all_trades()

    if not trades:
        st.info("No trades found.")
        return

    table_rows = []
    for trade in trades:
        symbol = trade["symbol"]
        status = trade["status"]
        entry_price = float(trade["entry_price"])
        quantity = float(trade["quantity"])
        live_price = prices.get(symbol)

        unrealized = None
        if status == "OPEN" and live_price is not None:
            unrealized = pnl_for_trade(trade["side"], quantity, entry_price, float(live_price))

        table_rows.append(
            {
                "ID": trade["id"],
                "Status": trade["status"],
                "Symbol": trade["symbol"],
                "Side": trade["side"],
                "Qty": quantity,
                "Entry Price": entry_price,
                "Live Price": live_price,
                "Live PnL": unrealized,
                "Close Price": trade["close_price"],
                "Final PnL": trade["realized_pnl"],
                "Created At": trade["created_at"],
                "Closed At": trade["closed_at"],
            }
        )

    df = pd.DataFrame(table_rows)
    status_order = {"OPEN": 0, "CLOSED": 1}
    df["_sort"] = df["Status"].map(status_order)
    df = df.sort_values(by=["_sort", "ID"], ascending=[True, False]).drop(columns=["_sort"])

    st.dataframe(
        df,
        use_container_width=True,
        height=520,
        hide_index=True,
    )

    st.download_button(
        "Download Trades CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="trade_history.csv",
        mime="text/csv",
        use_container_width=True,
    )


def main() -> None:
    inject_css()

    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("page", "dashboard")

    if not st.session_state["logged_in"]:
        show_login()
        return

    symbols, prices, data_source, source_message = load_market_data()

    if data_source == "Offline Fallback":
        st.warning(source_message)
    elif data_source != "Binance Futures":
        st.info(source_message)

    if st.session_state["page"] == "history":
        history_page(prices, data_source, source_message)
    else:
        dashboard_page(symbols, prices, data_source, source_message)


if __name__ == "__main__":
    main()
