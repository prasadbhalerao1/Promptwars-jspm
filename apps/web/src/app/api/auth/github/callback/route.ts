// Pure passthrough, per doc 00 §2.1 ("Next.js never runs business logic") — the OAuth
// code/token exchange itself happens in FastAPI (services/api/routers/candidates.py),
// not here. This only exists because GITHUB_OAUTH_REDIRECT_URI is already registered
// on the GitHub OAuth App as this frontend URL; changing that would require access to
// the GitHub App settings this session doesn't have.
import { type NextRequest, NextResponse } from "next/server";

import { BACKEND_URL } from "@/lib/env";

export async function GET(request: NextRequest) {
  const target = new URL("/candidates/github/oauth/callback", BACKEND_URL);
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });
  return NextResponse.redirect(target);
}
