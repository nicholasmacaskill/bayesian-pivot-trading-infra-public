"use client";

import { ShieldAlert, Fingerprint, Lock, Search, Shield } from "lucide-react";

export function PropGuardianPanel({ audits = [] }: { audits?: any[] }) {
    const rules = [
        {
            category: "Structure",
            severity: "Low",
            title: "Hard Drawdown Limit",
            detail: "10% max drawdown based on starting balance. No relative drawdown logic detected."
        },
        {
            category: "Execution",
            severity: "Medium",
            title: "News Trading restriction",
            detail: "Restricted window: 2 minutes before/after high-impact news on majors."
        },
        {
            category: "Fees",
            severity: "Low",
            title: "Raw Spread + Commission",
            detail: "$7/lot round turn. Competitive for institutional scale."
        },
        {
            category: "Payout",
            severity: "Medium",
            title: "Bi-Weekly Payouts",
            detail: "Minimum 14 days between withdrawal requests. Manual audit on first payout."
        },
        {
            category: "Rules",
            severity: "Low",
            title: "No Consistency Rule",
            detail: "No lot-size consistency or hidden trade-count rules identified in v1.4 docs."
        }
    ];

    return (
        <div className="space-y-12">
            {/* Header */}
            <div className="flex justify-between items-center opacity-20">
                <div className="flex items-center gap-2">
                    <ShieldAlert className="w-3 h-3 text-white" />
                    <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">Rule Custodian Active</h2>
                </div>
                <div className="text-[10px] font-bold text-white uppercase tracking-widest">ACTIVE_FIRM: UPCOMS</div>
            </div>

            {/* Rules List */}
            <div className="grid gap-1">
                {rules.map((rule, idx) => (
                    <div key={idx} className="py-4 border-b border-white/[0.03] flex justify-between items-center group">
                        <div className="max-w-2xl">
                            <div className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] mb-1">{rule.category}</div>
                            <div className="text-sm font-bold text-white/60 mb-1 group-hover:text-white transition-colors">{rule.title}</div>
                            <div className="text-[10px] text-white/30 leading-normal">{rule.detail}</div>
                        </div>

                        <div className={`text-[10px] font-bold uppercase shrink-0 ml-4 ${rule.severity === 'High' ? 'text-rose-500' :
                                rule.severity === 'Medium' ? 'text-amber-500' :
                                    'text-white/20'
                            }`}>
                            {rule.severity} Sev
                        </div>
                    </div>
                ))}
            </div>

            {/* Shield Status */}
            <div className="p-4 bg-white/[0.02] border border-white/5 flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
                    <Shield className="w-4 h-4 text-emerald-500" />
                </div>
                <div>
                    <div className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest mb-1">Structural Integrity: VESTED</div>
                    <div className="text-[10px] text-white/40 leading-relaxed max-w-lg">
                        Prop Guardian has analyzed the active broker environment (Up-Down / Funding Pips).
                        Execution paths are clear. Dynamic slippage buffers adjusted for High-Impact windows.
                    </div>
                </div>
            </div>
        </div>
    );
}
