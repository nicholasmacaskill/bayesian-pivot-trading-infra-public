"use client";

import { motion } from "framer-motion";
import { Zap, Activity } from "lucide-react";

interface ShadowComparison {
    trade_id: string;
    symbol: string;
    timestamp: string;
    actual_pnl: number;
    shadow_pnl: number;
    regime: string;
    shadow_multiplier: number;
    actual?: {
        timestamp: string;
        outcome?: string;
    };
}

interface ShadowOptimizerProps {
    comparisons: ShadowComparison[];
}

export function ShadowOptimizer({ comparisons }: ShadowOptimizerProps) {
    const winRate = comparisons.length > 0
        ? (comparisons.filter(c => c.shadow_pnl > 0).length / comparisons.length) * 100
        : 0;
    const totalShadowPnL = comparisons.reduce((sum, c) => sum + c.shadow_pnl, 0);

    return (
        <div className="space-y-12">
            {/* Header: Zero Friction */}
            <div className="flex items-center gap-2 mb-4 opacity-20">
                <Zap className="w-3 h-3 text-white" />
                <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">Shadow Projection Layer</h2>
            </div>

            {/* Performance Ribbon */}
            <div className="flex flex-wrap gap-8 items-end border-b border-white/5 pb-8">
                <div className="space-y-1">
                    <div className="text-[10px] font-bold text-white/20 uppercase tracking-widest">Projection Win Rate</div>
                    <div className="text-3xl font-mono font-bold tracking-tighter text-white">
                        {winRate.toFixed(1)}% <span className="text-[10px] text-white/20 ml-2">VS {((comparisons.filter(c => c.actual?.outcome === 'WIN').length / comparisons.length) * 100 || 0).toFixed(1)}% ACTUAL</span>
                    </div>
                </div>

                <div className="space-y-1">
                    <div className="text-[10px] font-bold text-white/20 uppercase tracking-widest">Shadow PnL Delta</div>
                    <div className="text-3xl font-mono font-bold tracking-tighter text-emerald-500">
                        +${totalShadowPnL.toLocaleString()}
                    </div>
                </div>
            </div>

            {/* Delta Row Analysis */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 opacity-20">
                    <Activity className="w-3 h-3 text-white" />
                    <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">Alpha Delta Verifications</h3>
                </div>

                <div className="grid gap-px bg-white/5">
                    {comparisons.slice().reverse().map((comp, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="bg-black hover:bg-white/[0.02] flex flex-col md:flex-row justify-between py-2 px-1 transition-colors group"
                        >
                            <div className="flex items-center gap-6">
                                <div className="text-[10px] font-mono text-white/20 w-16">
                                    {comp.actual?.timestamp ? comp.actual.timestamp.split('T')[1].substring(0, 5) : "--:--"}
                                </div>
                                <div className="w-16">
                                    <div className="text-sm font-bold tracking-tighter text-white">{comp.symbol}</div>
                                </div>
                                <div className="hidden md:flex flex-col">
                                    <div className="text-[10px] font-mono text-purple-400/50 uppercase">SHADOW {comp.regime}</div>
                                    <div className="text-[9px] font-bold text-white/20">MULT: {comp.shadow_multiplier}x</div>
                                </div>
                            </div>

                            <div className="flex items-center gap-6 text-right">
                                <div className="space-y-0.5">
                                    <div className={`text-xs font-mono font-bold ${comp.shadow_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                                        SHADOW: ${comp.shadow_pnl.toFixed(2)}
                                    </div>
                                    <div className={`text-[10px] font-mono font-bold ${comp.actual_pnl >= 0 ? "text-white/40" : "text-rose-500/40"}`}>
                                        ACTUAL: ${comp.actual_pnl.toFixed(2)}
                                    </div>
                                </div>
                                <div className="w-12 text-center">
                                    <div className={`text-[10px] font-black ${comp.shadow_pnl > comp.actual_pnl ? "text-emerald-500" : "text-white/10"}`}>
                                        {((comp.shadow_pnl - (comp.actual_pnl || 0))).toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    );
}
