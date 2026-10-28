import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep compiled pages resident in memory for the whole dev session (24 hours)
  // and maintain a high buffer limit so previously visited routes are never disposed
  // and recompiled from scratch.
  onDemandEntries: {
    maxInactiveAge: 24 * 60 * 60 * 1000,
    pagesBufferLength: 100,
  },

  experimental: {
    optimizePackageImports: [
      "framer-motion",
      "lucide-react",
      "recharts",
      "@dnd-kit/core",
      "@dnd-kit/sortable",
      "clsx",
      "tailwind-merge",
      "sonner",
    ],
  },

  images: {
    // Candidate avatars come straight from GitHub's CDN. Without an allowlist,
    // next/image refuses the host outright.
    remotePatterns: [
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
      { protocol: "https", hostname: "raw.githubusercontent.com" },
    ],
  },

  compiler: {
    // Strip console noise from production bundles but keep `console.error` — it is the
    // only channel several catch-blocks use to report a genuine failure, and dropping it
    // would make production faults invisible rather than merely quieter.
    removeConsole: { exclude: ["error"] },
  },
};

export default nextConfig;
