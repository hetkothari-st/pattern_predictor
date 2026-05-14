"""Bulk-download NSE/BSE historical OHLCV via yfinance.

yfinance limitations on intraday history:
  1m  → 7 days max per request, 30 days total available
  5m  → 60 days max
  15m → 60 days max
  30m → 60 days max
  60m → 730 days
  1d  → unlimited

We chunk through the allowed window so the user gets the maximum
available history per resolution. Output goes to data/ohlcv/{symbol}_{tf}.csv
in the same shape the recorder produces, so the trainer + backtest harness
read both interchangeably.

Usage:
    python -m app.tools.fetch_history
    python -m app.tools.fetch_history --symbols NIFTY50,NIFTYBANK --tfs 5m,15m,1h
"""
from __future__ import annotations

import argparse
import csv
import logging
import time as _time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("fetch_history")

# yfinance ticker codes for the indices we care about.
SYMBOL_TO_TICKER: dict[str, str] = {
    "NIFTY50": "^NSEI",
    "NIFTYBANK": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN",
}

# yfinance interval -> (interval string, max-period-per-request, total-history-days)
TF_PARAMS: dict[str, tuple[str, int, int]] = {
    "1m": ("1m", 7, 30),
    "5m": ("5m", 60, 60),
    "15m": ("15m", 60, 60),
    "30m": ("30m", 60, 60),
    "1h": ("60m", 60, 730),
    "1d": ("1d", 365, 365 * 20),
}


def _out_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ohlcv"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)


def _fetch_chunk(ticker: str, interval: str, start: datetime, end: datetime):
    import yfinance as yf

    df = yf.download(
        tickers=ticker,
        interval=interval,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        return []
    # Some tickers return MultiIndex columns when threads=False; flatten.
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    rows = []
    for ts, row in df.iterrows():
        try:
            ts_unix = ts.tz_convert("UTC").timestamp() if ts.tzinfo else ts.timestamp()
        except Exception:
            ts_unix = ts.timestamp()
        rows.append(
            {
                "ts": float(ts_unix),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0) or 0),
            }
        )
    return rows


def _write_csv(symbol: str, tf: str, rows: list[dict]) -> Path:
    if not rows:
        return None  # type: ignore
    path = _out_dir() / f"{_safe(symbol)}_{tf}.csv"
    # Merge with anything already on disk; dedupe on ts; sort.
    existing: dict[float, dict] = {}
    if path.exists():
        with path.open() as f:
            for r in csv.DictReader(f):
                try:
                    existing[float(r["ts"])] = {k: float(v) for k, v in r.items()}
                except (KeyError, ValueError):
                    continue
    for r in rows:
        existing[r["ts"]] = r
    sorted_rows = sorted(existing.values(), key=lambda r: r["ts"])
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for r in sorted_rows:
            w.writerow([r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]])
    return path


def fetch_symbol_tf(symbol: str, tf: str, max_days: int | None = None) -> int:
    """Pull all available history for one (symbol, tf). Returns row count."""
    if symbol not in SYMBOL_TO_TICKER:
        log.warning("unknown symbol %s; skipping", symbol)
        return 0
    if tf not in TF_PARAMS:
        log.warning("unknown tf %s; skipping", tf)
        return 0

    ticker = SYMBOL_TO_TICKER[symbol]
    interval, chunk_days, total_days = TF_PARAMS[tf]
    if max_days is not None:
        total_days = min(total_days, max_days)

    end = datetime.utcnow()
    earliest = end - timedelta(days=total_days)
    all_rows: list[dict] = []
    cursor_end = end
    while cursor_end > earliest:
        chunk_start = max(cursor_end - timedelta(days=chunk_days), earliest)
        try:
            rows = _fetch_chunk(ticker, interval, chunk_start, cursor_end)
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch failed %s/%s [%s..%s]: %s", symbol, tf, chunk_start, cursor_end, exc)
            rows = []
        log.info(
            "  %s/%s chunk %s..%s -> %d rows",
            symbol, tf, chunk_start.date(), cursor_end.date(), len(rows),
        )
        all_rows.extend(rows)
        cursor_end = chunk_start
        _time.sleep(0.4)  # polite pause to avoid rate limits

    path = _write_csv(symbol, tf, all_rows)
    log.info("wrote %d unique rows to %s", len(all_rows), path)
    return len(all_rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--symbols",
        default=",".join(SYMBOL_TO_TICKER.keys()),
        help="comma-separated list",
    )
    ap.add_argument(
        "--tfs",
        default="5m,15m,1h,1d",
        help=f"comma-separated subset of {','.join(TF_PARAMS.keys())}",
    )
    ap.add_argument("--max-days", type=int, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]

    grand = 0
    for symbol in symbols:
        for tf in tfs:
            log.info("→ %s / %s", symbol, tf)
            grand += fetch_symbol_tf(symbol, tf, max_days=args.max_days)
    log.info("done. total rows fetched: %d", grand)


if __name__ == "__main__":
    main()
