import { GlassCard } from "./glass-card";

export function StatsCard({ label, value, sub, icon: Icon, alert, highlight, className }: any) {
    return (
        <GlassCard className="p-4 space-y-2 relative overflow-hidden group min-h-[100px]">
            {/* Background Decorators: Spaced further to edges */}
            <div className="absolute -right-14 -bottom-14 opacity-[0.03] text-white pointer-events-none group-hover:scale-125 transition-transform blur-md">
                <Icon size={140} />
            </div>
            <div className="absolute -left-14 -top-14 opacity-[0.02] text-white pointer-events-none group-hover:scale-125 transition-transform blur-md">
                <Icon size={160} />
            </div>

            <div className="relative z-10 space-y-2">
                <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em]">{label}</span>
                    <Icon className={`w-3.5 h-3.5 ${alert ? "text-rose-400" : highlight ? "text-amber-400" : "text-emerald-400"} opacity-40`} />
                </div>
                <div className={`text-2xl font-mono font-bold tracking-tighter ${className || "text-white"}`}>{value}</div>
                <div className={`text-[10px] font-bold tracking-tight ${alert ? "text-rose-500/50" : highlight ? "text-amber-500/50" : "text-emerald-500/50"}`}>
                    {sub}
                </div>
            </div>
        </GlassCard>
    );
}
