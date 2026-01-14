import { GlassCard } from "./glass-card";

export function StatsCard({ label, value, sub, icon: Icon, alert, highlight, className }: any) {
    return (
        <GlassCard className="p-4 space-y-2 relative overflow-hidden group">
            <div className="absolute -right-4 -bottom-4 opacity-[0.03] text-white pointer-events-none group-hover:scale-110 transition-transform">
                <Icon size={80} />
            </div>
            <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white/40 uppercase tracking-wider">{label}</span>
                <Icon className={`w-4 h-4 ${alert ? "text-rose-400" : highlight ? "text-amber-400" : "text-emerald-400"}`} />
            </div>
            <div className={`text-2xl font-mono font-bold ${className || "text-white"}`}>{value}</div>
            <div className={`text-[10px] font-bold ${alert ? "text-white/40" : highlight ? "text-amber-400" : "text-emerald-400"}`}>
                {sub}
            </div>
        </GlassCard>
    );
}
