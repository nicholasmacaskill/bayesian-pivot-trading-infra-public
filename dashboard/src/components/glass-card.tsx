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
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className={cn(
                "transition-all",
                className
            )}
            {...props}
        >
            {children}
        </motion.div>
    );
}
