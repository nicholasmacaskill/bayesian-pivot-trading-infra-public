"use client";

import { motion } from "framer-motion";
import { GlassCard } from "./glass-card";
import { BookText, ArrowUpRight, AlertCircle, CheckCircle2 } from "lucide-react";

export interface JournalEntry {
    trade_id: string;
    symbol: string;
    side: "BUY" | "SELL";
    pnl: number;
    ai_grade: number;
    mentor_feedback: string;
    deviations: string[];
    timestamp: string;
}

export function JournalFeed({ entries, isZenMode }: { entries: JournalEntry[], isZenMode?: boolean }) {
    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <BookText className="w-5 h-5 text-blue-400" />
                    {isZenMode ? "Institutional Journal // Zen" : "Institutional Trade Journal"}
                </h2>
                <div className="text-[10px] font-mono text-white/20 uppercase tracking-widest">
                    {entries.length} Sessions Logged
                </div>
            </div>

            <div className="space-y-4">
                {entries.map((trade) => (
                    <motion.div
                        key={trade.trade_id}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                    >
                        <GlassCard className={`p-4 rounded-xl border border-white/5 bg-white/[0.02] flex flex-col md:flex-row gap-4 justify-between items-start md:items-center transition-all hover:bg-white/[0.04] ${isZenMode ? "hover:border-emerald-500/20" : "hover:border-blue-500/20"}`}>
                            <div className="flex gap-4 items-center">
                                <div className={`p-3 rounded-lg ${trade.side === "BUY" ? "bg-emerald-500/10" : "bg-rose-500/10"}`}>
                                    <ArrowUpRight className={`w-5 h-5 ${trade.side === "BUY" ? "text-emerald-400" : "text-rose-400"} ${trade.side === "SELL" ? "rotate-90" : ""}`} />
                                </div>
                                <div>
                                    <div className="text-sm font-bold text-white">{trade.symbol}</div>
                                    <div className="text-[10px] font-mono text-white/40 uppercase">
                                        {new Date(trade.timestamp).toLocaleDateString()} // {trade.side}
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 px-4">
                                <div className="text-xs text-white/60 italic line-clamp-2">
                                    "{trade.mentor_feedback}"
                                </div>
                                <div className="flex gap-2 mt-2">
                                    {trade.deviations.map((d, i) => (
                                        <span key={i} className={`px-2 py-1 rounded text-[9px] font-bold uppercase tracking-tighter flex items-center gap-1 ${d === "None" ? "bg-emerald-500/10 text-emerald-400/50" : "bg-rose-500/10 text-rose-400"}`}>
                                            {d !== "None" && <AlertCircle className="w-2.5 h-2.5" />}
                                            {d}
                                        </span>
                                    ))}
                                    {trade.ai_grade >= 9 && (
                                        <span className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 text-[9px] font-bold uppercase tracking-tighter flex items-center gap-1">
                                            <CheckCircle2 className="w-2.5 h-2.5" />
                                            Elite
                                        </span>
                                    )}
                                </div>
                            </div>

                            <div className="flex items-center gap-6 min-w-fit border-l border-white/5 pl-6">
                                <div className="text-right">
                                    <div className={`text-sm font-bold ${isZenMode ? "text-white/20 select-none blur-[2px]" : (trade.pnl >= 0 ? "text-emerald-400" : "text-rose-400")}`}>
                                        {isZenMode ? "$0,000.00" : (trade.pnl >= 0 ? `+${trade.pnl.toFixed(2)}` : trade.pnl.toFixed(2))}
                                    </div>
                                    <div className="text-[10px] font-mono text-white/20 uppercase tracking-tighter">Outcome</div>
                                </div>

                                <div className="text-center px-4 border-l border-white/10">
                                    <div className={`text-lg font-black ${trade.ai_grade >= 8 ? "text-emerald-400" : trade.ai_grade >= 5 ? "text-yellow-400" : "text-rose-400"}`}>
                                        {trade.ai_grade.toFixed(1)}
                                    </div>
                                    <div className="text-[9px] font-bold text-white/40 uppercase tracking-widest">Grade</div>
                                </div>
                            </div>
                        </GlassCard>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}
