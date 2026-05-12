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

### MT Data Feed (NSE/BSE)

```bash
cp backend/.env.example backend/.env
# edit MT_SUBSCRIPTIONS to taste (NIFTY50/NIFTYBANK preset)
uvicorn app.main:app --reload
```

`PRICE_WS_FORMAT=mt` speaks the funnel-op protocol: anonymous Login →
TokenRequest per FeedType → 3s heartbeat → IndexData/DepthData → Tick.

### Docker

```bash
docker compose up --build
# UI on http://localhost:8080, API on http://localhost:8000
```

`backend/.env` is loaded by the backend container; the frontend nginx config
proxies `/api` and `/ws` to it.

### Bulkowski ingest

```bash
cd backend
pip install -e ".[knowledge]"
python -m app.knowledge.ingest_book --pdf "/path/to/encyclopedia.pdf"
# review backend/app/knowledge/patterns_extracted.yaml; if it looks right:
python -m app.knowledge.ingest_book --pdf "/path/to/encyclopedia.pdf" --apply
```

The parser is best-effort — `--apply` is opt-in so a noisy extract can't
quietly overwrite the curated `patterns.yaml`.

### Recording OHLCV for ML training

Set `RECORD_OHLCV=true` in `backend/.env`. Every closed bar lands in
`data/ohlcv/{symbol}_{tf}.csv`. After a few weeks of capture:

```bash
pip install -e ".[ml]"
python -m app.ml.train --data "../data/ohlcv/*.csv" --epochs 20
```

## Tests

```bash
cd backend && pytest -q
```
