"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, type SignupInput } from "@/components/AuthProvider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  SIGNUP_ROLE_OPTIONS,
  RESERVED_USERNAMES,
  USERNAME_PATTERN,
  type Role,
} from "@/lib/constants";
import { Input } from "@/components/ui/input";

export default function SignUpPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [username, setUsername] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!role) return;

    if (role === "candidate") {
      const cleanUsername = username.trim().toLowerCase();
      if (!cleanUsername) {
        setError("A portfolio username is required for candidates.");
        return;
      }
      if (RESERVED_USERNAMES.has(cleanUsername) || !USERNAME_PATTERN.test(cleanUsername)) {
        setError("Username must be 3-40 lowercase characters (a-z, 0-9, hyphens) and not a system reserved name.");
        return;
      }
    }

    setSubmitting(true);
    setError(null);
    try {
      const input: SignupInput = {
        email,
        password,
        full_name: fullName || undefined,
        role,
        username:
          role === "candidate" && username.trim() ? username.trim().toLowerCase() : undefined,
      };
      await signup(input);
      router.replace("/home");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sign up failed";
      if (msg.includes("username_taken")) {
        setError("That username is already taken. Please choose a different portfolio handle.");
      } else if (msg.includes("invalid_username")) {
        setError("Invalid username. Use 3-40 lowercase letters, numbers, or hyphens.");
      } else if (msg.includes("email_taken")) {
        setError("An account with this email already exists.");
      } else {
        setError(msg);
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-md items-center p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="font-heading">Create Account</CardTitle>
          {role === "candidate" && (
            <CardDescription>
              Claim your unique portfolio link now - you can always change it
              later in Profile settings.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="full-name">Full Name</Label>
              <Input
                id="full-name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your Name"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">I am a…</Label>
              <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                <SelectTrigger id="role">
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  {SIGNUP_ROLE_OPTIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {role === "candidate" && (
              <div className="space-y-2">
                <Label htmlFor="username">
                  Portfolio Username{" "}
                  <span className="text-xs font-normal text-destructive">
                    (required)
                  </span>
                </Label>
                <div className="flex items-center rounded-md border border-input bg-background ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
                  <span className="select-none pl-3 text-sm text-muted-foreground">
                    trace.dev/
                  </span>
                  <Input
                    id="username"
                    value={username}
                    onChange={(e) =>
                      setUsername(
                        e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
                      )
                    }
                    placeholder="yourname"
                    required
                    className="border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 pl-1"
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button
              type="submit"
              pending={submitting}
              disabled={!role || (role === "candidate" && !username.trim())}
              className="w-full"
            >
              {submitting ? "Creating account…" : "Sign Up"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link href="/sign-in" className="font-semibold hover:underline">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
