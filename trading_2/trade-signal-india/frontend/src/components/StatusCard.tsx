"use client";

import React from "react";
import { CheckCircle2, ShieldCheck, Clock, Layers, Zap } from "lucide-react";
import { SystemHealth } from "@/types";

interface StatusCardProps {
  health: SystemHealth | null;
  loading: boolean;
  error: string | null;
}

export const StatusCard: React.FC<StatusCardProps> = ({ health, loading, error }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* System Status */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 backdrop-blur-sm shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">System Status</span>
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="mt-3">
          {loading ? (
            <div className="h-7 w-24 bg-slate-800 animate-pulse rounded"></div>
          ) : error ? (
            <span className="text-xl font-bold text-rose-400">OFFLINE</span>
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white tracking-tight">ONLINE</span>
              <span className="text-xs text-emerald-400 font-mono">v{health?.version || "0.1.0"}</span>
            </div>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-1">Backend FastAPI service active & responding</p>
      </div>

      {/* Execution Architecture */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 backdrop-blur-sm shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Execution Safety</span>
          <ShieldCheck className="w-4 h-4 text-sky-400" />
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold text-sky-400 tracking-tight">SIGNAL ONLY</span>
        </div>
        <p className="text-xs text-slate-500 mt-1">Order execution disabled (zero broker risk)</p>
      </div>

      {/* Strategy Engine & MTF */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 backdrop-blur-sm shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Multi-Timeframe Engine</span>
          <Layers className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="mt-3">
          <div className="flex gap-1.5">
            {["1m", "3m", "5m", "10m", "15m"].map((tf) => (
              <span
                key={tf}
                className={`text-xs px-2 py-0.5 rounded font-mono font-semibold ${
                  tf === "5m"
                    ? "bg-indigo-600 text-white border border-indigo-400 shadow-sm"
                    : "bg-slate-800 text-slate-300 border border-slate-700"
                }`}
              >
                {tf}
              </span>
            ))}
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-1">Primary setup timeframe: 5m</p>
      </div>
    </div>
  );
};
