"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface AchievementCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  earned: boolean;
  tierClassName?: string;
  index?: number;
}

export function AchievementCard({
  icon: Icon,
  title,
  description,
  earned,
  tierClassName,
  index = 0,
}: AchievementCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: earned ? 1 : 0.45, scale: 1 }}
      transition={{ delay: index * 0.05, duration: 0.25 }}
      whileHover={earned ? { y: -2 } : undefined}
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border border-border p-4 text-center transition-all duration-300",
        earned
          ? "bg-card hover:border-border hover:shadow-flat hover:"
          : "bg-card/50 grayscale select-none",
      )}
    >
      <div
        className={cn(
          "rounded-full p-3 border shadow-flat transition-colors",
          earned
            ? (tierClassName ?? "border-success/20 bg-success/10 text-success")
            : "border-border bg-muted text-muted-foreground",
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <p className="text-xs font-bold text-foreground font-heading leading-tight">
          {title}
        </p>
        <p className="text-meta leading-relaxed text-muted-foreground font-sans">
          {description}
        </p>
      </div>
    </motion.div>
  );
}
