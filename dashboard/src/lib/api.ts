const BASE_URL = "https://nicholasmacaskill--smc-alpha-scanner";

const getUrl = (endpoint: string) => `${BASE_URL}-${endpoint}.modal.run`;

// Supabase Integration for Real-Time Data
import { supabase } from './supabase';

export async function fetchDashboardState() {
    // Fetch from Supabase for real-time journal/scans data
    try {
        const [journalRes, scansRes, auditsRes, syncRes] = await Promise.all([
            supabase.from('journal').select('*').order('timestamp', { ascending: false }).limit(50),
            supabase.from('scans').select('*').order('timestamp', { ascending: false }).limit(20),
            supabase.from('prop_guardian_audits').select('*').order('timestamp', { ascending: false }).limit(5),
            fetch(getUrl("get-dashboard-state")) // Still fetch equity/sync state from Modal
        ]);

        const syncData = syncRes.ok ? await syncRes.json() : {};

        return {
            journal_entries: journalRes.data || [],
            scans: scansRes.data || [],
            prop_audits: auditsRes.data || [],
            equity: syncData.equity || 0,
            trades_today: syncData.trades_today || 0,
            alpha_delta: syncData.alpha_delta || {}
        };
    } catch (e) {
        console.error("Failed to fetch from Supabase, falling back to Modal:", e);
        // Fallback to Modal API
        const res = await fetch(getUrl("get-dashboard-state"));
        if (!res.ok) throw new Error("Failed to fetch dashboard state");
        return res.json();
    }
}

export async function fetchBacktestReports() {
    const res = await fetch(getUrl("get-backtest-reports"));
    if (!res.ok) throw new Error("Failed to fetch backtest reports");
    return res.json();
}

export async function triggerBacktest(symbol = "BTC/USDT") {
    const res = await fetch(`${getUrl("trigger-backfill-job")}?symbol=${symbol}`);
    if (!res.ok) throw new Error("Failed to trigger backtest");
    return res.json();
}

export async function updateTradeNotes(trade_id: string, notes: string) {
    // Write directly to Supabase for instant persistence
    const { error } = await supabase
        .from('journal')
        .update({ notes })
        .eq('trade_id', trade_id);

    if (error) {
        console.error("Failed to update notes in Supabase:", error);
        throw new Error("Failed to update notes");
    }

    return { status: "success", message: "Notes updated" };
}

export async function auditPropFirms() {
    const res = await fetch(getUrl("audit-prop-firms"), {
        method: "POST"
    });
    if (!res.ok) throw new Error("Failed to audit prop firms");
    return res.json();
}
