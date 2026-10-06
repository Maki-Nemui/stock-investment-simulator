import json
import os
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from math import isfinite
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import streamlit as st


INITIAL_CAPITAL = 100000
STOCKS = {"AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon", "GOOGL": "Alphabet"}
DEFAULT_SAVE_FILE = Path(__file__).with_name("portfolio.json")
SAVE_FILE = Path(os.environ.get("SIMULATOR_SAVE_FILE", DEFAULT_SAVE_FILE))
LEGACY_SIDES = {"买入": "Buy", "卖出": "Sell"}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_daily(symbol, api_key):
    query = urlencode({
        "function": "TIME_SERIES_DAILY", "symbol": symbol,
        "outputsize": "compact", "apikey": api_key,
    })
    try:
        with urlopen("https://www.alphavantage.co/query?" + query, timeout=20) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, OSError):
        raise ValueError("Could not connect to the market data service. Check your connection and try again.") from None
    except (ValueError, UnicodeError):
        raise ValueError("The market data service returned unreadable data.") from None

    if not isinstance(payload, dict):
        raise ValueError("The market data format is invalid.")
    if "Information" in payload or "Note" in payload:
        raise ValueError("API request limited. Check your account quota and permissions.")
    if "Error Message" in payload or not payload.get("Time Series (Daily)"):
        raise ValueError("The API returned no daily prices for this stock.")
    try:
        frame = pd.DataFrame.from_dict(payload["Time Series (Daily)"], orient="index")
        frame = frame[["4. close"]]
        frame = frame.rename(columns={"4. close": "Close"})
        frame = frame.astype(float)
        frame.index = pd.to_datetime(frame.index)
        frame = frame.sort_index()
        frame = frame.tail(100)
        if frame.empty:
            raise ValueError
        for price in frame["Close"]:
            if not isfinite(price) or price <= 0:
                raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("The API returned incomplete or invalid closing prices.") from None
    return frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def quote_on_date(frame, selected_date):
    day = pd.Timestamp(selected_date)
    if day not in frame.index:
        if day < frame.index.min():
            raise ValueError("The selected date is earlier than the latest 100 trading days.")
        raise ValueError("No data for this date. The market may be closed or daily prices are not yet available.")
    price = frame.loc[day, "Close"]
    earlier_dates = frame.index < day
    previous = frame.loc[earlier_dates, "Close"]
    change = None
    if not previous.empty and previous.iloc[-1] != 0:
        previous_price = previous.iloc[-1]
        change = (price / previous_price - 1) * 100
    return price, change


def new_portfolio():
    return {"cash": Decimal(str(INITIAL_CAPITAL)), "holdings": {}, "history": []}


def save_portfolio(portfolio, selected_date):
    data = {"history": portfolio["history"], "selected_date": selected_date}
    temporary = SAVE_FILE.with_suffix(".tmp")
    try:
        text = json.dumps(data, default=str, ensure_ascii=False, indent=2)
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(SAVE_FILE)
    except OSError:
        raise ValueError("Save failed. Check folder permissions. This operation was not applied.") from None


def load_portfolio():
    portfolio = new_portfolio()
    try:
        text = SAVE_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get("history"), list):
            raise ValueError
        selected = None
        if data["selected_date"]:
            selected = date.fromisoformat(data["selected_date"])
        for trade in data["history"]:
            trade_stock(portfolio, trade["symbol"], trade["shares"], trade["price"],
                        date.fromisoformat(trade["date"]), trade["side"])
        if portfolio["history"]:
            last_trade_date = portfolio["history"][-1]["date"]
            if selected is None or selected < last_trade_date:
                raise ValueError
        return portfolio, selected
    except FileNotFoundError:
        return portfolio, None
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation):
        raise ValueError("Could not read portfolio.json. Check the file or back it up and move it before restarting. The original file was not overwritten.") from None


def saved_trade(portfolio, symbol, shares, price, selected_date, side):
    updated = deepcopy(portfolio)
    amount = trade_stock(updated, symbol, shares, price, selected_date, side)
    save_portfolio(updated, selected_date)
    portfolio.update(updated)
    return amount


def sellable_shares(portfolio, symbol, trade_date):
    available = 0
    for trade in portfolio["history"]:
        if trade["symbol"] == symbol:
            if trade["side"] == "Buy" and trade["date"] < trade_date:
                available += trade["shares"]
            elif trade["side"] == "Sell":
                available -= trade["shares"]
    return max(0, available)


def trade_stock(portfolio, symbol, shares, price, trade_date, side):
    price = Decimal(str(price))
    side = LEGACY_SIDES.get(side, side)
    if side not in ("Buy", "Sell"):
        raise ValueError("Choose Buy or Sell.")
    if symbol not in STOCKS:
        raise ValueError("Choose a supported stock.")
    if type(shares) is not int or shares <= 0:
        raise ValueError("Enter a positive whole number of shares.")
    if not price.is_finite() or price <= 0:
        raise ValueError("The current price is invalid. Trading is unavailable.")
    if portfolio["history"] and trade_date < portfolio["history"][-1]["date"]:
        raise ValueError("The trade date cannot be earlier than the previous trade.")
    amount = price * shares
    if side == "Buy":
        if amount > portfolio["cash"]:
            raise ValueError("Insufficient cash. Reduce the number of shares.")
        change = shares
        cash_after = portfolio["cash"] - amount
    else:
        if shares > sellable_shares(portfolio, symbol, trade_date):
            raise ValueError("Not enough sellable shares. Only unsold shares bought before this date can be sold.")
        change = -shares
        cash_after = portfolio["cash"] + amount
    record = {"date": trade_date, "side": side, "symbol": symbol, "shares": shares,
              "price": price, "amount": amount, "cash_before": portfolio["cash"], "cash_after": cash_after}
    portfolio["cash"] = cash_after
    old_shares = portfolio["holdings"].get(symbol, 0)
    portfolio["holdings"][symbol] = old_shares + change
    if portfolio["holdings"][symbol] == 0:
        del portfolio["holdings"][symbol]
    portfolio["history"].append(record)
    return amount


def show_history(portfolio):
    st.subheader("Trade History")
    if not portfolio["history"]:
        st.info("No trades in this simulation yet.")
        return
    rows = []
    for trade in portfolio["history"]:
        row = {
            "Date": str(trade["date"]),
            "Side": trade["side"],
            "Stock": trade["symbol"],
            "Shares": trade["shares"],
            "Trade Price (USD)": f'{trade["price"]:,.4f}',
            "Trade Amount (USD)": f'{trade["amount"]:,.2f}',
            "Cash Before (USD)": f'{trade["cash_before"]:,.2f}',
            "Cash After (USD)": f'{trade["cash_after"]:,.2f}',
        }
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True)


def show_portfolio(portfolio, prices):
    holdings = portfolio["holdings"]
    complete = True
    market_value = Decimal("0")
    for symbol, shares in holdings.items():
        if symbol not in prices:
            complete = False
            continue
        price = Decimal(str(prices[symbol]))
        market_value += price * shares

    value_text = "Valuation unavailable"
    assets_text = "Valuation unavailable"
    profit_text = "Valuation unavailable"
    return_text = "Valuation unavailable"
    if complete:
        total_assets = portfolio["cash"] + market_value
        profit = total_assets - Decimal(str(INITIAL_CAPITAL))
        return_percent = profit / INITIAL_CAPITAL * 100
        value_text = f"${market_value:,.2f}"
        assets_text = f"${total_assets:,.2f}"
        profit_text = f"{profit:+,.2f}"
        return_text = f"{return_percent:+.2f}%"
    cols = st.columns(3)
    cols[0].metric("Cash Balance (USD)", f'${portfolio["cash"]:,.2f}')
    cols[1].metric("Holdings Value (USD)", value_text)
    cols[2].metric("Total Assets (USD)", assets_text)
    result = st.columns(2)
    result[0].metric("Total Profit / Loss (USD)", profit_text)
    result[1].metric("Return (%)", return_text)
    if not complete:
        st.warning("Some holdings have no price for this date. Full valuation and returns are unavailable.")
    if holdings:
        rows = []
        for symbol, shares in holdings.items():
            stock_name = f"{STOCKS[symbol]} ({symbol})"
            rows.append({"Stock": stock_name, "Shares Held": shares})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    else:
        st.info("No holdings yet. Choose a date to buy stocks.")


def show_market(api_key, selected_date, portfolio):
    rows = []
    histories = {}
    timestamps = []
    prices = {}
    with st.spinner("Loading historical prices..."):
        for symbol, name in STOCKS.items():
            try:
                frame, fetched_at = fetch_daily(symbol, api_key)
                price, change = quote_on_date(frame, selected_date)
            except ValueError as error:
                st.warning(f"{name} ({symbol}): {error}")
                continue
            if change is None:
                change_text = "Previous price unavailable"
            else:
                change_text = f"{change:+.2f}%"
            rows.append({
                "Company": name, "Symbol": symbol, "Close (USD)": f"{price:.2f}",
                "Daily Change": change_text,
            })
            histories[symbol] = frame.loc[frame.index <= pd.Timestamp(selected_date)]
            timestamps.append(fetched_at)
            prices[symbol] = price
    if not rows:
        st.info("No prices to display. Choose another date or check the messages above.")
        return prices
    st.write(f"Market Date: **{selected_date:%Y-%m-%d}**")
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption("Data fetched at (local time): " + max(timestamps))
    symbol = st.selectbox("Select a stock", list(histories))
    st.subheader("Simulated Trading")
    st.write(f"Stock: {STOCKS[symbol]} ({symbol}) | Trade price: {prices[symbol]:.4f} USD")
    with st.form("buy_form", clear_on_submit=True):
        shares = st.number_input("Shares to buy", min_value=1, value=1, step=1)
        buy = st.form_submit_button("Buy")
    if buy:
        try:
            cost = saved_trade(portfolio, symbol, shares, prices[symbol], selected_date, "Buy")
            st.success(f"Bought {shares} shares of {symbol} for {cost:,.2f} USD.")
        except ValueError as error:
            st.error(str(error))
    available = sellable_shares(portfolio, symbol, selected_date)
    with st.form("sell_form", clear_on_submit=True):
        sell_shares = st.number_input("Shares to sell", min_value=1, value=1, step=1)
        sell = st.form_submit_button("Sell", disabled=available == 0)
    if sell:
        try:
            amount = saved_trade(portfolio, symbol, sell_shares, prices[symbol], selected_date, "Sell")
            st.success(f"Sold {sell_shares} shares of {symbol} for {amount:,.2f} USD.")
        except ValueError as error:
            st.error(str(error))
    available = sellable_shares(portfolio, symbol, selected_date)
    st.caption(f"Sellable shares: {available}. Shares can only be sold after their purchase date.")
    st.caption("Trades use the selected date's closing price with no fees. Total assets = cash + holdings value.")
    st.subheader(f"{STOCKS[symbol]} ({symbol}) - Closing Prices")
    st.line_chart(histories[symbol], x_label="Trading Date", y_label="Close (USD)")
    st.caption("Shows available prices up to the selected date within the latest 100 trading days. Prices are unadjusted for splits and dividends.")
    return prices


def main():
    st.set_page_config(page_title="Stock Portfolio Simulator", layout="wide")
    st.title("Stock Portfolio Simulator")
    st.subheader("My Portfolio")
    st.metric("Initial Capital (USD)", f"${INITIAL_CAPITAL:,.2f}")
    if "portfolio" not in st.session_state:
        try:
            portfolio, selected = load_portfolio()
        except ValueError as error:
            st.error(str(error))
            return
        st.session_state.portfolio = portfolio
        if selected is not None:
            st.session_state.selected_date = selected
            st.session_state.date_choice = selected
    st.caption("Reset restores 100,000 USD and clears holdings, trade history and the saved simulation date.")
    if st.button("Reset Simulation"):
        try:
            save_portfolio(new_portfolio(), None)
            st.session_state.portfolio = new_portfolio()
            for key in ("selected_date", "date_choice"):
                st.session_state.pop(key, None)
        except ValueError as error:
            st.error(str(error))
    portfolio = st.session_state.portfolio
    if "history" not in portfolio:
        st.warning("This older session has no trade dates. Reset the simulation to continue.")
        return
    for trade in portfolio["history"]:
        trade["side"] = LEGACY_SIDES.get(trade["side"], trade["side"])
    summary = st.container()
    st.caption("Trades and date changes are saved locally to portfolio.json and restored on startup. Use only one browser tab.")
    st.subheader("Market Overview")
    st.caption("Historical US stock prices from Alpha Vantage | Latest 100 trading days | Change from the previous trading day")

    if "date_choice" not in st.session_state:
        st.session_state.date_choice = date.today()
    with st.form("date_form"):
        chosen = st.date_input("Market Date", value=None, key="date_choice",
                               min_value=date(1999, 1, 1), max_value=date.today())
        submitted = st.form_submit_button("Load Prices")
    if submitted and chosen is None:
        st.error("Please choose a market date first.")
    elif submitted:
        if portfolio["history"] and chosen < st.session_state.selected_date:
            st.error("You cannot move backwards after trading. The previous simulation date is still active.")
        else:
            try:
                save_portfolio(portfolio, chosen)
                st.session_state.selected_date = chosen
            except ValueError as error:
                st.error(str(error))
    if "selected_date" not in st.session_state:
        with summary:
            show_portfolio(portfolio, {})
        show_history(portfolio)
        st.info("Choose a date and click Load Prices. Closed market dates are not replaced with other dates.")
        return

    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
        except FileNotFoundError:
            pass
    if not api_key:
        st.error("Set ALPHA_VANTAGE_API_KEY in .streamlit/secrets.toml.")
        with summary:
            show_portfolio(portfolio, {})
        show_history(portfolio)
        return
    prices = show_market(api_key, st.session_state.selected_date, portfolio)
    with summary:
        st.caption(f"Valuation Date: {st.session_state.selected_date}")
        show_portfolio(portfolio, prices)
    show_history(portfolio)


if __name__ == "__main__":
    main()
