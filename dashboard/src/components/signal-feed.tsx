"use client";

import { motion } from "framer-motion";
import { GlassCard } from "./glass-card";
import { Zap } from "lucide-react";

interface Signal {
    id: string;
    symbol: string;
    timeframe: string;
    pattern: string;
    aiScore: number;
    timestamp: string;
}

export function SignalFeed({ signals }: { signals: Signal[] }) {
    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3 mb-2">
                <Zap className="w-5 h-5 text-emerald-400" />
                <h2 className="text-xl font-semibold text-white/90">Live Scanner</h2>
            </div>

            <div className="grid gap-4">
                {signals.map((signal, i) => (
                    <motion.div
                        key={signal.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                    >
                        <GlassCard className="p-4 border-white/5 hover:border-white/10 transition-colors relative group">
                            <div className="absolute top-0 right-0 p-4 opacity-10 text-4xl font-black text-white/5 z-0 transition-colors group-hover:text-emerald-500/10">
                                {signal.symbol.split('/')[0]}
                            </div>

                            <div className="relative z-10">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="text-[10px] font-mono text-white/40 uppercase tracking-widest">
                                        {signal.timeframe} • {new Date(signal.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    <div className={`text-xs px-2 py-0.5 rounded font-bold border ${signal.aiScore >= 8.5 ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                                        }`}>
                                        SCORE: {signal.aiScore}
                                    </div>
                                </div>

                                <h3 className="text-lg font-bold text-white mb-1">{signal.pattern}</h3>
                                <div className="text-2xl font-mono font-bold text-white/90">{signal.symbol}</div>
                            </div>
                        </GlassCard>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}
