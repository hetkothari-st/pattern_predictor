# Chart Pattern Intelligence

Real-time chart-pattern detection for traders. Ingests a live price WebSocket, builds OHLCV bars, runs rule-based detectors plus a small ML model, and renders the result on a TradingView-style chart (Lightweight Charts).

**This is an advisory tool, not a trading bot.** Every signal carries a calibrated probability and the historical follow-through statistic from *Encyclopedia of Chart Patterns* (Bulkowski). The trader makes the call.

## Quickstart

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
export PRICE_WS_URL="wss://your-price-feed/stream"   # your existing feed
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Offline replay (no live feed needed)

```bash
cd backend
python -m app.tools.replay --csv ../data/sample.csv --symbol BTCUSDT --speed 60
```

Streams a historical CSV through the live pipeline at 60× wall-clock so the full UI can be exercised without market hours.

## Layout

See the implementation plan in `data/PLAN.md` for the phased build and the design rationale.

## Tests

```bash
cd backend && pytest -q
```
