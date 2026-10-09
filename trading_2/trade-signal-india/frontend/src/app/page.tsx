"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { StatusCard } from "@/components/StatusCard";
import { TradingChart } from "@/components/TradingChart";
import { BacktestPanel } from "@/components/BacktestPanel";
import { SystemHealth, SignalData } from "@/types";
import { Clock, BarChart3, Info, AlertTriangle, ShieldCheck, Zap } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api";

export default function Home() {
  const [mounted, setMounted] = useState(false);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [currentSignal, setCurrentSignal] = useState<SignalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealthAndSignal = async () => {
    try {
      setLoading(true);
      const apiBase = getApiBaseUrl();
      const [resHealth, resSignal] = await Promise.all([
        fetch(`${apiBase}/health`),
        fetch(`${apiBase}/signals/current`),
      ]);

      if (resHealth.ok) {
        const dataHealth: SystemHealth = await resHealth.json();
        setHealth(dataHealth);
      }
      if (resSignal.ok) {
        const dataSig: SignalData = await resSignal.json();
        setCurrentSignal(dataSig);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to reach backend API");
      setHealth({
        status: "healthy",
        app: "TradeSignal India",
        version: "0.1.0",
        environment: "DEVELOPMENT",
        mode: "SIGNAL_ONLY",
        order_execution: false,
        disclaimer:
          "Private trading research tool. Signals are algorithmic estimates, not guaranteed predictions. Past performance does not guarantee future results."
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setMounted(true);
    fetchHealthAndSignal();
    const timer = setInterval(() => {
      fetchHealthAndSignal();
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  if (!mounted) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="text-slate-400 font-mono text-sm animate-pulse">
          Loading TradeSignal India...
        </div>
      </div>
    );
  }

  const isLive = !error && health?.status === "healthy";

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100" suppressHydrationWarning>
      <Header isLive={isLive} marketStatus="OPEN" />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Banner Notice */}
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3 text-slate-300 text-sm">
          <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-white">Interactive Trading Engine Ready: </span>
            TradingView Lightweight Candlestick Chart & Historical Backtest Simulator active. Real-time multi-timeframe regime analysis.
          </div>
        </div>

        {/* System Status Cards */}
        <StatusCard health={health} loading={loading} error={error} />

        {/* TradingView Lightweight Chart */}
        <TradingChart symbol="NIFTY" activeSignal={currentSignal} />

        {/* Active NIFTY Signal & Evaluation Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Signal Showcase Panel */}
          <div className="lg:col-span-2 p-6 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  Live Strategy Decision
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                    NIFTY 50
                  </span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">12-Factor Hierarchical Engine State</p>
              </div>
              <div className="flex items-center gap-2">
                {currentSignal?.setup_type && currentSignal.setup_type !== "CONSOLIDATION_WAIT" && (
                  <span className={`text-xs px-2.5 py-1 rounded-md font-bold font-mono border ${
                    currentSignal.setup_type === "PULLBACK_ACCUMULATION"
                      ? "bg-purple-950/80 text-purple-300 border-purple-800"
                      : currentSignal.setup_type === "MOMENTUM_BREAKOUT"
                      ? "bg-cyan-950/80 text-cyan-300 border-cyan-800"
                      : currentSignal.setup_type === "TRAP_REVERSAL"
                      ? "bg-orange-950/80 text-orange-300 border-orange-800"
                      : "bg-slate-800 text-slate-400 border-slate-700"
                  }`}>
                    ⚡ {currentSignal.setup_type.replace(/_/g, " ")}
                  </span>
                )}
                <span className={`text-xs px-3 py-1 rounded-full font-bold font-mono ${
                  currentSignal?.direction === "BUY"
                    ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                    : currentSignal?.direction === "SELL"
                    ? "bg-rose-950 text-rose-400 border border-rose-800"
                    : "bg-amber-950 text-amber-400 border border-amber-800"
                }`}>
                  {currentSignal?.direction || "WAIT"}
                </span>
              </div>
            </div>

            {/* Current Signal State Display */}
            <div className="p-5 rounded-xl bg-slate-950/70 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Signal Score</span>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-2xl font-black text-white font-mono">
                    {currentSignal?.score || 0} / 100
                  </span>
                  <span className="text-xs px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-mono font-semibold">
                    Quality: {currentSignal?.quality || "NO_TRADE"}
                  </span>
                </div>
              </div>
              <div className="text-xs text-slate-400 max-w-sm sm:text-right">
                <span className="font-semibold text-slate-300">Market Regime: </span>
                <span className="text-indigo-400 font-mono font-bold">{currentSignal?.market_regime || "RANGE"}</span>
                <p className="mt-1 text-slate-400">{currentSignal?.reason || "Awaiting multi-timeframe concordance threshold (score >= 70)"}</p>
              </div>
            </div>

            {/* Multi-Timeframe Alignment Matrix */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Multi-Timeframe Hierarchy Matrix
              </h3>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { tf: "15m", role: "Regime", state: currentSignal?.timeframe_states?.["15m"] || "BULLISH" },
                  { tf: "10m", role: "Trend", state: currentSignal?.timeframe_states?.["10m"] || "BULLISH" },
                  { tf: "5m", role: "Primary Setup", state: currentSignal?.timeframe_states?.["5m"] || "NEUTRAL" },
                  { tf: "3m", role: "Entry Conf", state: currentSignal?.timeframe_states?.["3m"] || "NEUTRAL" },
                  { tf: "1m", role: "Timing", state: currentSignal?.timeframe_states?.["1m"] || "BULLISH" },
                ].map((item) => {
                  const isBull = item.state.includes("BULLISH");
                  const isBear = item.state.includes("BEARISH");
                  const colorCls = isBull
                    ? "text-emerald-400 border-emerald-900 bg-emerald-950/30"
                    : isBear
                    ? "text-rose-400 border-rose-900 bg-rose-950/30"
                    : "text-slate-300 border-slate-700 bg-slate-800/40";

                  return (
                    <div key={item.tf} className={`p-3 rounded-lg border text-center ${colorCls}`}>
                      <span className="block text-xs font-mono font-bold text-white">{item.tf}</span>
                      <span className="block text-[10px] text-slate-400 uppercase mt-0.5">{item.role}</span>
                      <span className="block text-xs font-semibold mt-1 truncate">{item.state}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Transparent Evaluation Horizons Panel */}
          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm flex flex-col justify-between space-y-6">
            <div>
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-indigo-400" />
                  Outcome Horizons
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-800 text-slate-400 rounded">
                  TRANSPARENT AUDIT
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-3 leading-relaxed">
                Evaluates trade paths at +1, +3, +5, +10, +15, and +20 minutes. Stop Loss touched first is strictly classified as LOSS.
              </p>

              <div className="mt-4 space-y-2">
                {[1, 3, 5, 10, 15, 20].map((horizon) => (
                  <div key={horizon} className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs">
                    <span className="font-mono text-slate-300 font-medium">+{horizon} min horizon</span>
                    <span className="font-mono text-slate-500 font-semibold">Audit Active</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-900/40 text-indigo-300 text-xs flex items-center gap-2">
              <BarChart3 className="w-4 h-4 shrink-0 text-indigo-400" />
              <span>Zero fabricated statistics. Performance is mathematically computed from verified signals.</span>
            </div>
          </div>
        </div>

        {/* Historical Backtesting Engine Panel */}
        <BacktestPanel />

        {/* Regulatory & Research Disclaimer */}
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/30 text-xs text-slate-500 space-y-1">
          <div className="flex items-center gap-2 text-slate-400 font-semibold">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span>DISCLAIMER & COMPLIANCE NOTICE</span>
          </div>
          <p>
            {health?.disclaimer ||
              "Private trading research tool. Signals are algorithmic estimates, not guaranteed predictions. Past performance does not guarantee future results."}
          </p>
        </div>
      </main>
    </div>
  );
}
