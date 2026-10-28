"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  iconClassName?: string;
  index?: number;
}

export function StatCard({
  label,
  value,
  icon: Icon,
  iconClassName,
  index = 0,
}: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.25 }}
      whileHover={{ y: -2 }}
      className="min-w-0"
    >
      <Card className="h-full border-border bg-card text-foreground shadow-flat transition-all duration-300 hover:border-border hover:bg-card/40">
        <CardContent className="flex items-start justify-between gap-3 p-4">
          <div className="space-y-1">
            <p className="text-meta font-medium text-muted-foreground">
              {label}
            </p>
            <p className="font-heading text-2xl font-semibold text-foreground tracking-tight">
              {value}
            </p>
          </div>
          {Icon && (
            <div
              className={cn(
                "rounded-lg border border-border bg-card p-2 text-muted-foreground group-hover:text-foreground transition-colors",
                iconClassName,
              )}
            >
              <Icon className="h-4 w-4" />
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
