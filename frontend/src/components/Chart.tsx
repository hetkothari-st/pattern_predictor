import { useEffect, useMemo, useRef } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  IChartApi,
  ISeriesApi,
  LineStyle,
  Time,
} from "lightweight-charts";
import { useStore } from "../state/store";
import { setChartHandle } from "../state/chartHandle";
import type { Detection } from "../types";

interface ChartProps {
  theme: "dark" | "light";
}

const PALETTE = {
  dark: {
    bg: "#0a0c10",
    text: "#a7abb2",
    grid: "#1a1e26",
    border: "#353c48",
    crosshair: "#c9ccd3",
    crosshairLabelBg: "#1c2129",
    bull: "#1ad17d",
    bear: "#ff3b4d",
  },
  light: {
    bg: "#ffffff",
    text: "#404853",
    grid: "#e5e8ec",
    border: "#a8adb6",
    crosshair: "#404853",
    crosshairLabelBg: "#e7ebf0",
    bull: "#008f5a",
    bear: "#e8243a",
  },
};

export function Chart({ theme }: ChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const overlayRef = useRef<{ lines: ISeriesApi<"Line">[] }>({ lines: [] });

  const bars = useStore((s) => s.bars);
  const detections = useStore((s) => s.detections);

  useEffect(() => {
    if (!containerRef.current) return;
    const p = PALETTE[theme];
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: p.bg },
        textColor: p.text,
        fontFamily:
          "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: p.grid },
        horzLines: { color: p.grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: p.crosshair,
          style: LineStyle.Dashed,
          width: 1,
          labelVisible: true,
          labelBackgroundColor: p.crosshairLabelBg,
        },
        horzLine: {
          color: p.crosshair,
          style: LineStyle.Dashed,
          width: 1,
          labelVisible: true,
          labelBackgroundColor: p.crosshairLabelBg,
        },
      },
      rightPriceScale: {
        borderColor: p.border,
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      timeScale: {
        borderColor: p.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 8,
      },
      autoSize: true,
    });
    const candles = chart.addCandlestickSeries({
      upColor: p.bull,
      downColor: p.bear,
      borderVisible: false,
      wickUpColor: p.bull,
      wickDownColor: p.bear,
    });
    chartRef.current = chart;
    candleRef.current = candles;
    overlayRef.current = { lines: [] };
    setChartHandle({ chart, series: candles });
    return () => {
      setChartHandle(null);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      overlayRef.current = { lines: [] };
    };
  }, [theme]);

  useEffect(() => {
    if (!candleRef.current) return;
    candleRef.current.setData(
      bars.map((b) => ({
        time: b.ts as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    );
  }, [bars]);

  const activeDetections = useMemo(() => {
    const all = Object.values(detections);
    const completed = all
      .filter((d) => d.status === "completed")
      .sort((a, b) => b.confidence - a.confidence);
    const forming = all
      .filter((d) => d.status === "forming")
      .sort((a, b) => b.confidence - a.confidence);
    return [...completed.slice(0, 1), ...forming.slice(0, 1)];
  }, [detections]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const p = PALETTE[theme];
    overlayRef.current.lines.forEach((s) => {
      try {
        chart.removeSeries(s);
      } catch {
        /* already gone */
      }
    });
    overlayRef.current = { lines: [] };
    const markers: Parameters<ISeriesApi<"Candlestick">["setMarkers"]>[0] = [];

    activeDetections.forEach((d: Detection) => {
      const lineColor = d.direction === "bullish" ? p.bull : p.bear;

      if (d.anchors.length >= 2) {
        const seen = new Set<number>();
        const points = d.anchors
          .slice()
          .sort((a, b) => a.ts - b.ts)
          .filter((a) => {
            if (!Number.isFinite(a.ts) || !Number.isFinite(a.price)) return false;
            if (seen.has(a.ts)) return false;
            seen.add(a.ts);
            return true;
          })
          .map((a) => ({ time: a.ts as Time, value: a.price }));
        if (points.length >= 2) {
          const line = chart.addLineSeries({
            color: lineColor,
            lineWidth: 3,
            lineStyle: d.status === "completed" ? LineStyle.Solid : LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          try {
            line.setData(points);
            overlayRef.current.lines.push(line);
            // Highlight neckline / mid anchor for completed double-tops/bottoms.
            if (d.status === "completed") {
              const mid = d.anchors.find((a) => /confirm|neck|breakout/i.test(a.label));
              if (mid && Number.isFinite(mid.price)) {
                line.createPriceLine({
                  price: mid.price,
                  color: lineColor,
                  lineWidth: 1,
                  lineStyle: LineStyle.Dotted,
                  axisLabelVisible: true,
                  title: mid.label || "neckline",
                });
              }
            }
          } catch {
            try {
              chart.removeSeries(line);
            } catch {
              /* noop */
            }
          }
        }
      }

      // Anchor dots — visible on chart so user sees pattern being drawn.
      // Skip last anchor on completed (arrow marker replaces it).
      const lastIdx = d.anchors.length - 1;
      const anchorPos: "aboveBar" | "belowBar" =
        d.direction === "bullish" ? "belowBar" : "aboveBar";
      d.anchors.forEach((a, idx) => {
        if (!Number.isFinite(a.ts) || !Number.isFinite(a.price)) return;
        if (d.status === "completed" && idx === lastIdx) return;
        markers.push({
          time: a.ts as Time,
          position: anchorPos,
          color: lineColor,
          shape: "circle",
          text: a.label || String(idx + 1),
        });
      });

      if (d.status === "completed" && d.anchors.length > 0) {
        const tip = d.anchors[d.anchors.length - 1];
        if (Number.isFinite(tip.ts)) {
          markers.push({
            time: tip.ts as Time,
            position: d.direction === "bullish" ? "belowBar" : "aboveBar",
            color: lineColor,
            shape: d.direction === "bullish" ? "arrowUp" : "arrowDown",
            text: d.pattern.replaceAll("_", " "),
          });
        }
      }
    });

    const seenT = new Set<number>();
    const ordered = markers
      .sort((a, b) => (a.time as number) - (b.time as number))
      .filter((m) => {
        const t = m.time as number;
        if (seenT.has(t)) return false;
        seenT.add(t);
        return true;
      });
    try {
      candleRef.current?.setMarkers(ordered);
    } catch {
      /* HMR can briefly leave the series detached */
    }
  }, [activeDetections, theme]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
