# Stock Portfolio Simulator

A small Python and Streamlit project for learning historical stock trading simulation.
Requires Python 3.10 or newer. 

## Run

On Windows, double-click `start.bat` and keep its terminal window open.
If Streamlit asks for an email on first launch, press Enter to skip it.
Alternatively, run these commands from the project folder:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

Opening `main.py` directly does not launch the web interface.

## Use the simulator

1. Choose a Market Date and click Load Prices.
2. Review prices for AAPL, MSFT, NVDA, AMZN and GOOGL.
3. Select a stock to view its closing-price chart and trade forms.
4. Enter a positive whole number of shares and click Buy or Sell.
5. Review cash, holdings, total assets, profit/loss, return and Trade History.

The single portfolio starts with 100,000 USD. Trades use the selected date's closing price, with no fees or slippage.
Insufficient cash or sellable shares will prevent a trade. Shares can only be sold on a date later than their purchase date.
For example, buying 10 shares yesterday and 5 today allows selling at most 10 shares today.
After the first trade, the simulation date cannot move backwards, even after all holdings have been sold.

- Holdings value = sum of each stock's shares multiplied by its price on the selected date.
- Total assets = cash + holdings value.
- Total profit/loss = total assets - 100,000 USD, including realized and unrealized results.
- Return = total profit/loss / 100,000 x 100%.

If any holding has no price for the selected date, full valuation and returns are unavailable.
Trade History includes the date, side, symbol, shares, price, amount, cash before and cash after each successful trade.

## Data and API key

Set the key in `.streamlit/secrets.toml`:

```toml
ALPHA_VANTAGE_API_KEY = "your key"
```

The environment variable with the same name is also supported. Never commit the secrets file.
The app uses Alpha Vantage TIME_SERIES_DAILY with outputsize=compact, covering the latest 100 trading days.
It does not provide a 100-day window around any arbitrary past date.
Closed market dates, missing prices and API failures show messages instead of silently selecting another date.
Successful responses are cached for one hour. Charts exclude dates after the selected simulation date.
Prices are unadjusted; splits and dividends are not processed, which may distort simulated performance.
This is an educational closing-price simulation, not a model of real order execution.

## Local saving

Trades and date changes are saved automatically to `portfolio.json` beside `main.py`.
On startup, the app replays saved trades to restore cash, holdings, history and the simulation date.
Old saves with Chinese Buy/Sell labels are supported without clearing the portfolio.
A temporary file is written before replacing the save. If saving fails, the operation is not applied.
If loading fails, the original file is preserved and an error message is displayed.

**Reset Simulation restores 100,000 USD and clears holdings, history and the saved date.**
Use only one browser tab: this local version does not handle concurrent users, cloud synchronization or automatic backups.
Market prices are not saved, so older restored dates may eventually fall outside the API's latest 100 trading days.
The save and secrets files are excluded from Git.

## Read the code

Start with `trade_stock`, `sellable_shares` and `show_portfolio` to understand the calculations.
Then read `quote_on_date`, `fetch_daily`, `show_market` and `main` for data and page flow.
Finally, study `save_portfolio`, `load_portfolio` and `saved_trade` for persistence.

Dense expressions have been expanded into loops and intermediate variables.
Decimal, Streamlit session state, caching, deep copies and temporary-file saving remain because they protect correct behavior.
More lines do not necessarily mean more complexity: the goal is to show one step at a time.

## Tests

```powershell
python -m unittest test_main -v
```

Tests use mock prices and temporary save files. They do not consume API quota or change the real portfolio.
