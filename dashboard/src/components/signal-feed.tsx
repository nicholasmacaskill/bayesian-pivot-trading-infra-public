"use client";

import { motion } from "framer-motion";
import { GlassCard } from "./glass-card";
import { Zap } from "lucide-react";

interface Signal {
    id: string;
    symbol: string;
    timeframe: string;
    pattern: string;
    ai_score: number;
    timestamp: string;
    shadow_regime?: string;
    shadow_multiplier?: number;
    action?: string;
}

export function SignalFeed({ signals }: { signals: Signal[] }) {
    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4 opacity-20">
                <Zap className="w-3 h-3 text-white" />
                <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">Live Scanner</h2>
            </div>

            <div className="grid gap-1">
                {signals.map((signal, i) => {
                    const isLowScore = signal.ai_score < 7;
                    return (
                        <motion.div
                            key={signal.id}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: isLowScore ? 0.3 : 1 }}
                            className="group flex flex-col md:flex-row md:items-center justify-between py-2 border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                        >
                            <div className="flex items-center gap-4">
                                <div className="text-[10px] font-mono text-white/20 w-12">{signal.timeframe}</div>
                                <div className="space-y-0.5">
                                    <div className="text-sm font-bold tracking-tight text-white group-hover:text-emerald-500 transition-colors">
                                        {signal.symbol}
                                    </div>
                                    <div className="text-[10px] font-mono text-white/30 uppercase">{signal.pattern}</div>
                                </div>
                            </div>

                            <div className="flex items-center gap-4 text-right">
                                {signal.shadow_regime && signal.shadow_regime !== 'N/A' && (
                                    <span className="text-[9px] font-bold text-blue-400/50 uppercase tracking-tighter">
                                        {signal.shadow_regime}
                                    </span>
                                )}
                                {signal.shadow_multiplier && signal.shadow_multiplier !== 1.0 && (
                                    <span className={`text-[10px] font-mono font-bold ${signal.shadow_multiplier > 1.0 ? "text-emerald-500/50" : "text-rose-500/50"}`}>
                                        {signal.shadow_multiplier.toFixed(2)}x
                                    </span>
                                )}
                                <div className={`text-xs font-mono font-bold w-16 ${signal.ai_score >= 8.5 ? "text-emerald-500" : "text-white/20"}`}>
                                    {signal.ai_score.toFixed(1)}
                                </div>
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </div>
    );
}
