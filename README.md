# Binance Futures PnL Tracker

A simple Streamlit app with:
- demo login (`rahim` / `rahim123`)
- Binance Futures perpetual symbol dropdown + search
- open trade logging for long/short positions
- live mark-price based PnL
- SQLite built-in database (`trades.db`)
- trade history page with open trades on top and closed trades below
- close-trade workflow with final realized PnL

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. In Streamlit Community Cloud, choose the repo and set the main file to `app.py`.
3. Deploy.

## Notes

- This app uses Binance Futures public endpoints for symbol discovery and mark prices.
- The database is SQLite and is created automatically on first run.
- The login is intentionally hardcoded because that is what was requested. It is **not** secure for production use.
