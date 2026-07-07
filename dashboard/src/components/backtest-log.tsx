"use client";

import { useEffect, useState } from "react";
import { fetchBacktestReports, triggerBacktest } from "../lib/api";
import { GlassCard } from "./glass-card";
import { Beaker, Play, RefreshCw, ChevronDown, ChevronUp, TrendingUp, TrendingDown, Target } from "lucide-react";

export function BacktestLog() {
    const [reports, setReports] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isRunning, setIsRunning] = useState(false);
    const [expandedId, setExpandedId] = useState<number | null>(null);

    async function loadReports() {
        setIsLoading(true);
        try {
            const data = await fetchBacktestReports();
            if (data.reports) setReports(data.reports);
        } catch (e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        loadReports();
        const interval = setInterval(loadReports, 30000); // Poll every 30s
        return () => clearInterval(interval);
    }, []);

    async function handleRunBackfill() {
        setIsRunning(true);
        try {
            await triggerBacktest("BTC/USDT");
            alert("Simulation started! It may take 10-15 minutes. Data will appear here automatically.");
        } catch (e) {
            alert("Failed to start simulation: " + e);
        } finally {
            setIsRunning(false);
        }
    }

    const toggleExpand = (id: number) => {
        setExpandedId(expandedId === id ? null : id);
    };

    return (
        <div className="space-y-6">
            {/* Header / Actions */}
            <GlassCard className="p-6 flex flex-col md:flex-row justify-between items-center gap-4 bg-purple-500/5 border-purple-500/10">
                <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <Beaker className="w-5 h-5 text-purple-400" />
                        Backtest Lab
                    </h2>
                    <p className="text-sm text-white/40 font-mono">
                        30-Day Historical Simulation (Shadow Mode)
                    </p>
                </div>

                <button
                    onClick={handleRunBackfill}
                    disabled={isRunning}
                    className={`px-6 py-2 rounded-lg font-bold uppercase tracking-wider text-xs flex items-center gap-2 transition-all ${isRunning
                            ? "bg-white/5 text-white/20 cursor-not-allowed"
                            : "bg-purple-500 hover:bg-purple-400 text-white shadow-[0_0_20px_rgba(168,85,247,0.3)]"
                        }`}
                >
                    {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    {isRunning ? "Simulating..." : "Run 30-Day Sim"}
                </button>
            </GlassCard>

            {/* Reports List */}
            {isLoading && reports.length === 0 ? (
                <div className="text-center py-10 text-white/20 animate-pulse">Loading Simulation Data...</div>
            ) : reports.length === 0 ? (
                <div className="text-center py-20 bg-white/5 rounded-xl border border-white/5">
                    <Beaker className="w-12 h-12 text-white/10 mx-auto mb-4" />
                    <h3 className="text-lg font-bold text-white/50">No Simulations Found</h3>
                    <p className="text-sm text-white/30 max-w-md mx-auto mt-2">
                        Run a simulation to test the current algorithm parameters against the last 30 days of price action.
                    </p>
                </div>
            ) : (
                <div className="space-y-4">
                    {reports.map((report) => (
                        <GlassCard key={report.id} className="overflow-hidden transition-all hover:bg-white/5">
                            {/* Summary Header */}
                            <div
                                className="p-5 flex flex-col md:flex-row items-center justify-between cursor-pointer"
                                onClick={() => toggleExpand(report.id)}
                            >
                                <div className="flex items-center gap-4 mb-4 md:mb-0">
                                    <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center border border-purple-500/30">
                                        <span className="font-bold text-purple-400 text-xs">SIM</span>
                                    </div>
                                    <div>
                                        <div className="font-bold text-white text-sm">{report.symbol} {report.timeframe}</div>
                                        <div className="text-xs text-white/40 font-mono">{new Date(report.run_date).toLocaleString()}</div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-8">
                                    <div className="text-center">
                                        <div className="text-xs text-white/30 uppercase font-bold">Win Rate</div>
                                        <div className={`text-xl font-bold font-mono ${report.win_rate > 50 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                            {report.win_rate.toFixed(1)}%
                                        </div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-xs text-white/30 uppercase font-bold">Total PnL</div>
                                        <div className={`text-xl font-bold font-mono ${report.pnl > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                            {report.pnl > 0 ? "+" : ""}{report.pnl.toFixed(2)}R
                                        </div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-xs text-white/30 uppercase font-bold">Trades</div>
                                        <div className="text-xl font-bold font-mono text-white">
                                            {report.total_trades}
                                        </div>
                                    </div>

                                    {expandedId === report.id ? <ChevronUp className="w-5 h-5 text-white/20" /> : <ChevronDown className="w-5 h-5 text-white/20" />}
                                </div>
                            </div>

                            {/* Trade Log Details */}
                            {expandedId === report.id && (
                                <div className="bg-black/20 border-t border-white/5 p-4">
                                    <h4 className="text-xs font-bold text-white/40 uppercase mb-3">Trade Breakdown</h4>
                                    <div className="space-y-2 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
                                        {JSON.parse(report.trade_log || "[]").map((trade: any, i: number) => (
                                            <div key={i} className="flex items-center justify-between p-2 rounded bg-white/5 text-xs">
                                                <span className="font-mono text-white/50">{new Date(trade.timestamp).toLocaleDateString()}</span>
                                                <span className={`font-bold ${trade.direction === 'LONG' ? 'text-emerald-400' : 'text-rose-400'}`}>{trade.direction}</span>
                                                <span className="text-white/70">{trade.pattern}</span>
                                                <span className={`font-bold font-mono px-2 py-0.5 rounded ${trade.outcome === 'WIN' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                                                    {trade.pnl_r > 0 ? "+" : ""}{trade.pnl_r}R
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </GlassCard>
                    ))}
                </div>
            )}
        </div>
    );
}
