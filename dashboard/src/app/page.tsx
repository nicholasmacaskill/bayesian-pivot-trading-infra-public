"use client";

import { fetchDashboardState, triggerBacktest } from "../lib/api";
import { StatsCard } from "../components/stats-card";
import { SignalFeed } from "../components/signal-feed";
import { JournalFeed } from "../components/journal-feed";
import { GlassCard } from "../components/glass-card";
import { ShadowOptimizer } from "../components/shadow-optimizer";

import { PropGuardianPanel } from "../components/prop-guardian";
import { useRef, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap,
  ShieldAlert,
  Activity,
  Target,
  Clock,
  ArrowUpRight,
  Beaker,
  TrendingUp,
  History
} from "lucide-react";

export default function Dashboard() {
  const [isZenMode, setIsZenMode] = useState(true);
  const [activeTab, setActiveTab] = useState<"signals" | "journal" | "shadow" | "backtest" | "guardian">("signals");
  const [activeStrategy, setActiveStrategy] = useState<"ALL" | "SMC" | "FLOW">("ALL");

  const [signals, setSignals] = useState<any[]>([]);
  const [journal, setJournal] = useState<any[]>([]);
  const [comparisons, setComparisons] = useState<any[]>([]);
  const [equity, setEquity] = useState<number>(0);
  const [tradesToday, setTradesToday] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [session, setSession] = useState({ name: "ASIA", sub: "MARKET CLOSED" });

  useEffect(() => {
    async function loadData() {
      try {
        const data = await fetchDashboardState();

        setSignals(data.scans || []);
        setEquity(data.equity || 0);
        setTradesToday(data.trades_today || 0);
        setJournal(data.journal_entries || []);
        if (data.alpha_delta) setComparisons(data.alpha_delta.comparisons || []);
      } catch (e) {
        console.error("Failed to load dashboard data:", e);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();

    // Session Clock
    function updateSession() {
      const h = new Date().getUTCHours();
      let s = { name: "ASIA", sub: "RANGE BUILDING" };
      if (h >= 7 && h < 12) s = { name: "LONDON", sub: "VOLATILITY EXPANSION" };
      else if (h >= 12 && h < 16) s = { name: "NY AM", sub: "TRUE OPEN" };
      else if (h >= 16 && h < 20) s = { name: "NY PM", sub: "CLOSE/RESET" };
      setSession(s);
    }
    updateSession();

    const interval = setInterval(() => { loadData(); updateSession(); }, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate Stats
  const avgScore = signals.length > 0
    ? (signals.reduce((acc, s) => acc + (s.aiScore || 0), 0) / signals.length).toFixed(1)
    : "0.0";

  const equityDisplay = equity > 0
    ? `$${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : "$0.00";

  // Calculate Daily PnL from Journal
  const todayDate = new Date().toISOString().split('T')[0];
  const todayEntries = journal.filter(j => j.timestamp && j.timestamp.startsWith(todayDate));
  const dailyPnL = todayEntries.reduce((acc, j) => acc + (j.pnl || 0), 0);

  // Total PnL (Assuming $100k Start for Prop Firms)
  const totalPnL = equity - 100000;
  const totalReturnPercent = ((totalPnL / 100000) * 100).toFixed(2);
  const pnlSign = totalPnL >= 0 ? "+" : "";

  const equitySub = isZenMode
    ? "LEVEL 4 TRADER"
    : `${pnlSign}${totalReturnPercent}% (Total Return)`;

  // Drawdown Calculation (Assuming 100k Peak or Current)
  const peakEquity = Math.max(100000, equity);
  const drawdown = ((peakEquity - equity) / peakEquity * 100).toFixed(2);
  const drawdownDisplay = `-${drawdown}%`;
  const progressPercent = Math.min(100, Math.max(0, (parseFloat(totalReturnPercent) / 3.0) * 100));

  // Market Bias (Derived from latest signal or default)
  const marketBias = signals.length > 0 ? signals[0].bias : "NEUTRAL";
  const biasColor = marketBias === "BULLISH" ? "text-emerald-400" : marketBias === "BEARISH" ? "text-rose-400" : "text-white";

  // Filter Signals by Strategy
  const filteredSignals = signals.filter(s => {
    if (activeStrategy === "ALL") return true;
    if (activeStrategy === "SMC" && (s.pattern.includes("Judas") || s.pattern.includes("Pullback"))) return true;
    if (activeStrategy === "FLOW" && s.pattern.includes("Order Block")) return true;
    return false;
  });

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
              <span className="text-xs font-bold text-white/80 uppercase">Risk: 0.65%</span>
            </div>
            <div className="px-4 py-2 bg-white/5 border border-white/10 rounded-full flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-white/80 uppercase">Limit: {tradesToday}/2 Daily</span>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatsCard
          label={isZenMode ? "Discipline XP" : "Total Equity"}
          value={isZenMode ? "--- XP" : equityDisplay}
          sub={equitySub}
          icon={isZenMode ? Zap : TrendingUp}
          alert={!isZenMode && dailyPnL < 0}
        />
        <StatsCard label="Market Bias" value={marketBias} sub="4H TREND (EMA 20/50)" icon={Target} className={biasColor} />
        <StatsCard label="Max Drawdown" value={drawdownDisplay} sub="HARD LIMIT: 6.0%" icon={ShieldAlert} alert={parseFloat(drawdown) > 5} />
        <StatsCard label="Avg AI Score" value={avgScore} sub={`SYMBOLS: ${signals.length} SCANS`} icon={Target} />
        <StatsCard label="Session Time" value={session.name} sub={session.sub} icon={Clock} highlight />
      </div>

      {/* Progress Tracker Section */}
      <GlassCard className={`p-6 border-blue-500/10 bg-blue-500/5 transition-all ${isZenMode ? "border-emerald-500/20 bg-emerald-500/5" : ""}`}>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="space-y-1">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Target className={`w-5 h-5 ${isZenMode ? "text-emerald-400" : "text-blue-400"}`} />
              {isZenMode ? "Monthly Discipline Goal" : "Monthly Growth Target"}
            </h3>
            <p className="text-sm text-white/40 font-mono uppercase tracking-widest">
              {isZenMode ? "Objective: 35 A+ Grade Executions / Month" : "Objective: 3.0% / Month for Prop Firm Stability"}
            </p>
          </div>

          <div className="w-full md:w-1/2 space-y-2">
            <div className="flex justify-between text-xs font-bold uppercase tracking-tight">
              <span className={isZenMode ? "text-emerald-400" : "text-blue-400"}>
                {isZenMode ? "Current Streak: 0" : `Progress: ${totalReturnPercent}%`}
              </span>
              <span className="text-white/20">{isZenMode ? "Goal: 35" : "Target: 3.0%"}</span>
            </div>
            <div className="w-full bg-white/5 h-3 rounded-full overflow-hidden border border-white/5">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: isZenMode ? "0%" : `${progressPercent}%` }}
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

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-white/10 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab("signals")}
          className={`px-4 py-2 rounded-t-lg text-sm font-bold uppercase tracking-wider transition-colors whitespace-nowrap ${activeTab === "signals"
            ? "bg-white/10 text-white border-b-2 border-emerald-400"
            : "text-white/40 hover:text-white/60"
            }`}
        >
          <Activity className="w-4 h-4 inline mr-2" />
          Live Signals
        </button>
        <button
          onClick={() => setActiveTab("journal")}
          className={`px-4 py-2 rounded-t-lg text-sm font-bold uppercase tracking-wider transition-colors whitespace-nowrap ${activeTab === "journal"
            ? "bg-white/10 text-white border-b-2 border-blue-400"
            : "text-white/40 hover:text-white/60"
            }`}
        >
          <Target className="w-4 h-4 inline mr-2" />
          AI Journal
        </button>
        <button
          onClick={() => setActiveTab("shadow")}
          className={`px-4 py-2 rounded-t-lg text-sm font-bold uppercase tracking-wider transition-colors whitespace-nowrap ${activeTab === "shadow"
            ? "bg-white/10 text-white border-b-2 border-purple-400"
            : "text-white/40 hover:text-white/60"
            }`}
        >
          <Zap className="w-4 h-4 inline mr-2" />
          Shadow Optimizer
        </button>

        <button
          onClick={() => setActiveTab("guardian")}
          className={`px-4 py-2 rounded-t-lg text-sm font-bold uppercase tracking-wider transition-colors whitespace-nowrap ${activeTab === "guardian"
            ? "bg-white/10 text-white border-b-2 border-red-500"
            : "text-white/40 hover:text-white/60"
            }`}
        >
          <ShieldAlert className="w-4 h-4 inline mr-2" />
          Prop Guardian
        </button>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <div className="text-center py-20 text-white/20 animate-pulse">Connecting to Neural Core...</div>
      ) : (
        <>
          {activeTab === "signals" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-1">
                {/* STRATEGY TOGGLE */}
                <div className="flex gap-2 mb-4">
                  {["ALL", "SMC", "FLOW"].map((strat) => (
                    <button
                      key={strat}
                      onClick={() => setActiveStrategy(strat as any)}
                      className={`px-3 py-1 rounded text-xs font-bold uppercase transition-colors ${activeStrategy === strat
                        ? "bg-white text-black"
                        : "bg-white/5 text-white/40 hover:bg-white/10"
                        }`}
                    >
                      {strat === "SMC" ? "SMC Alpha" : strat === "FLOW" ? "Order Flow" : "All Strategies"}
                    </button>
                  ))}
                </div>
                <SignalFeed signals={filteredSignals} />
              </div>
              <div className="lg:col-span-2">
                <JournalFeed entries={journal} isZenMode={isZenMode} />
              </div>
            </div>
          )}

          {activeTab === "journal" && (
            <div className="max-w-4xl mx-auto">
              <JournalFeed entries={journal} isZenMode={isZenMode} />
            </div>
          )}

          {activeTab === "shadow" && (
            <div className="max-w-6xl mx-auto">
              <ShadowOptimizer comparisons={comparisons} />
            </div>
          )}



          {activeTab === "guardian" && (
            <div className="max-w-4xl mx-auto">
              <PropGuardianPanel />
            </div>
          )}
        </>
      )}
    </main>
  );
}


