import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, AlertTriangle, CheckCircle, Search, ChevronRight, FileText } from "lucide-react";
import { GlassCard } from "./glass-card";

interface GuardianReport {
    risk_score: number;
    firm_name: string;
    verdict: string;
    recommendation: string;
    traps: Array<{
        category: string;
        severity: "High" | "Medium" | "Low";
        title: string;
        description: string;
    }>;
}

const PROP_FIRMS = [
    { name: "Upcomers (Active)", url: "https://upcomers.com/faq" },
    { name: "FTMO", url: "https://ftmo.com/en/faq/" },
    { name: "FundedNext", url: "https://fundednext.com/faq" },
    { name: "TopStep", url: "https://intercom.help/topstep-llc/en/" },
    { name: "Blue Guardian", url: "https://blueguardian.com/faq" },
    { name: "Alpha Capital", url: "https://alphacapitalgroup.uk/faq/" },
    { name: "Funding Pips", url: "https://fundingpips.com/faq" },
    { name: "E8 Markets", url: "https://e8markets.com/faq" },
    { name: "The5ers", url: "https://the5ers.com/faqs/" },
    { name: "Maven Trading", url: "https://maventrading.com/faq" }
];

export function PropGuardianPanel() {
    const [rules, setRules] = useState("");
    const [loading, setLoading] = useState(false);
    const [report, setReport] = useState<GuardianReport | null>(null);

    const analyze = async () => {
        if (!rules) return;
        setLoading(true);
        try {
            const { analyzeFirmRules } = require("../lib/api");
            const res = await analyzeFirmRules(rules);
            if (res.report) setReport(res.report);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <GlassCard className="p-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
                <Shield className="w-24 h-24 text-emerald-400" />
            </div>

            <div className="flex items-center gap-3 mb-6 relative z-10">
                <div className="p-2 bg-emerald-500/20 rounded-lg">
                    <Shield className="w-5 h-5 text-emerald-400" />
                </div>
                <h2 className="text-lg font-bold text-white">Prop Firm Guardian</h2>
            </div>

            {!report ? (
                <div className="space-y-4 relative z-10">
                    <p className="text-sm text-gray-400">
                        Select a known firm or paste a URL/Rules text to scan for traps.
                    </p>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
                        {PROP_FIRMS.map((firm) => (
                            <button
                                key={firm.name}
                                onClick={() => setRules(firm.url)}
                                className="px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-left transition-colors truncate"
                            >
                                {firm.name}
                            </button>
                        ))}
                    </div>

                    <textarea
                        className="w-full h-32 bg-black/40 border border-white/10 rounded-lg p-3 text-sm text-gray-200 focus:border-emerald-500/50 outline-none resize-none font-mono"
                        placeholder="https://firm.com/rules OR Paste Text..."
                        value={rules}
                        onChange={(e) => setRules(e.target.value)}
                    />
                    <button
                        onClick={analyze}
                        disabled={loading || !rules}
                        className="w-full py-3 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-50 text-black font-bold rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
                    >
                        {loading ? <Search className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                        {loading ? "Scanning Adversarial Rules..." : "SCAN FOR TRAPS"}
                    </button>
                </div>
            ) : (
                <div className="space-y-6 relative z-10">
                    <div className="flex items-start justify-between">
                        <div>
                            <h3 className="text-xl font-bold text-white">{report.firm_name}</h3>
                            <p className="text-xs text-gray-400 uppercase tracking-wider">Risk Assessment</p>
                        </div>
                        <div className={`px-3 py-1 rounded-full text-xs font-bold border ${report.risk_score > 7 ? "bg-red-500/20 border-red-500/50 text-red-400" :
                            report.risk_score > 4 ? "bg-amber-500/20 border-amber-500/50 text-amber-400" :
                                "bg-emerald-500/20 border-emerald-500/50 text-emerald-400"
                            }`}>
                            Score: {report.risk_score}/10
                        </div>
                    </div>

                    <p className="text-sm text-gray-300 italic">"{report.verdict}"</p>

                    <div className="space-y-3">
                        {(report.traps || []).map((trap, i) => (
                            <div key={i} className="bg-white/5 border border-white/10 rounded-lg p-3">
                                <div className="flex items-center justify-between mb-1">
                                    <span className={`text-xs font-bold ${trap.severity === "High" ? "text-red-400" : "text-amber-400"
                                        }`}>{trap.title}</span>
                                    <span className="text-[10px] text-gray-500 uppercase">{trap.category}</span>
                                </div>
                                <p className="text-xs text-gray-400">{trap.description}</p>
                            </div>
                        ))}
                    </div>

                    <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs text-blue-300">
                        <strong className="block mb-1 text-blue-200">Recommendation:</strong>
                        {report.recommendation}
                    </div>

                    <button
                        onClick={() => setReport(null)}
                        className="text-xs text-gray-500 hover:text-white underline w-full text-center"
                    >
                        Scan Another
                    </button>
                </div>
            )}
        </GlassCard>
    );
}
