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
            "User-Agent": "Mozilla/5.0 FuturesPnLTracker/1.4",
            "Accept": "application/json",
        }
    )
    return session


def delete_trade_record(trade_id: int) -> None:
    import sqlite3

    conn = sqlite3.connect("trades.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .main > div {
                padding-top: 1rem;
            }
            .block-container {
                padding-top: 1rem;
                padding-bottom: 1.6rem;
            }
            .app-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 1rem 1rem 0.9rem 1rem;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
                margin-bottom: 0.85rem;
            }
            .big-title {
                font-size: 1.9rem;
                font-weight: 800;
                margin-bottom: 0.2rem;
                color: #0f172a;
            }
            .muted {
                color: #6b7280;
                font-size: 0.96rem;
            }
            .metric-box {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                padding: 0.9rem;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
                min-height: 100px;
            }
            .metric-box-profit {
                background: rgba(34, 197, 94, 0.10);
                border: 1px solid rgba(34, 197, 94, 0.35);
            }
            .metric-box-loss {
                background: rgba(239, 68, 68, 0.10);
                border: 1px solid rgba(239, 68, 68, 0.35);
            }
            .trade-pill {
                display: inline-block;
                padding: 0.22rem 0.58rem;
                border-radius: 999px;
                font-size: 0.76rem;
                font-weight: 700;
                margin-right: 0.35rem;
                margin-bottom: 0.35rem;
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
                font-size: 0.82rem;
            }
            .trade-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                padding: 0.8rem;
                margin-bottom: 0.7rem;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
            }
            .source-badge {
                display: inline-block;
                margin-top: 0.35rem;
                padding: 0.25rem 0.65rem;
                border-radius: 999px;
                font-size: 0.8rem;
                font-weight: 700;
                background: rgba(99, 102, 241, 0.12);
                color: #4338ca;
            }
            .trade-mini-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                margin-bottom: 0.4rem;
            }
            .trade-symbol {
                font-weight: 800;
                font-size: 1rem;
                color: #0f172a;
            }
            .history-table-wrap {
                overflow-x: auto;
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 0.3rem;
                margin-top: 0.75rem;
                margin-bottom: 1rem;
            }
            .history-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 16px;
            }
            .history-table th {
                background: #f3f4f6;
                font-weight: 800;
                text-align: center;
                padding: 12px 10px;
                border: 1px solid #d1d5db;
                white-space: nowrap;
                font-size: 16px;
            }
            .history-table td {
                text-align: center;
                font-weight: 700;
                padding: 10px 8px;
                border: 1px solid #e5e7eb;
                white-space: nowrap;
                font-size: 15px;
            }
            .history-row-open {
                background: #ffffff;
            }
            .history-row-closed {
                background: #fff7cc !important;
            }
            .history-profit {
                color: #15803d;
                font-weight: 800;
            }
            .history-loss {
                color: #b91c1c;
                font-weight: 800;
            }
            .action-btn {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 8px;
                font-weight: 800;
                font-size: 14px;
            }
            div[data-testid="stMetric"] {
                background: transparent;
                border-radius: 10px;
                padding: 0;
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
    _, center, _ = st.columns([1, 1.1, 1])

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
            extra_class = ""
            if label == "Unrealized PnL":
                extra_class = " metric-box-profit" if total_unrealized >= 0 else " metric-box-loss"

            st.markdown(f"<div class='metric-box{extra_class}'>", unsafe_allow_html=True)
            st.markdown(f"<div class='small-label'><b>{label}</b></div>", unsafe_allow_html=True)

            if label == "Unrealized PnL":
                st.markdown(
                    f"<div class='{pnl_class(total_unrealized)}' style='font-size:1.6rem; margin-top:0.45rem; font-weight:800;'>{value}</div>",
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
    trade_id = int(trade["id"])

    close_key = f"close_manual_{trade_id}"
    delete_key = f"delete_confirm_{trade_id}"

    if close_key not in st.session_state:
        current_price = prices.get(symbol)
        st.session_state[close_key] = float(current_price if current_price is not None else entry_price)
    if delete_key not in st.session_state:
        st.session_state[delete_key] = False

    current_price = prices.get(symbol) if status == "OPEN" else None
    pnl_value = 0.0 if current_price is None else pnl_for_trade(side, quantity, entry_price, current_price)

    bg_class = ""
    if status == "OPEN":
        bg_class = " metric-box-profit" if pnl_value >= 0 else " metric-box-loss"

    st.markdown(f"<div class='trade-card{bg_class}'>", unsafe_allow_html=True)

    head_left, head_right = st.columns([5, 1])
    with head_left:
        st.markdown(
            f"<div class='trade-mini-head'>"
            f"<div>"
            f"<span class='trade-pill {'long-pill' if side == 'LONG' else 'short-pill'}'>{side}</span>"
            f"<span class='trade-pill {'open-pill' if status == 'OPEN' else 'closed-pill'}'>{status}</span>"
            f"<span class='trade-symbol'>{symbol}</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with head_right:
        if st.button("✖", key=f"delete_btn_{trade_id}", help="Delete this trade", use_container_width=True):
            st.session_state[delete_key] = True
            st.rerun()

    cols = st.columns([1, 1, 1, 1, 1, 1])
    cols[0].markdown(f"**Qty**  \n{format_money(quantity)}")
    cols[1].markdown(f"**Entry**  \n{format_money(entry_price)}")

    if status == "OPEN":
        current_display = "N/A" if current_price is None else format_money(current_price)
        cols[2].markdown(f"**Live**  \n{current_display}")
        cols[3].markdown(
            f"**PnL**  \n<span class='{pnl_class(pnl_value)}'>{format_money(pnl_value)}</span>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(f"**Opened**  \n{trade['created_at']}")
        cols[5].markdown("")

        action1, action2 = st.columns([2.2, 2.8])

        if allow_close:
            with action1:
                with st.expander(f"Close #{trade_id}"):
                    st.caption(f"Live market price: {current_display}")

                    with st.form(f"close_form_{trade_id}"):
                        close_price = st.number_input(
                            "Close Price",
                            min_value=0.00000001,
                            value=float(st.session_state[close_key]),
                            format="%.8f",
                            key=f"close_price_{trade_id}",
                        )
                        submitted = st.form_submit_button("Confirm Close", use_container_width=True)

                    st.session_state[close_key] = close_price

                    if submitted:
                        close_trade(trade_id, float(close_price))
                        st.success(f"Trade #{trade_id} closed.")
                        st.session_state.pop(close_key, None)
                        st.rerun()
    else:
        close_price = float(trade["close_price"] or 0)
        realized_pnl = float(trade["realized_pnl"] or 0)
        cols[2].markdown(f"**Close**  \n{format_money(close_price)}")
        cols[3].markdown(
            f"**Final PnL**  \n<span class='{pnl_class(realized_pnl)}'>{format_money(realized_pnl)}</span>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(f"**Closed**  \n{trade['closed_at'] or '-'}")
        cols[5].markdown("")

    if st.session_state.get(delete_key):
        st.warning(f"Delete trade #{trade_id} permanently?")
        d1, d2 = st.columns(2)
        with d1:
            if st.button("Yes, Delete", key=f"confirm_delete_{trade_id}", use_container_width=True):
                delete_trade_record(trade_id)
                st.session_state.pop(delete_key, None)
                st.session_state.pop(close_key, None)
                st.success(f"Trade #{trade_id} deleted.")
                st.rerun()
        with d2:
            if st.button("Cancel", key=f"cancel_delete_{trade_id}", use_container_width=True):
                st.session_state[delete_key] = False
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_history_table(trades: List[dict], prices: Dict[str, float]) -> None:
    rows_html = []

    sorted_trades = sorted(
        trades,
        key=lambda t: (0 if t["status"] == "OPEN" else 1, -int(t["id"]))
    )

    for trade in sorted_trades:
        symbol = trade["symbol"]
        status = trade["status"]
        side = trade["side"]
        quantity = float(trade["quantity"])
        entry_price = float(trade["entry_price"])
        live_price = prices.get(symbol)

        live_pnl = ""
        live_pnl_class = ""
        if status == "OPEN" and live_price is not None:
            pnl_val = pnl_for_trade(side, quantity, entry_price, float(live_price))
            live_pnl = format_money(pnl_val)
            live_pnl_class = "history-profit" if pnl_val >= 0 else "history-loss"

        final_pnl = trade["realized_pnl"]
        final_pnl_display = ""
        final_pnl_class = ""
        if final_pnl is not None:
            final_pnl = float(final_pnl)
            final_pnl_display = format_money(final_pnl)
            final_pnl_class = "history-profit" if final_pnl >= 0 else "history-loss"

        row_class = "history-row-closed" if status == "CLOSED" else "history-row-open"

        rows_html.append(
            f"""
            <tr class="{row_class}">
                <td>{trade['id']}</td>
                <td>{status}</td>
                <td>{symbol}</td>
                <td>{side}</td>
                <td>{format_money(quantity)}</td>
                <td>{format_money(entry_price)}</td>
                <td>{format_money(float(live_price)) if live_price is not None else ''}</td>
                <td class="{live_pnl_class}">{live_pnl}</td>
                <td>{format_money(float(trade['close_price'])) if trade['close_price'] is not None else ''}</td>
                <td class="{final_pnl_class}">{final_pnl_display}</td>
                <td>{trade['created_at'] or ''}</td>
                <td>{trade['closed_at'] or ''}</td>
            </tr>
            """
        )

    table_html = f"""
    <div class="history-table-wrap">
        <table class="history-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Status</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Entry Price</th>
                    <th>Live Price</th>
                    <th>Live PnL</th>
                    <th>Close Price</th>
                    <th>Final PnL</th>
                    <th>Created At</th>
                    <th>Closed At</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def dashboard_page(symbols: List[str], prices: Dict[str, float], data_source: str, source_message: str) -> None:
    st_autorefresh(interval=AUTO_REFRESH_MS, key="dashboard_refresh")

    top_bar(data_source, source_message)
    render_trade_form(symbols, prices, data_source)

    trades = get_all_trades()
    open_trades = [t for t in trades if t["status"] == "OPEN"]

    summarize_open_trades(trades, prices)

    st.markdown("### Ongoing Trades")

    filter_options = ["ALL"] + sorted({t["symbol"] for t in trades})
    selected_filter = st.selectbox("Filter by coin", options=filter_options, key="dashboard_trade_filter")

    if selected_filter != "ALL":
        open_trades = [t for t in open_trades if t["symbol"] == selected_filter]

    if not open_trades:
        st.info("No open trades found for this filter.")
        return

    for trade in open_trades:
        render_trade_card(trade, prices, allow_close=True)


def history_page(prices: Dict[str, float], data_source: str, source_message: str) -> None:
    st_autorefresh(interval=AUTO_REFRESH_MS, key="history_refresh")

    head1, head2 = st.columns([4, 1.2])

    with head1:
        st.markdown("<div class='big-title'>Trade History</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Compact table view with close-trade and delete controls.</div>",
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

    filter_options = ["ALL"] + sorted({t["symbol"] for t in trades})
    selected_filter = st.selectbox("Filter history by coin", options=filter_options, key="history_trade_filter")

    filtered_trades = trades
    if selected_filter != "ALL":
        filtered_trades = [t for t in trades if t["symbol"] == selected_filter]

    if not filtered_trades:
        st.info("No trades found for this filter.")
        return

    render_history_table(filtered_trades, prices)

    open_trades = [t for t in filtered_trades if t["status"] == "OPEN"]

    close_col, delete_col = st.columns(2)

    with close_col:
        st.markdown("### Close Trade From History")

        if open_trades:
            open_labels = [
                f"#{t['id']} | {t['symbol']} | {t['side']} | Qty {format_money(float(t['quantity']))}"
                for t in open_trades
            ]
            trade_map = {label: trade for label, trade in zip(open_labels, open_trades)}

            selected_label = st.selectbox(
                "Select open trade to close",
                options=open_labels,
                key="history_close_trade_select",
            )
            selected_trade = trade_map[selected_label]

            close_key = f"history_close_manual_{selected_trade['id']}"
            if close_key not in st.session_state:
                current_price = prices.get(selected_trade["symbol"])
                st.session_state[close_key] = float(
                    current_price if current_price is not None else float(selected_trade["entry_price"])
                )

            current_live = prices.get(selected_trade["symbol"])
            st.caption(
                f"Live market price for {selected_trade['symbol']}: "
                f"{format_money(float(current_live)) if current_live is not None else 'N/A'}"
            )

            with st.form("history_close_form"):
                close_price = st.number_input(
                    "Manual Close Price",
                    min_value=0.00000001,
                    value=float(st.session_state[close_key]),
                    format="%.8f",
                    key="history_close_price_input",
                )
                submitted = st.form_submit_button("Close Selected Trade", use_container_width=True)

            st.session_state[close_key] = close_price

            if submitted:
                close_trade(int(selected_trade["id"]), float(close_price))
                st.success(f"Trade #{selected_trade['id']} closed.")
                st.session_state.pop(close_key, None)
                st.rerun()
        else:
            st.info("There are no open trades to close in this filter.")

    with delete_col:
        st.markdown("### Delete Trade")
        trade_labels = [
            f"#{t['id']} | {t['symbol']} | {t['side']} | {t['status']}"
            for t in filtered_trades
        ]
        trade_map = {label: trade for label, trade in zip(trade_labels, filtered_trades)}

        selected_delete_label = st.selectbox(
            "Select trade to delete",
            options=trade_labels,
            key="history_delete_trade_select",
        )
        delete_trade_obj = trade_map[selected_delete_label]

        confirm_delete = st.checkbox(
            f"Confirm delete trade #{delete_trade_obj['id']}",
            key="history_delete_confirm_checkbox",
        )

        if st.button("Delete Selected Trade", use_container_width=True, key="history_delete_btn"):
            if confirm_delete:
                delete_trade_record(int(delete_trade_obj["id"]))
                st.success(f"Trade #{delete_trade_obj['id']} deleted.")
                st.rerun()
            else:
                st.error("Please confirm deletion first.")

    export_rows = []
    sorted_trades = sorted(
        filtered_trades,
        key=lambda t: (0 if t["status"] == "OPEN" else 1, -int(t["id"]))
    )

    for trade in sorted_trades:
        symbol = trade["symbol"]
        live_price = prices.get(symbol)
        live_pnl = None

        if trade["status"] == "OPEN" and live_price is not None:
            live_pnl = pnl_for_trade(
                trade["side"],
                float(trade["quantity"]),
                float(trade["entry_price"]),
                float(live_price),
            )

        export_rows.append(
            {
                "ID": trade["id"],
                "Status": trade["status"],
                "Symbol": trade["symbol"],
                "Side": trade["side"],
                "Qty": trade["quantity"],
                "Entry Price": trade["entry_price"],
                "Live Price": live_price,
                "Live PnL": live_pnl,
                "Close Price": trade["close_price"],
                "Final PnL": trade["realized_pnl"],
                "Created At": trade["created_at"],
                "Closed At": trade["closed_at"],
            }
        )

    df = pd.DataFrame(export_rows)

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
