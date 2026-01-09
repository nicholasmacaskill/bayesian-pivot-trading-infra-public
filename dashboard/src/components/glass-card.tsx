import { cn } from "@/lib/utils";
import { motion, HTMLMotionProps } from "framer-motion";

interface GlassCardProps extends HTMLMotionProps<"div"> {
    children: React.ReactNode;
    className?: string;
    glow?: boolean;
}

export function GlassCard({ children, className, glow = false, ...props }: GlassCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className={cn(
                "rounded-xl border border-white/5 bg-white/5 p-6 backdrop-blur-md transition-all",
                glow && "hover:border-purple-500/30 hover:shadow-[0_0_30px_-10px_rgba(168,85,247,0.3)]",
                className
            )}
            {...props}
        >
            {children}
        </motion.div>
    );
}
