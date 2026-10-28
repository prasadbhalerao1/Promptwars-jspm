"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Marketing header for the public landing page.
 *
 * Separate from `AppHeader`, which is signed-in app chrome (mobile nav trigger, account
 * menu) and reads the current user. A marketing page needs none of that, and showing app
 * furniture to someone who has never signed in is the fastest way to make a landing page
 * look like a dashboard.
 *
 * Quiet by default: no border until the page scrolls, so the header does not draw a line
 * across the hero.
 */

const NAV = [
  { href: "#platform", label: "Platform" },
  { href: "#candidates", label: "For candidates" },
  { href: "#recruiters", label: "For recruiters" },
  { href: "#intelligence", label: "Intelligence" },
] as const;

export function LandingHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    // passive: this listener must never block scrolling.
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 h-16 bg-background/80 backdrop-blur-md transition-shadow duration-(--animate-duration-base)",
        scrolled ? "shadow-flat" : "shadow-none",
      )}
    >
      <div className="mx-auto flex h-full w-full max-w-workspace items-center justify-between gap-6 px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 rounded-sm text-section font-semibold tracking-tight text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span aria-hidden className="size-2 rounded-full bg-primary" />
          TRACE
        </Link>

        {/* Centre nav collapses below lg rather than wrapping: a marketing nav that
            stacks onto two lines reads as broken. The links are in-page anchors, so
            nothing is lost on small screens where the user simply scrolls. */}
        <nav
          aria-label="Sections"
          className="hidden items-center gap-7 lg:flex"
        >
          {NAV.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-sm text-body text-muted-foreground outline-none transition-colors duration-(--animate-duration-fast) hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            render={<Link href="/sign-in" />}
            className="hidden sm:inline-flex"
          >
            Sign in
          </Button>
          <Button size="sm" render={<Link href="/sign-up" />}>
            Get started
          </Button>
        </div>
      </div>
    </header>
  );
}
