"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, X, CheckCircle2 } from "lucide-react";

export function BurnoutGuard() {
    const [isBurnout, setIsBurnout] = useState(false);
    const [burnoutDate, setBurnoutDate] = useState<string | null>(null);
    const [showReminder, setShowReminder] = useState(false);

    useEffect(() => {
        // Load burnout state from localStorage
        const burnoutState = localStorage.getItem("burnout_mode");
        const burnoutTimestamp = localStorage.getItem("burnout_timestamp");

        if (burnoutState === "true" && burnoutTimestamp) {
            setIsBurnout(true);
            setBurnoutDate(burnoutTimestamp);

            // Check if we should show daily reminder
            const lastReminder = localStorage.getItem("last_burnout_reminder");
            const today = new Date().toDateString();

            if (lastReminder !== today) {
                setShowReminder(true);
                localStorage.setItem("last_burnout_reminder", today);
            }
        }
    }, []);

    const activateBurnout = () => {
        const timestamp = new Date().toISOString();
        localStorage.setItem("burnout_mode", "true");
        localStorage.setItem("burnout_timestamp", timestamp);
        localStorage.setItem("last_burnout_reminder", new Date().toDateString());

        setIsBurnout(true);
        setBurnoutDate(timestamp);
        setShowReminder(true);
    };

    const deactivateBurnout = () => {
        localStorage.removeItem("burnout_mode");
        localStorage.removeItem("burnout_timestamp");
        localStorage.removeItem("last_burnout_reminder");

        setIsBurnout(false);
        setBurnoutDate(null);
        setShowReminder(false);
    };

    const getDaysSinceBurnout = () => {
        if (!burnoutDate) return 0;
        const then = new Date(burnoutDate);
        const now = new Date();
        const diffTime = Math.abs(now.getTime() - then.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays;
    };

    return (
        <>
            {/* Burnout Toggle Button */}
            <button
                onClick={isBurnout ? deactivateBurnout : activateBurnout}
                className={`text-[10px] font-bold px-3 py-1 rounded transition-all ${isBurnout
                        ? "bg-rose-500 text-white animate-pulse"
                        : "bg-white/5 text-white/40 border border-white/10 hover:bg-white/10"
                    }`}
            >
                {isBurnout ? "RECOVERY MODE" : "BURNOUT / TILT"}
            </button>

            {/* Daily Recovery Reminder Modal */}
            <AnimatePresence>
                {showReminder && isBurnout && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
                        onClick={() => setShowReminder(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-gradient-to-br from-rose-900/40 to-black border-2 border-rose-500/50 rounded-lg p-8 max-w-md mx-4 shadow-2xl"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="flex items-start gap-4">
                                <AlertTriangle className="w-8 h-8 text-rose-500 flex-shrink-0 mt-1" />
                                <div className="flex-1 space-y-4">
                                    <h2 className="text-xl font-black text-white">
                                        CORTISOL RECOVERY MODE
                                    </h2>
                                    <div className="space-y-2 text-sm text-white/70">
                                        <p>
                                            You entered recovery mode <strong>{getDaysSinceBurnout()} day(s)</strong> ago.
                                        </p>
                                        <p className="text-rose-400 font-bold">
                                            Do NOT trade until your cortisol levels have normalized.
                                        </p>
                                        <div className="bg-white/5 rounded p-3 mt-4 space-y-1">
                                            <div className="flex items-center gap-2">
                                                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                                <span className="text-xs">Rest & Sleep (8+ hours)</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                                <span className="text-xs">Physical Activity</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                                <span className="text-xs">Mindfulness & Relaxation</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                                <span className="text-xs">Social Connection</span>
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => setShowReminder(false)}
                                        className="w-full bg-rose-500 hover:bg-rose-600 text-white font-bold py-2 px-4 rounded mt-4 transition-colors"
                                    >
                                        I Understand
                                    </button>
                                </div>
                                <button
                                    onClick={() => setShowReminder(false)}
                                    className="text-white/40 hover:text-white transition-colors"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Persistent Warning Banner */}
            <AnimatePresence>
                {isBurnout && !showReminder && (
                    <motion.div
                        initial={{ y: -100, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: -100, opacity: 0 }}
                        className="fixed top-4 left-1/2 -translate-x-1/2 z-40 bg-rose-500/20 border border-rose-500/50 rounded-lg px-4 py-2 backdrop-blur-sm"
                    >
                        <div className="flex items-center gap-2 text-sm">
                            <AlertTriangle className="w-4 h-4 text-rose-500" />
                            <span className="text-rose-400 font-bold">
                                Recovery Mode Active • Day {getDaysSinceBurnout()}
                            </span>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
