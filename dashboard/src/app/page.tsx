"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { SignalFeed } from "@/components/signal-feed";
import { JournalFeed } from "@/components/journal-feed";
import {
  TrendingUp,
  ShieldAlert,
  Activity,
  Target,
  Clock,
  Zap,
  ArrowUpRight
} from "lucide-react";

// Mock Data
const MOCK_SIGNALS = [
  { id: "1", symbol: "BTC/USDT", timeframe: "15m", pattern: "Bullish BOS + FVG", aiScore: 9.2, timestamp: new Date().toISOString() },
  { id: "2", symbol: "ETH/USDT", timeframe: "15m", pattern: "Liquidity Sweep", aiScore: 7.8, timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString() },
];

const MOCK_JOURNAL = [
  {
    trade_id: "TL-882",
    symbol: "BTC/USDT",
    side: "BUY" as const,
    pnl: 1250.00,
    ai_grade: 9.2,
    mentor_feedback: "Clean execution. You waited for the displacement and entered on the 50% FVG retest. This is institutional discipline.",
    deviations: ["None"],
    timestamp: new Date().toISOString()
  },
  {
    trade_id: "TL-881",
    symbol: "ETH/USDT",
    side: "SELL" as const,
    pnl: -420.00,
    ai_grade: 4.5,
    mentor_feedback: "You chased the candle. There was no displacement here, just a minor liquidity grab. You traded into a premium instead of waiting for a discount.",
    deviations: ["FOMO Entry", "Counter-Bias"],
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString()
  },
];

export default function Dashboard() {
  const [isZenMode, setIsZenMode] = useState(true);

  return (
    <main className={`min-h-screen p-4 md:p-8 space-y-8 bg-black text-white transition-all duration-700 ${isZenMode ? "grayscale-[0.5]" : ""}`}>
      {/* Header & Status */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tighter text-white bg-clip-text text-transparent bg-gradient-to-r from-white to-white/40">
            SMC ALPHA // {isZenMode ? "ZEN MODE" : "GLASS JOURNAL"}
          </h1>
          <p className="text-white/40 text-sm font-mono flex items-center gap-2 mt-1 uppercase tracking-widest">
            <Activity className="w-3 h-3 text-emerald-400 animate-pulse" />
            {isZenMode ? "PROCESS VALIDATION ACTIVE // PNL MASKED" : "SYSTEM STATUS: OPERATIONAL // IP-SAFE SYNC ACTIVE"}
          </p>
        </div>

        <div className="flex items-center gap-6">
          {/* Zen Toggle */}
          <div className="flex items-center gap-3 px-4 py-2 bg-white/5 border border-white/10 rounded-full">
            <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Process First</span>
            <button
              onClick={() => setIsZenMode(!isZenMode)}
              className={`w-10 h-5 rounded-full transition-colors relative ${isZenMode ? "bg-blue-500" : "bg-white/10"}`}
            >
              <motion.div
                animate={{ x: isZenMode ? 22 : 2 }}
                className="w-4 h-4 bg-white rounded-full shadow-lg overflow-hidden"
              />
            </button>
          </div>

          <div className="flex gap-3">
            <div className="px-4 py-2 bg-white/5 border border-white/10 rounded-full flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <span className="text-xs font-bold text-white/80 uppercase">Risk: 0.5%</span>
            </div>
            <div className="px-4 py-2 bg-white/5 border border-white/10 rounded-full flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-white/80 uppercase">Limit: 2/2 Days</span>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          label={isZenMode ? "Discipline XP" : "Total Equity"}
          value={isZenMode ? "2,840 XP" : "$100,832.14"}
          sub={isZenMode ? "LEVEL 4 TRADER" : "+1.2% (Home IP Sync)"}
          icon={isZenMode ? Zap : TrendingUp}
        />
        <StatsCard label="Max Drawdown" value="0.42%" sub="HARD LIMIT: 6.0%" icon={ShieldAlert} alert />
        <StatsCard label="Avg AI Score" value="8.4" sub="SYMBOLS: 12 ACTIVE" icon={Target} />
        <StatsCard label="Session Time" value="NY PM" sub="KILLZONE ACTIVE" icon={Clock} highlight />
      </div>

      {/* Progress Tracker Section */}
      <GlassCard className={`p-6 border-blue-500/10 bg-blue-500/5 transition-all ${isZenMode ? "border-emerald-500/20 bg-emerald-500/5" : ""}`}>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="space-y-1">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Target className={`w-5 h-5 ${isZenMode ? "text-emerald-400" : "text-blue-400"}`} />
              {isZenMode ? "Weekly Discipline Goal" : "Monthly Growth Target"}
            </h3>
            <p className="text-sm text-white/40 font-mono uppercase tracking-widest">
              {isZenMode ? "Objective: 10 Straight A+ Grade Executions" : "Objective: 3.0% / Month for Prop Firm Stability"}
            </p>
          </div>

          <div className="w-full md:w-1/2 space-y-2">
            <div className="flex justify-between text-xs font-bold uppercase tracking-tight">
              <span className={isZenMode ? "text-emerald-400" : "text-blue-400"}>
                {isZenMode ? "Current Streak: 4" : "Progress: 1.2%"}
              </span>
              <span className="text-white/20">{isZenMode ? "Goal: 10" : "Target: 3.0%"}</span>
            </div>
            <div className="w-full bg-white/5 h-3 rounded-full overflow-hidden border border-white/5">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: isZenMode ? "40%" : "40%" }}
                className={`h-full bg-gradient-to-r ${isZenMode ? "from-emerald-600 to-emerald-400" : "from-blue-600 to-emerald-400"} rounded-full`}
              />
            </div>
          </div>

          <div className={`px-6 py-3 border rounded-xl ${isZenMode ? "bg-blue-500/10 border-blue-500/20" : "bg-emerald-500/10 border-emerald-500/20"}`}>
            <div className={`text-[10px] font-bold uppercase mb-1 ${isZenMode ? "text-blue-400" : "text-emerald-400"}`}>Status</div>
            <div className="text-sm font-bold text-white uppercase tracking-tighter italic">{isZenMode ? "Focused" : "On Track"}</div>
          </div>
        </div>
      </GlassCard>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Live Scan Feed */}
        <div className="lg:col-span-1">
          <SignalFeed signals={MOCK_SIGNALS} />
        </div>

        {/* Right Column: AI Journal */}
        <div className="lg:col-span-2">
          <JournalFeed entries={MOCK_JOURNAL} isZenMode={isZenMode} />
        </div>
      </div>
    </main>
  );
}

function StatsCard({ label, value, sub, icon: Icon, alert, highlight }: any) {
  return (
    <GlassCard className="p-4 space-y-2 relative overflow-hidden group">
      <div className="absolute -right-4 -bottom-4 opacity-[0.03] text-white pointer-events-none group-hover:scale-110 transition-transform">
        <Icon size={80} />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-white/40 uppercase tracking-wider">{label}</span>
        <Icon className={`w-4 h-4 ${alert ? "text-rose-400" : highlight ? "text-amber-400" : "text-emerald-400"}`} />
      </div>
      <div className="text-2xl font-mono font-bold text-white">{value}</div>
      <div className={`text-[10px] font-bold ${alert ? "text-white/40" : highlight ? "text-amber-400" : "text-emerald-400"}`}>
        {sub}
      </div>
    </GlassCard>
  );
}
