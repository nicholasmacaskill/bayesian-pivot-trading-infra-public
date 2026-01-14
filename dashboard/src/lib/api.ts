const BASE_URL = "https://nicholasmacaskill--smc-alpha-scanner";

export async function fetchDashboardState() {
    const res = await fetch(`${BASE_URL}-get-dashboard-state.modal.run`);
    if (!res.ok) throw new Error("Failed to fetch dashboard state");
    return res.json();
}

export async function fetchBacktestReports() {
    const res = await fetch(`${BASE_URL}-get-backtest-reports.modal.run`);
    if (!res.ok) throw new Error("Failed to fetch backtest reports");
    return res.json();
}

export async function triggerBacktest(symbol = "BTC/USDT") {
    const res = await fetch(`${BASE_URL}-trigger-backfill-job.modal.run?symbol=${symbol}`);
    if (!res.ok) throw new Error("Failed to trigger backtest");
    return res.json();
}


export async function analyzeFirmRules(rules: string) {
    const res = await fetch(`${BASE_URL}-analyze-firm-rules.modal.run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules })
    });
    if (!res.ok) throw new Error("Failed to analyze rules");
    return res.json();
}
