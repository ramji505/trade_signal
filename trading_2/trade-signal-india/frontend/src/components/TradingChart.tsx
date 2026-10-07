"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  ColorType,
  Time
} from "lightweight-charts";
import { RefreshCw } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";

interface TradingChartProps {
  symbol?: string;
  activeSignal?: {
    direction: "BUY" | "SELL" | "WAIT";
    entry_price?: number | null;
    stop_loss?: number | null;
    target_1?: number | null;
    target_2?: number | null;
  } | null;
}

export const TradingChart: React.FC<TradingChartProps> = ({
  symbol = "NIFTY",
  activeSignal
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const candleSeries = useRef<ISeriesApi<any> | null>(null);
  const ema9Series = useRef<ISeriesApi<any> | null>(null);
  const ema21Series = useRef<ISeriesApi<any> | null>(null);
  const ema50Series = useRef<ISeriesApi<any> | null>(null);
  const vwapSeries = useRef<ISeriesApi<any> | null>(null);

  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("5m");
  const [loading, setLoading] = useState<boolean>(true);
  const [lastPrice, setLastPrice] = useState<number>(22776.1);

  // Indicator visibility toggles
  const [showEma9, setShowEma9] = useState(true);
  const [showEma21, setShowEma21] = useState(true);
  const [showEma50, setShowEma50] = useState(true);
  const [showVwap, setShowVwap] = useState(true);

  // Fetch and populate chart data
  const loadChartData = async (timeframe: string, silent: boolean = false) => {
    try {
      if (!silent) setLoading(true);
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/market/candles?symbol=${symbol}&timeframe=${timeframe}&count=90`);
      if (!res.ok) throw new Error("Failed to fetch candle data");
      const data = await res.json();

      if (data.last_price) {
        setLastPrice(data.last_price);
      }

      if (candleSeries.current && data.candles) {
        const formattedCandles: CandlestickData<Time>[] = data.candles.map((c: any) => ({
          time: c.time as Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));
        candleSeries.current.setData(formattedCandles);
      }

      if (ema9Series.current && data.ema_9) {
        ema9Series.current.setData(data.ema_9.map((p: any) => ({ time: p.time as Time, value: p.value })));
      }
      if (ema21Series.current && data.ema_21) {
        ema21Series.current.setData(data.ema_21.map((p: any) => ({ time: p.time as Time, value: p.value })));
      }
      if (ema50Series.current && data.ema_50) {
        ema50Series.current.setData(data.ema_50.map((p: any) => ({ time: p.time as Time, value: p.value })));
      }
      if (vwapSeries.current && data.vwap) {
        vwapSeries.current.setData(data.vwap.map((p: any) => ({ time: p.time as Time, value: p.value })));
      }

      if (!silent && chartInstance.current) {
        chartInstance.current.timeScale().fitContent();
      }
    } catch (e) {
      console.error("Error loading chart data:", e);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Initialize TradingView Lightweight Chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#090d16" },
        textColor: "#94a3b8",
        fontSize: 12,
        fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
      },
      grid: {
        vertLines: { color: "#1e293b", style: 1 },
        horzLines: { color: "#1e293b", style: 1 },
      },
      crosshair: {
        vertLine: { color: "#475569", width: 1, style: 2 },
        horzLine: { color: "#475569", width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: "#334155",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    chartInstance.current = chart;

    // Candlestick series (Lightweight Charts v5 API)
    const mainSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#f43f5e",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    });
    candleSeries.current = mainSeries;

    // Indicator Line Series
    ema9Series.current = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 2, title: "EMA 9" });
    ema21Series.current = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 2, title: "EMA 21" });
    ema50Series.current = chart.addSeries(LineSeries, { color: "#a855f7", lineWidth: 2, title: "EMA 50" });
    vwapSeries.current = chart.addSeries(LineSeries, { color: "#eab308", lineWidth: 2, title: "VWAP" });

    // Handle Resize
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length > 0 && entries[0].contentRect) {
        const { width, height } = entries[0].contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    loadChartData(selectedTimeframe);

    // Continuous 2-second live polling loop for real-time market ticks
    const tickInterval = setInterval(() => {
      loadChartData(selectedTimeframe, true);
    }, 2000);

    return () => {
      clearInterval(tickInterval);
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [selectedTimeframe]);

  // Update timeframe
  const handleTimeframeChange = (tf: string) => {
    setSelectedTimeframe(tf);
    loadChartData(tf);
  };

  // Toggle indicators visibility
  useEffect(() => {
    if (ema9Series.current) ema9Series.current.applyOptions({ visible: showEma9 });
    if (ema21Series.current) ema21Series.current.applyOptions({ visible: showEma21 });
    if (ema50Series.current) ema50Series.current.applyOptions({ visible: showEma50 });
    if (vwapSeries.current) vwapSeries.current.applyOptions({ visible: showVwap });
  }, [showEma9, showEma21, showEma50, showVwap]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-md overflow-hidden flex flex-col">
      {/* Chart Top Toolbar */}
      <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-950/40">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-white tracking-tight">{symbol} 50</span>
            <span className="text-xs px-2.5 py-0.5 rounded bg-emerald-950/90 text-emerald-400 font-mono font-bold border border-emerald-800/80 flex items-center gap-1.5 shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
              ₹{lastPrice.toFixed(2)}
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60 flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse"></span>
              LIVE 2s
            </span>
          </div>

          {/* Timeframe selector */}
          <div className="flex items-center bg-slate-900 p-1 rounded-lg border border-slate-800">
            {["1m", "3m", "5m", "10m", "15m"].map((tf) => (
              <button
                key={tf}
                onClick={() => handleTimeframeChange(tf)}
                className={`px-2.5 py-1 text-xs font-mono font-semibold rounded-md transition-all ${
                  selectedTimeframe === tf
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* Indicator Legend Toggles */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowEma9(!showEma9)}
            className={`px-2 py-1 text-xs font-mono rounded border flex items-center gap-1.5 transition ${
              showEma9
                ? "bg-sky-950/60 text-sky-400 border-sky-800"
                : "bg-slate-900 text-slate-500 border-slate-800 line-through"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-sky-400"></span>
            EMA 9
          </button>

          <button
            onClick={() => setShowEma21(!showEma21)}
            className={`px-2 py-1 text-xs font-mono rounded border flex items-center gap-1.5 transition ${
              showEma21
                ? "bg-amber-950/60 text-amber-400 border-amber-800"
                : "bg-slate-900 text-slate-500 border-slate-800 line-through"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            EMA 21
          </button>

          <button
            onClick={() => setShowEma50(!showEma50)}
            className={`px-2 py-1 text-xs font-mono rounded border flex items-center gap-1.5 transition ${
              showEma50
                ? "bg-purple-950/60 text-purple-400 border-purple-800"
                : "bg-slate-900 text-slate-500 border-slate-800 line-through"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-purple-400"></span>
            EMA 50
          </button>

          <button
            onClick={() => setShowVwap(!showVwap)}
            className={`px-2 py-1 text-xs font-mono rounded border flex items-center gap-1.5 transition ${
              showVwap
                ? "bg-yellow-950/60 text-yellow-400 border-yellow-800"
                : "bg-slate-900 text-slate-500 border-slate-800 line-through"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-yellow-400"></span>
            VWAP
          </button>

          <button
            onClick={() => loadChartData(selectedTimeframe)}
            title="Refresh Chart"
            className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Chart Canvas Area */}
      <div className="relative w-full h-[420px] bg-slate-950">
        <div ref={chartContainerRef} className="w-full h-full" />

        {/* Active Trade Levels Overlay Banner (if active signal exists) */}
        {activeSignal && activeSignal.direction !== "WAIT" && (
          <div className="absolute top-3 left-3 bg-slate-900/90 border border-slate-700 backdrop-blur-md p-3 rounded-xl shadow-lg flex items-center gap-4 text-xs font-mono">
            <span className={`px-2 py-0.5 rounded font-bold ${
              activeSignal.direction === "BUY" ? "bg-emerald-600 text-white" : "bg-rose-600 text-white"
            }`}>
              {activeSignal.direction}
            </span>
            <div className="flex gap-3 text-slate-300">
              <span>Entry: <strong className="text-white">₹{activeSignal.entry_price}</strong></span>
              <span>SL: <strong className="text-rose-400">₹{activeSignal.stop_loss}</strong></span>
              <span>Tgt 1: <strong className="text-emerald-400">₹{activeSignal.target_1}</strong></span>
              <span>Tgt 2: <strong className="text-emerald-400">₹{activeSignal.target_2}</strong></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
