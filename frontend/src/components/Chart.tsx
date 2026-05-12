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
import type { Detection } from "../types";

const COMPLETED_COLORS: Record<"bullish" | "bearish", string> = {
  bullish: "rgba(46, 160, 67, 0.18)",
  bearish: "rgba(248, 81, 73, 0.18)",
};
const FORMING_COLORS: Record<"bullish" | "bearish", string> = {
  bullish: "rgba(46, 160, 67, 0.07)",
  bearish: "rgba(248, 81, 73, 0.07)",
};

export function Chart() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const overlayRef = useRef<{
    bands: ISeriesApi<"Area">[];
    lines: ISeriesApi<"Line">[];
  }>({ bands: [], lines: [] });

  const bars = useStore((s) => s.bars);
  const detections = useStore((s) => s.detections);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0e1116" },
        textColor: "#c9d1d9",
      },
      grid: {
        vertLines: { color: "#21262d" },
        horzLines: { color: "#21262d" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#30363d" },
      timeScale: { borderColor: "#30363d", timeVisible: true, secondsVisible: false },
      autoSize: true,
    });
    const candles = chart.addCandlestickSeries({
      upColor: "#3fb950",
      downColor: "#f85149",
      borderVisible: false,
      wickUpColor: "#3fb950",
      wickDownColor: "#f85149",
    });
    chartRef.current = chart;
    candleRef.current = candles;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
    };
  }, []);

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

  const activeDetections = useMemo(() => Object.values(detections), [detections]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    // Tear down previous overlays.
    overlayRef.current.bands.forEach((s) => chart.removeSeries(s));
    overlayRef.current.lines.forEach((s) => chart.removeSeries(s));
    overlayRef.current = { bands: [], lines: [] };
    const markers: Parameters<ISeriesApi<"Candlestick">["setMarkers"]>[0] = [];

    activeDetections.forEach((d: Detection) => {
      const color =
        d.status === "completed"
          ? COMPLETED_COLORS[d.direction]
          : FORMING_COLORS[d.direction];
      // Shaded band as a wide area series along the detection time range.
      if (d.anchors.length >= 2) {
        const minPrice = Math.min(...d.anchors.map((a) => a.price));
        const maxPrice = Math.max(...d.anchors.map((a) => a.price));
        const area = chart.addAreaSeries({
          topColor: color,
          bottomColor: color,
          lineColor: color,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        area.setData([
          { time: d.start_ts as Time, value: maxPrice },
          { time: d.end_ts as Time, value: maxPrice },
        ]);
        overlayRef.current.bands.push(area);
        // A second area at the bottom of the band, so the shading reads as a rectangle.
        const areaBot = chart.addAreaSeries({
          topColor: color,
          bottomColor: color,
          lineColor: color,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        areaBot.setData([
          { time: d.start_ts as Time, value: minPrice },
          { time: d.end_ts as Time, value: minPrice },
        ]);
        overlayRef.current.bands.push(areaBot);
      }

      // Connect anchors with a thin line so the structure is visible.
      if (d.anchors.length >= 2) {
        const line = chart.addLineSeries({
          color: d.direction === "bullish" ? "#3fb950" : "#f85149",
          lineWidth: 1,
          lineStyle: d.status === "completed" ? LineStyle.Solid : LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        line.setData(
          d.anchors
            .slice()
            .sort((a, b) => a.ts - b.ts)
            .map((a) => ({ time: a.ts as Time, value: a.price }))
        );
        overlayRef.current.lines.push(line);
      }

      d.anchors.forEach((a) => {
        markers.push({
          time: a.ts as Time,
          position: "aboveBar",
          color: d.direction === "bullish" ? "#3fb950" : "#f85149",
          shape: "circle",
          text: a.label,
        });
      });
    });

    candleRef.current?.setMarkers(markers);
  }, [activeDetections]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
