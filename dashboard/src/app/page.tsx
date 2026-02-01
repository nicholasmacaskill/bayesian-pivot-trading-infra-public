"use client";

import { fetchDashboardState, triggerBacktest } from "../lib/api";
import { StatsCard } from "../components/stats-card";
import { SignalFeed } from "../components/signal-feed";
import { JournalFeed } from "../components/journal-feed";
import { GlassCard } from "../components/glass-card";
import { ShadowOptimizer } from "../components/shadow-optimizer";

import { PropGuardianPanel } from "../components/prop-guardian";
import { BurnoutGuard } from "../components/burnout-guard";
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
  const [propAudits, setPropAudits] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [tradesToday, setTradesToday] = useState<number>(0);
  const [session, setSession] = useState({ name: "ASIA", sub: "MARKET CLOSED" });

  useEffect(() => {
    async function loadData() {
      try {
        const data = await fetchDashboardState();

        setSignals(data.scans || []);
        setEquity(data.equity || 0);
        setTradesToday(data.trades_today || 0);
        setJournal(data.journal_entries || []);
        setPropAudits(data.prop_audits || []);
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
    ? (signals.reduce((acc, s) => acc + (s.ai_score || 0), 0) / signals.length).toFixed(1)
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
    <main className={`min-h-screen p-4 md:p-8 space-y-12 bg-black text-white selection:bg-emerald-500/30`}>
      {/* Software as Glass Header: The Data Ribbon */}
      <div className="flex flex-wrap items-end justify-between gap-x-12 gap-y-8 border-b border-white/5 pb-8">
        <div className="space-y-1">
          <div className="text-[10px] font-mono font-bold text-white/20 uppercase tracking-[0.2em]">Neural Core // Operational</div>
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-black tracking-tighter text-white">SMC ALPHA</h1>
            <div className="h-1 w-1 rounded-full bg-emerald-500 animate-pulse" />
          </div>
        </div>

        {/* Primary Metrics Ribbon */}
        <div className="flex flex-wrap items-end gap-x-12 gap-y-4">
          {/* Equity & Growth Integrated */}
          <div className="space-y-1">
            <div className="text-[10px] font-bold text-white/20 uppercase tracking-widest">Digital Equity</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-mono font-bold tracking-tighter">
                {isZenMode ? "— — — —" : equityDisplay}
              </span>
              {!isZenMode && (
                <span className={`text-xs font-bold ${totalPnL >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {pnlSign}{totalReturnPercent}%
                </span>
              )}
            </div>
            <div className="w-32 h-[2px] bg-white/5 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progressPercent}%` }}
                className="h-full bg-emerald-500"
              />
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-[10px] font-bold text-white/20 uppercase tracking-widest">Market Bias</div>
            <div className={`text-2xl font-black tracking-tighter ${biasColor}`}>{marketBias}</div>
          </div>

          <div className="space-y-1">
            <div className="text-[10px] font-bold text-white/20 uppercase tracking-widest">Daily Drawdown</div>
            <div className={`text-2xl font-mono font-bold tracking-tighter ${parseFloat(drawdown) > 5 ? "text-rose-500" : "text-white/40"}`}>
              {drawdownDisplay}
            </div>
          </div>

          <div className="space-y-1 text-right">
            <div className="text-[10px] font-bold text-white/20 uppercase tracking-widest">Session</div>
            <div className="text-xl font-bold text-white tracking-tighter">
              {session.name} <span className="text-[10px] text-white/20 align-middle ml-1">{session.sub}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <BurnoutGuard />
          <button
            onClick={() => setIsZenMode(!isZenMode)}
            className={`text-[10px] font-bold px-3 py-1 rounded transition-colors ${isZenMode ? "bg-white text-black" : "bg-white/5 text-white/40 border border-white/10"}`}
          >
            {isZenMode ? "REVEAL PNL" : "ZEN MODE"}
          </button>
        </div>
      </div>

      {/* Glass Tab Navigation */}
      <div className="flex gap-8 border-b border-white/5 pb-1 overflow-x-auto selection:bg-transparent">
        <button
          onClick={() => setActiveTab("signals")}
          className={`pb-2 text-[10px] font-black uppercase tracking-[0.2em] transition-colors whitespace-nowrap ${activeTab === "signals"
            ? "text-white border-b border-white"
            : "text-white/10 hover:text-white/30"
            }`}
        >
          Scanner
        </button>
        <button
          onClick={() => setActiveTab("journal")}
          className={`pb-2 text-[10px] font-black uppercase tracking-[0.2em] transition-colors whitespace-nowrap ${activeTab === "journal"
            ? "text-white border-b border-white"
            : "text-white/10 hover:text-white/30"
            }`}
        >
          Journal
        </button>
        <button
          onClick={() => setActiveTab("shadow")}
          className={`pb-2 text-[10px] font-black uppercase tracking-[0.2em] transition-colors whitespace-nowrap ${activeTab === "shadow"
            ? "text-white border-b border-white"
            : "text-white/10 hover:text-white/30"
            }`}
        >
          Projection
        </button>
        <button
          onClick={() => setActiveTab("guardian")}
          className={`pb-2 text-[10px] font-black uppercase tracking-[0.2em] transition-colors whitespace-nowrap ${activeTab === "guardian"
            ? "text-white border-b border-white"
            : "text-white/10 hover:text-white/30"
            }`}
        >
          Guardian
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
              <PropGuardianPanel audits={propAudits} />
            </div>
          )}
        </>
      )}
    </main>
  );
}


