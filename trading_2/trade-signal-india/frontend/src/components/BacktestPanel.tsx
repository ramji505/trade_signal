"use client";

import React, { useState } from "react";
import { Play, TrendingUp, BarChart, ShieldAlert, Award, Clock, ChevronDown, CheckCircle2, XCircle } from "lucide-react";

interface BacktestStats {
  symbol: string;
  timeframe: string;
  total_candles_analyzed: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  expectancy_points: number;
  max_drawdown_points: number;
  gross_profit_points: number;
  gross_loss_points: number;
  net_pnl_points: number;
  avg_winner_points: number;
  avg_loser_points: number;
  time_of_day_stats: {
    bucket: string;
    total_trades: number;
    winning_trades: number;
    win_rate_pct: number;
    net_pnl_points: number;
  }[];
  trade_log: {
    trade_id: number;
    time: string;
    direction: string;
    entry: number;
    stop_loss: number;
    target: number;
    score: number;
    result: string;
    pnl: number;
    bucket: string;
  }[];
}

import { getApiBaseUrl } from "@/lib/api";

export const BacktestPanel: React.FC = () => {
  const [data, setData] = useState<BacktestStats | null>(null);
  const [running, setRunning] = useState(false);
  const [candlesCount, setCandlesCount] = useState(250);
  const [scoreThreshold, setScoreThreshold] = useState(70);

  const runBacktest = async () => {
    try {
      setRunning(true);
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/backtest/run?candles_count=${candlesCount}&score_threshold=${scoreThreshold}`, {
        method: "POST"
      });
      if (!res.ok) throw new Error("Backtest failed");
      const report = await res.json();
      setData(report);
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-md p-6 space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <BarChart className="w-5 h-5 text-indigo-400" />
            Historical Strategy Backtester
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Walk-forward chronological simulation over historical NIFTY 50 candles (Zero Lookahead Bias)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 font-mono">Candles:</span>
            <select
              value={candlesCount}
              onChange={(e) => setCandlesCount(Number(e.target.value))}
              className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono text-xs"
            >
              <option value={100}>100 candles (~2 days)</option>
              <option value={250}>250 candles (~1 week)</option>
              <option value={500}>500 candles (~2 weeks)</option>
            </select>
          </div>

          <button
            onClick={runBacktest}
            disabled={running}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg transition disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${running ? "animate-spin" : ""}`} />
            {running ? "Simulating..." : "Run Backtest Simulation"}
          </button>
        </div>
      </div>

      {/* Metrics Cards */}
      {data ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {/* Win Rate */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[11px] font-semibold uppercase text-slate-400">Win Rate</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className={`text-2xl font-bold font-mono ${data.win_rate_pct >= 60 ? "text-emerald-400" : "text-amber-400"}`}>
                  {data.win_rate_pct}%
                </span>
                <span className="text-[10px] text-slate-500 font-mono">({data.winning_trades}/{data.total_trades})</span>
              </div>
            </div>

            {/* Profit Factor */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[11px] font-semibold uppercase text-slate-400">Profit Factor</span>
              <div className="mt-1">
                <span className="text-2xl font-bold font-mono text-sky-400">
                  {data.profit_factor}
                </span>
              </div>
            </div>

            {/* Expectancy */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[11px] font-semibold uppercase text-slate-400">Expectancy / Trade</span>
              <div className="mt-1">
                <span className="text-2xl font-bold font-mono text-indigo-400">
                  +{data.expectancy_points} pts
                </span>
              </div>
            </div>

            {/* Max Drawdown */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[11px] font-semibold uppercase text-slate-400">Max Drawdown</span>
              <div className="mt-1">
                <span className="text-2xl font-bold font-mono text-rose-400">
                  -{data.max_drawdown_points} pts
                </span>
              </div>
            </div>

            {/* Net P&L */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[11px] font-semibold uppercase text-slate-400">Net Points Gain</span>
              <div className="mt-1">
                <span className="text-2xl font-bold font-mono text-emerald-400">
                  +{data.net_pnl_points} pts
                </span>
              </div>
            </div>
          </div>

          {/* Time of Day Breakdown */}
          {data.time_of_day_stats.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-slate-400" />
                Performance By Time of Day
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {data.time_of_day_stats.map((tod) => (
                  <div key={tod.bucket} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center text-xs">
                    <div>
                      <span className="font-semibold text-slate-200 block">{tod.bucket}</span>
                      <span className="text-[10px] text-slate-500 font-mono">{tod.total_trades} trades executed</span>
                    </div>
                    <div className="text-right font-mono">
                      <span className={`font-bold block ${tod.win_rate_pct >= 65 ? "text-emerald-400" : "text-slate-300"}`}>
                        {tod.win_rate_pct}% Win
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">+{tod.net_pnl_points} pts</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-8 rounded-xl bg-slate-950/40 border border-dashed border-slate-800 text-center space-y-2">
          <p className="text-sm font-semibold text-slate-300">No Simulation Active</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Click &quot;Run Backtest Simulation&quot; to test the 12-factor strategy against historical NIFTY candles and verify win rates, drawdown, and expectancy.
          </p>
        </div>
      )}
    </div>
  );
};
