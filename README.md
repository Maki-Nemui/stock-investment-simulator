# Stock Portfolio Simulator

A small Streamlit app for exploring historical stock trades and portfolio performance. Each browser session starts with 100,000 USD and keeps its portfolio in memory using Streamlit session state.

## Features

- Daily closing prices for AAPL, MSFT, NVDA, AMZN and GOOGL from Alpha Vantage.
- Buy and sell whole shares, with cash and sellable-share validation.
- Holdings, cash, total assets, profit/loss, return percentage and trade history.
- Closing-price chart and two market analytics: annualized volatility and maximum drawdown.
- Reset the current session to 100,000 USD.
- One-hour API caching and clear messages for missing prices, connection errors and API limits.

The API uses `TIME_SERIES_DAILY` with `outputsize=compact`: up to the latest 100 trading days, not arbitrary historical dates. The date selector uses the earliest available AAPL date as its lower bound, falling back to another supported stock if AAPL data is unavailable. Weekends, holidays and missing dates are never replaced automatically.

Trades use the selected date's closing price without fees. Shares can only be sold after their purchase date. After trading, the simulation date cannot move backwards. Total assets equal cash plus holdings value; profit/loss equals total assets minus initial capital; return equals profit/loss divided by initial capital.

Analytics use the selected stock's chart data up to the simulation date. Annualized volatility is the sample standard deviation of daily percentage returns multiplied by the square root of 252; it needs at least two returns. Maximum drawdown is the largest loss from a running closing-price peak, displayed as a positive percentage. Prices are unadjusted for splits and dividends.

Portfolios are independent across sessions. Trades survive Streamlit reruns within a session, but a new session or server restart starts fresh. No portfolio files or database are used.

## Technologies

- Python 3.10+
- Streamlit for the interface, session state and caching
- pandas for price data and analytics
- Python standard library: Decimal for portfolio calculations and urllib/json for API requests
- Alpha Vantage for market data

## Live Demo

A public demo URL has not been configured in this repository. Run the app locally using the instructions below.

## Run Locally

From the project folder:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

On Windows, you can also double-click `start.bat`. Keep its terminal window open. Choose a market date, click **Load Prices**, select a stock and use **Buy** or **Sell**. **Reset Simulation** clears only the current session's portfolio and date.

## Alpha Vantage API Key

Create `.streamlit/secrets.toml` in the project folder:

```toml
ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY"
```

Alternatively, set an environment variable before starting Streamlit:

```powershell
$env:ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY"
python -m streamlit run main.py
```

The environment variable takes precedence. Keep real keys private; `.streamlit/secrets.toml` is excluded from Git.

## Tests

```powershell
python -m unittest test_main -v
```

Tests use mock market data and do not consume API quota.
