/**
 * Tiny pub/sub so the RobotWidget can read the chart's current
 * latest-bar coordinate without React re-rendering the chart.
 */
import type { IChartApi, ISeriesApi } from "lightweight-charts";

export interface ChartHandle {
  chart: IChartApi;
  series: ISeriesApi<"Candlestick">;
}

let handle: ChartHandle | null = null;
const listeners = new Set<(h: ChartHandle | null) => void>();

export function setChartHandle(next: ChartHandle | null) {
  handle = next;
  listeners.forEach((fn) => fn(handle));
}

export function getChartHandle() {
  return handle;
}

export function subscribeChartHandle(fn: (h: ChartHandle | null) => void) {
  listeners.add(fn);
  fn(handle);
  return () => {
    listeners.delete(fn);
  };
}
