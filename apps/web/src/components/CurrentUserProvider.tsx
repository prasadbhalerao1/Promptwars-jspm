"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { fetchMe, type MeResponse } from "@/lib/api";
import { MAX_AUTO_RETRIES, isRetryable, retryDelayMs } from "@/lib/errors";

interface CurrentUserContextValue {
  // undefined = auth/fetch not settled yet, null = signed out, MeResponse = resolved.
  me: MeResponse | null | undefined;
  isLoaded: boolean;
  isSignedIn: boolean | undefined;
  error: string | null;
  /** How many times the /me fetch has been retried after a connection-level failure.
   * Lets the UI escalate its copy from "connecting…" to "the server isn't responding"
   * instead of claiming a warm-up that clearly isn't happening. */
  attempts: number;
  reload: () => void;
}

/** Retry budget for GET /me. Shared with useAsyncResource — these were two separate
 * constants holding the same value for the same purpose. */
const _MAX_ME_RETRIES = MAX_AUTO_RETRIES;

/** Distinguishes "the request never reached the server" from a real API error, via the
 * shared classifier so /me and every other fetch agree on what is worth retrying. */
const isTransientMeError = (message: string) => isRetryable(message);

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

// Every route-group layout ((admin), (candidate), (judge), (organizer), (recruiter))
// independently called getToken() + fetchMe() on mount, guaranteeing a redundant GET /me
// round trip on every navigation between route groups. This provider fetches it once,
// shared via context, so layouts only need to read the result and apply their own role
// check/redirect.
// Last-known /me, cached so a returning user's role gate resolves without waiting on the
// network. Every authenticated page previously blocked its first paint on this one
// request. Authorization is unaffected: the API re-checks the role on every call, so a
// stale cache can at worst cause one redirect, never unauthorized access.
const ME_CACHE_KEY = "trace:me";

function readCachedMe(): MeResponse | undefined {
  // localStorage doesn't exist during SSR, and a corrupt/outdated entry must degrade to
  // "no cache" rather than crashing the whole provider.
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(ME_CACHE_KEY);
    return raw ? (JSON.parse(raw) as MeResponse) : undefined;
  } catch {
    return undefined;
  }
}

function writeCachedMe(me: MeResponse | null): void {
  try {
    if (me) window.localStorage.setItem(ME_CACHE_KEY, JSON.stringify(me));
    else window.localStorage.removeItem(ME_CACHE_KEY);
  } catch {
    // Quota errors / private mode — the cache is an optimization, never load-bearing.
  }
}

export function CurrentUserProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken, logout } = useAuth();
  // Holds only what must be fetched. The signed-out value is *derived* below rather than
  // written by an effect — being signed out is not new information that needs storing,
  // it's already known from `isSignedIn`, and setting it in an effect meant one extra
  // render on every sign-out.
  //
  // NOT seeded in the useState initializer: this provider is rendered from a Server
  // Component (app/layout.tsx), so the server has no localStorage and would emit markup
  // for the signed-out tree while the client emitted the cached-user tree — a hydration
  // mismatch. Instead it's read in the same effect that AuthProvider uses to establish
  // `isLoaded`, which by construction only runs post-hydration. The cached value is
  // therefore applied on the first *client* render, before the network call resolves,
  // which is where the blank-screen win actually comes from.
  const [fetchedMe, setFetchedMe] = useState<MeResponse | undefined>(undefined);
  // Last-known user from a previous session, read once per mount via the lazy
  // initializer (JSON.parse would otherwise return a fresh object on every render and
  // defeat the useMemo below). It is deliberately NOT used as the initial value of
  // `fetchedMe`: `me` gates on `isLoaded` before consulting this, and `isLoaded` only
  // flips in AuthProvider's post-hydration effect, so the server render never sees a
  // cached user and hydration stays consistent.
  const [cachedMe] = useState<MeResponse | undefined>(readCachedMe);
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState(0);
  // State, not a ref: a ref mutation doesn't re-render, so listing `tick.current` in the
  // dependency array below never actually re-ran the effect — React compares the value
  // captured at the *previous* render, which the mutation had already changed in place.
  // `reload()` therefore only refetched by accident, when some other dependency happened
  // to change too. Incrementing state makes the refetch deterministic.
  const [reloadCount, setReloadCount] = useState(0);

  const reload = useCallback(() => {
    setReloadCount((n) => n + 1);
    setFetchedMe(undefined);
    writeCachedMe(null);
    setError(null);
    setAttempts(0);
  }, []);

  useEffect(() => {
    // Signed out: nothing to fetch, and nothing to store — `me` below already resolves
    // to null from `isSignedIn` alone. Drop the cache so the next user to sign in on
    // this browser never sees the previous one's role.
    if (!isLoaded) return;
    if (!isSignedIn) {
      writeCachedMe(null);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const load = async (attempt: number): Promise<void> => {
      try {
        const token = await getToken();
        if (!token || cancelled) return;
        const result = await fetchMe(token);
        if (cancelled) return;
        setFetchedMe(result);
        writeCachedMe(result);
        setAttempts(0);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Failed to load account";
        // Check for 401 in error message (token expired/invalid)
        if (message.includes("401")) {
          writeCachedMe(null);
          logout();
          router.replace("/sign-in");
          return;
        }

        // The API pre-warms a 1.3GB embedding model at boot, so the first request of a
        // cold start can fail purely because the server isn't listening yet. That is a
        // wait, not a fault: retry on a backoff and let the UI say "connecting" rather
        // than presenting a dead end with a Retry button as the only way forward.
        if (isTransientMeError(message) && attempt < _MAX_ME_RETRIES) {
          setAttempts(attempt + 1);
          timer = setTimeout(
            () => {
              if (!cancelled) void load(attempt + 1);
            },
            retryDelayMs(attempt),
          );
          return;
        }

        // A cached value is already on screen, so this was a background revalidation
        // and swapping working content for an error panel would be a regression. Only
        // surface the error when there was nothing to show in the first place.
        if (readCachedMe() === undefined) setError(message);
      }
    };

    void load(0);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [isLoaded, isSignedIn, getToken, logout, router, reloadCount]);

  // undefined = still settling, null = definitively signed out, MeResponse = loaded.
  //
  // Falls back to the cached user while the first fetch is still in flight, so a
  // returning user's role gate resolves on the first client render instead of after a
  // network round trip — every authenticated page used to block its first paint on that
  // request. The `!isLoaded` branch is what keeps this hydration-safe: it short-circuits
  // to undefined on the server (and on the first client render, pre-effect), so the
  // cached user can never appear in server markup.
  const me: MeResponse | null | undefined = !isLoaded
    ? undefined
    : !isSignedIn
      ? null
      : (fetchedMe ?? cachedMe);

  // Object literal here re-rendered every consumer (all five route-group layouts and
  // anything calling useCurrentUser) on each render of this provider, regardless of
  // whether `me` actually changed.
  const value = useMemo<CurrentUserContextValue>(
    () => ({ me, isLoaded, isSignedIn, error, attempts, reload }),
    [me, isLoaded, isSignedIn, error, attempts, reload],
  );

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser(): CurrentUserContextValue {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) {
    throw new Error("useCurrentUser must be used within a CurrentUserProvider");
  }
  return ctx;
}
