import { motion, AnimatePresence } from "framer-motion";
import { GlassCard } from "./glass-card";
import { useRef, useState } from "react";
import { BookText, ArrowUpRight, AlertCircle, CheckCircle2, MessageSquare, Save, X } from "lucide-react";
import { updateTradeNotes } from "../lib/api";

export interface JournalEntry {
    trade_id: string;
    symbol: string;
    side: "BUY" | "SELL";
    pnl: number;
    ai_grade: number;
    mentor_feedback: string;
    deviations: string[] | null;
    timestamp: string;
    status?: string;
    notes?: string;
    strategy?: string;
}

export function JournalFeed({ entries, isZenMode }: { entries: JournalEntry[], isZenMode?: boolean }) {
    const [editingId, setEditingId] = useState<string | null>(null);
    const [tempNotes, setTempNotes] = useState("");
    const [isSaving, setIsSaving] = useState(false);

    const handleSaveNote = async (tradeId: string) => {
        setIsSaving(true);
        try {
            await updateTradeNotes(tradeId, tempNotes);
            const trade = entries.find(e => e.trade_id === tradeId);
            if (trade) trade.notes = tempNotes;
            setEditingId(null);
        } catch (e) {
            console.error("Failed to save note:", e);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4 opacity-20">
                <BookText className="w-3 h-3 text-white" />
                <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">Institutional Journal</h2>
            </div>

            <div className="grid gap-px bg-white/5">
                {entries.map((trade, i) => (
                    <motion.div
                        key={trade.trade_id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="group bg-black hover:bg-white/[0.02] transition-colors"
                    >
                        <div className="flex flex-col md:flex-row md:items-center justify-between py-2 px-1">
                            <div className="flex items-center gap-6">
                                <div className="text-[10px] font-mono text-white/20 w-16">
                                    {trade.timestamp ? (
                                        (() => {
                                            const ts = Number(trade.timestamp);
                                            const date = !isNaN(ts) ? new Date(ts) : new Date(trade.timestamp);
                                            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                                        })()
                                    ) : "--:--"}
                                </div>

                                <div className="w-16">
                                    <div className={`text-sm font-bold tracking-tighter ${trade.side === "BUY" ? "text-emerald-500" : "text-rose-500"}`}>
                                        {trade.symbol}
                                    </div>
                                </div>

                                <div className="hidden md:flex flex-col">
                                    <div className="flex items-center gap-1.5">
                                        <div className="text-[9px] font-bold text-white/30 uppercase tracking-widest">{trade.status === 'OPEN' ? "LIVE" : (trade.side || "MARKET")}</div>
                                        <div className={`px-1 py-0.5 rounded-[2px] text-[7px] font-black uppercase tracking-[0.1em] ${trade.strategy === 'ROGUE' ? 'bg-rose-500/20 text-rose-500 border border-rose-500/30' : 'bg-emerald-500/10 text-emerald-500/50 border border-emerald-500/10'}`}>
                                            {trade.strategy || 'SMC ALPHA'}
                                        </div>
                                    </div>
                                    <div className="text-[10px] font-mono text-blue-400/50">GRADE {Number(trade.ai_grade || 0).toFixed(1)}</div>
                                </div>

                                <div className="hidden lg:block text-[10px] font-mono text-white/40 max-w-[250px] truncate">
                                    {trade.notes || trade.mentor_feedback || <span className="opacity-10 italic">Awaiting analysis...</span>}
                                </div>
                            </div>

                            <div className="flex items-center gap-6">
                                <div className="text-right">
                                    <div className={`text-sm font-mono font-bold ${(isZenMode && trade.status !== 'OPEN') ? "text-white/10 blur-[2px]" : (trade.pnl >= 0 ? "text-emerald-500" : "text-rose-500")}`}>
                                        {(isZenMode && trade.status !== 'OPEN') ? "WIN" : `${trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}`}
                                    </div>
                                    <div className="text-[9px] font-bold text-white/20 uppercase tracking-tighter">
                                        {trade.status === 'OPEN' ? "FLOATING" : "PnL"}
                                    </div>
                                </div>

                                <button
                                    onClick={() => {
                                        setEditingId(editingId === trade.trade_id ? null : trade.trade_id);
                                        setTempNotes(trade.notes || "");
                                    }}
                                    className="p-2 text-white/20 hover:text-white transition-colors"
                                >
                                    <MessageSquare className={`w-3 h-3 ${trade.notes ? "text-blue-500" : ""}`} />
                                </button>
                            </div>
                        </div>

                        <AnimatePresence>
                            {editingId === trade.trade_id && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    className="overflow-hidden bg-white/[0.01] px-4"
                                >
                                    <div className="py-4 space-y-3">
                                        <textarea
                                            value={tempNotes}
                                            onChange={(e) => setTempNotes(e.target.value)}
                                            placeholder="Enter trade rationale..."
                                            className="w-full bg-transparent border-none text-sm text-white/70 placeholder:text-white/10 focus:ring-0 min-h-[80px] resize-none p-0"
                                            autoFocus
                                        />
                                        <div className="flex justify-end gap-3 pb-2">
                                            <button
                                                onClick={() => setEditingId(null)}
                                                className="text-[10px] font-bold text-white/20 hover:text-white uppercase tracking-widest"
                                            >
                                                Discard
                                            </button>
                                            <button
                                                onClick={() => handleSaveNote(trade.trade_id)}
                                                disabled={isSaving}
                                                className="text-[10px] font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest flex items-center gap-1"
                                            >
                                                {isSaving ? "Syncing..." : "Commit Notes"}
                                            </button>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}
