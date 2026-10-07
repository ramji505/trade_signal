"use client";

import React from "react";
import { Activity, ShieldAlert, Cpu } from "lucide-react";

interface HeaderProps {
  isLive: boolean;
  marketStatus: string;
}

export const Header: React.FC<HeaderProps> = ({ isLive, marketStatus }) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              TradeSignal India
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono font-medium">
                NIFTY 50
              </span>
            </h1>
            <p className="text-xs text-slate-400">Intraday Quantitative Signal Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Mode Badge */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Cpu className="w-3.5 h-3.5" />
            <span>MOCK DATA (DEV)</span>
          </div>

          {/* Market Status */}
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Market: {marketStatus}</span>
          </div>
        </div>
      </div>
    </header>
  );
};
