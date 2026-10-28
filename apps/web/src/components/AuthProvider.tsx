"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  ReactNode,
} from "react";
import { API_URL } from "@/lib/api";

export interface SignupInput {
  email: string;
  password: string;
  full_name?: string;
  role: string;
  username?: string;
}

interface AuthContextValue {
  isLoaded: boolean;
  isSignedIn: boolean;
  getToken: () => Promise<string | null>;
  login: (email: string, password: string) => Promise<void>;
  signup: (input: SignupInput) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [isSignedIn, setIsSignedIn] = useState(false);

  useEffect(() => {
    // Reading localStorage is exactly the "subscribe to an external system" case the
    // rule carves out: it does not exist during SSR, so this value cannot be computed in
    // the initial state without breaking hydration. Runs once on mount with an empty
    // dependency list, so there is no cascade to worry about.
    const token = localStorage.getItem("access_token");
    /* eslint-disable react-hooks/set-state-in-effect */
    setIsSignedIn(!!token);
    setIsLoaded(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  // Every data fetcher in the app is memoized on `getToken` (useCallback deps), and
  // useAsyncResource refetches whenever its `fetcher` identity changes. An unmemoized
  // getToken therefore invalidated ~28 fetchers on every AuthProvider render and
  // re-issued their requests. Stable identity here is what makes those useCallbacks
  // actually hold.
  const getToken = useCallback(async (): Promise<string | null> => {
    return localStorage.getItem("access_token");
  }, []);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Login failed");
      }

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      setIsSignedIn(true);
    },
    [],
  );

  const signup = useCallback(async (input: SignupInput): Promise<void> => {
    const response = await fetch(`${API_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Signup failed");
    }

    const data = await response.json();
    localStorage.setItem("access_token", data.access_token);
    setIsSignedIn(true);
  }, []);

  const logout = useCallback((): void => {
    localStorage.removeItem("access_token");
    setIsSignedIn(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ isLoaded, isSignedIn, getToken, login, signup, logout }),
    [isLoaded, isSignedIn, getToken, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
