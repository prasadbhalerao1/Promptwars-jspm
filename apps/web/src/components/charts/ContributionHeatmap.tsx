"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";

interface ContributionHeatmapProps {
  /** date (YYYY-MM-DD) -> contribution/submission count */
  days: { date: string; count: number }[];
}

/** Five intensity steps built from one hue, so the ramp reads as a single scale
 * rather than five unrelated colours. Level 0 is a neutral "no activity" cell. */
const LEVEL_CLASSNAMES = [
  "bg-muted/80 dark:bg-zinc-800",
  "bg-[#9be9a8] dark:bg-[#0e4429]",
  "bg-[#40c463] dark:bg-[#006d32]",
  "bg-[#30a14e] dark:bg-[#26a641]",
  "bg-[#216e39] dark:bg-[#39d353]",
];

function levelFor(count: number, max: number): number {
  if (count <= 0) return 0;
  if (max <= 0) return 1;
  const ratio = count / max;
  if (ratio > 0.75) return 4;
  if (ratio > 0.5) return 3;
  if (ratio > 0.25) return 2;
  return 1;
}

/** GitHub/LeetCode-style contribution heatmap — 7-row week grid, most recent ~53 weeks. */
export function ContributionHeatmap({ days }: ContributionHeatmapProps) {
  const { weeks, max, monthLabels } = useMemo(() => {
    const byDate = new Map(days.map((d) => [d.date, d.count]));
    const sorted = [...byDate.keys()].sort();
    const today = new Date();
    const start = new Date(today);
    start.setDate(start.getDate() - 370);
    // Align the grid to start on a Sunday so weeks stack into clean columns.
    start.setDate(start.getDate() - start.getDay());

    const allDays: { date: string; count: number }[] = [];
    const cursor = new Date(start);
    while (cursor <= today) {
      const iso = cursor.toISOString().slice(0, 10);
      allDays.push({ date: iso, count: byDate.get(iso) ?? 0 });
      cursor.setDate(cursor.getDate() + 1);
    }

    const weeksArr: { date: string; count: number }[][] = [];
    for (let i = 0; i < allDays.length; i += 7) {
      weeksArr.push(allDays.slice(i, i + 7));
    }

    const maxCount = Math.max(1, ...sorted.map((d) => byDate.get(d) ?? 0));

    const labels: { weekIndex: number; label: string }[] = [];
    let lastMonth = -1;
    weeksArr.forEach((week, i) => {
      const firstOfMonth = week.find((d) => Number(d.date.slice(8, 10)) <= 7);
      if (firstOfMonth) {
        const month = new Date(firstOfMonth.date).getMonth();
        if (month !== lastMonth) {
          labels.push({
            weekIndex: i,
            label: new Date(firstOfMonth.date).toLocaleString("default", {
              month: "short",
            }),
          });
          lastMonth = month;
        }
      }
    });

    return { weeks: weeksArr, max: maxCount, monthLabels: labels };
  }, [days]);

  return (
    // The scrollbar-* utilities here needed a Tailwind plugin the project doesn't
    // install, so they never applied. Dropped rather than adding a dependency to
    // restyle a scrollbar.
    <div className="w-full overflow-x-auto">
      <div
        className="relative mb-2 h-4 select-none"
        style={{ width: weeks.length * 14 }}
      >
        {monthLabels.map(({ weekIndex, label }) => (
          <span
            key={weekIndex}
            className="absolute text-meta font-bold text-muted-foreground uppercase tracking-wider font-mono"
            style={{ left: weekIndex * 14 }}
          >
            {label}
          </span>
        ))}
      </div>
      <div className="flex gap-[3px]" style={{ width: weeks.length * 14 }}>
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[3px]">
            {week.map((day, di) => (
              <motion.div
                key={day.date}
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.15, delay: (wi * 7 + di) * 0.0008 }}
                title={`${day.count} contribution${day.count === 1 ? "" : "s"} on ${day.date}`}
                className={`h-[11px] w-[11px] rounded-[2px] ${LEVEL_CLASSNAMES[levelFor(day.count, max)]}`}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-end gap-1.5 text-meta font-bold text-muted-foreground uppercase tracking-wider font-mono select-none">
        <span>Less</span>
        {LEVEL_CLASSNAMES.map((cls, idx) => (
          <div key={idx} className={`h-[10px] w-[10px] rounded-[2px] ${cls}`} />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}
