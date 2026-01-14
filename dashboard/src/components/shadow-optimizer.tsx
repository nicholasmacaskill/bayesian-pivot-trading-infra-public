"use client";

import { motion } from "framer-motion";
import { GlassCard } from "./glass-card";
import { TrendingUp, TrendingDown, Activity, Zap, Target, AlertTriangle } from "lucide-react";

interface ShadowComparison {
    trade_id: string;
    symbol: string;
    timestamp: string;
    actual_return: number;
    shadow_return: number;
    actual_risk: number;
    shadow_risk: number;
    regime: string;
    shadow_multiplier: number;
}

interface ShadowOptimizerProps {
    comparisons: ShadowComparison[];
}

export function ShadowOptimizer({ comparisons }: ShadowOptimizerProps) {
    // Calculate cumulative performance
    const actualCumulative = comparisons.reduce((sum, c) => sum + c.actual_return, 0);
    const shadowCumulative = comparisons.reduce((sum, c) => sum + c.shadow_return, 0);
    const alphaDelta = shadowCumulative - actualCumulative;
    const alphaDeltaPct = actualCumulative !== 0 ? (alphaDelta / Math.abs(actualCumulative)) * 100 : 0;

    // Win rate comparison
    const actualWins = comparisons.filter(c => c.actual_return > 0).length;
    const shadowWins = comparisons.filter(c => c.shadow_return > 0).length;
    const actualWinRate = comparisons.length > 0 ? (actualWins / comparisons.length) * 100 : 0;
    const shadowWinRate = comparisons.length > 0 ? (shadowWins / comparisons.length) * 100 : 0;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Zap className="w-6 h-6 text-purple-400" />
                        Shadow Optimizer Analysis
                    </h2>
                    <p className="text-sm text-white/40 font-mono uppercase tracking-widest mt-1">
                        Control (0.75%) vs Shadow (Dynamic Risk)
                    </p>
                </div>
                <div className="px-4 py-2 bg-purple-500/10 border border-purple-500/20 rounded-full">
                    <span className="text-xs font-bold text-purple-400 uppercase">Experimental</span>
                </div>
            </div>

            {/* Performance Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Cumulative Return Delta */}
                <GlassCard className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white/40 uppercase tracking-wider">Alpha Delta</span>
                        {alphaDelta >= 0 ? (
                            <TrendingUp className="w-4 h-4 text-emerald-400" />
                        ) : (
                            <TrendingDown className="w-4 h-4 text-rose-400" />
                        )}
                    </div>
                    <div className={`text-2xl font-mono font-bold ${alphaDelta >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {alphaDelta >= 0 ? "+" : ""}{alphaDelta.toFixed(2)}%
                    </div>
                    <div className="text-[10px] font-bold text-white/40">
                        Shadow {alphaDelta >= 0 ? "outperformed" : "underperformed"} by {Math.abs(alphaDeltaPct).toFixed(1)}%
                    </div>
                </GlassCard>

                {/* Win Rate Comparison */}
                <GlassCard className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white/40 uppercase tracking-wider">Win Rate</span>
                        <Target className="w-4 h-4 text-blue-400" />
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className="text-xl font-mono font-bold text-white">{actualWinRate.toFixed(0)}%</span>
                        <span className="text-sm text-white/40">→</span>
                        <span className={`text-xl font-mono font-bold ${shadowWinRate >= actualWinRate ? "text-emerald-400" : "text-rose-400"}`}>
                            {shadowWinRate.toFixed(0)}%
                        </span>
                    </div>
                    <div className="text-[10px] font-bold text-white/40">
                        Control vs Shadow
                    </div>
                </GlassCard>

                {/* Sample Size */}
                <GlassCard className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white/40 uppercase tracking-wider">Sample Size</span>
                        <Activity className="w-4 h-4 text-amber-400" />
                    </div>
                    <div className="text-2xl font-mono font-bold text-white">{comparisons.length}</div>
                    <div className="text-[10px] font-bold text-amber-400">
                        {comparisons.length < 10 ? "Need 10+ for significance" : "Statistically valid"}
                    </div>
                </GlassCard>
            </div>

            {/* Comparison Table */}
            <GlassCard className="p-6">
                <div className="space-y-4">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <Activity className="w-4 h-4 text-purple-400" />
                        Trade-by-Trade Comparison
                    </h3>

                    {comparisons.length === 0 ? (
                        <div className="text-center py-12 space-y-2">
                            <AlertTriangle className="w-12 h-12 text-white/20 mx-auto" />
                            <p className="text-white/40 text-sm">No trades yet. Shadow analysis will appear after first setup.</p>
                        </div>
                    ) : (
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                            {comparisons.map((comp, idx) => (
                                <motion.div
                                    key={comp.trade_id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: idx * 0.05 }}
                                    className="p-4 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
                                >
                                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-center">
                                        {/* Trade Info */}
                                        <div className="space-y-1">
                                            <div className="text-xs font-mono text-white/40">{comp.trade_id}</div>
                                            <div className="text-sm font-bold text-white">{comp.symbol}</div>
                                            <div className="text-[10px] text-white/40">{comp.regime}</div>
                                        </div>

                                        {/* Actual Performance */}
                                        <div className="space-y-1">
                                            <div className="text-[10px] text-white/40 uppercase">Control (0.75%)</div>
                                            <div className={`text-lg font-mono font-bold ${comp.actual_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                                {comp.actual_return >= 0 ? "+" : ""}{comp.actual_return.toFixed(2)}%
                                            </div>
                                        </div>

                                        {/* Shadow Performance */}
                                        <div className="space-y-1">
                                            <div className="text-[10px] text-purple-400 uppercase">Shadow ({comp.shadow_risk}%)</div>
                                            <div className={`text-lg font-mono font-bold ${comp.shadow_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                                {comp.shadow_return >= 0 ? "+" : ""}{comp.shadow_return.toFixed(2)}%
                                            </div>
                                        </div>

                                        {/* Delta */}
                                        <div className="space-y-1">
                                            <div className="text-[10px] text-white/40 uppercase">Delta</div>
                                            <div className={`text-lg font-mono font-bold ${(comp.shadow_return - comp.actual_return) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                                {(comp.shadow_return - comp.actual_return) >= 0 ? "+" : ""}
                                                {(comp.shadow_return - comp.actual_return).toFixed(2)}%
                                            </div>
                                        </div>

                                        {/* Multiplier Badge */}
                                        <div className="flex justify-end">
                                            <div className={`px-3 py-1 rounded-full text-xs font-bold ${comp.shadow_multiplier > 1.1
                                                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                                    : comp.shadow_multiplier < 0.9
                                                        ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                                                        : "bg-white/10 text-white/60 border border-white/20"
                                                }`}>
                                                {comp.shadow_multiplier.toFixed(2)}x
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    )}
                </div>
            </GlassCard>

            {/* Insights */}
            {comparisons.length >= 5 && (
                <GlassCard className="p-4 bg-purple-500/5 border-purple-500/20">
                    <div className="flex items-start gap-3">
                        <Zap className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                        <div className="space-y-1">
                            <h4 className="text-sm font-bold text-purple-400 uppercase">Shadow Insights</h4>
                            <p className="text-sm text-white/60">
                                {alphaDelta > 0
                                    ? `Shadow optimizer is outperforming control by ${alphaDeltaPct.toFixed(1)}%. Consider gradually adopting dynamic risk sizing.`
                                    : alphaDelta < 0
                                        ? `Control strategy is outperforming shadow by ${Math.abs(alphaDeltaPct).toFixed(1)}%. Current fixed risk approach is optimal.`
                                        : "Shadow and control are performing equally. Continue monitoring for regime changes."}
                            </p>
                        </div>
                    </div>
                </GlassCard>
            )}
        </div>
    );
}
