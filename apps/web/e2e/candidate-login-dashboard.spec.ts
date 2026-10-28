import { expect, test } from "@playwright/test";

/**
 * Covers the path every authenticated page depends on: sign in with the seeded demo
 * candidate, land on the role hub, and reach the dashboard with its navigation intact.
 *
 * Auth is self-hosted (bcrypt + HS256 JWT issued by this API), so the test drives the
 * app's own /sign-in form directly. An earlier version of this file drove a hosted
 * Clerk <SignIn/> widget and imported @clerk/testing — a provider this project does
 * not use and a package that is not in package.json, so the suite could not even
 * import, let alone run.
 *
 * Credentials default to the seeded demo candidate (scripts/seed_db.py). Override via
 * apps/web/.env.test if you seeded something else.
 */

const EMAIL = process.env.E2E_CANDIDATE_EMAIL ?? "demo_candidate@trace.dev";
const PASSWORD = process.env.E2E_CANDIDATE_PASSWORD ?? "password123";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/sign-in");
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASSWORD);
  // Scoped to the form: the site header also has a "Sign in" control, and it now
  // correctly exposes role="button", so an unscoped match is ambiguous.
  await page
    .locator("form")
    .getByRole("button", { name: /sign in/i })
    .click();
}

test.describe("candidate authentication", () => {
  test("signs in and lands on the role hub", async ({ page }) => {
    await signIn(page);

    // Sign-in redirects to /home — the role-aware landing hub. Generous timeout: the
    // API pre-warms a 1.3GB embedding model at startup, so the very first request of
    // a cold run is slow.
    // waitUntil: "commit" because sign-in navigates via next/navigation's router.replace,
    // a client-side transition that never fires a `load` event — the default wait state.
    await page.waitForURL(/\/home/, { timeout: 30_000, waitUntil: "commit" });

    // The hub lists every capability for the signed-in role, so a known card proves
    // both that /me resolved and that the correct role catalog rendered.
    await expect(
      page.getByRole("heading", { name: /everything you can do/i }),
    ).toBeVisible();

    // Scoped to <main>: "Talent dashboard" is now both a sidebar item and a card in the
    // hub's capability grid, so an unscoped match is ambiguous. The card is the thing
    // this test is actually about — it proves the role catalog rendered, which the
    // sidebar (which renders before /me resolves) would not.
    await expect(
      page.getByRole("main").getByRole("link", { name: /talent dashboard/i }),
    ).toBeVisible();
  });

  test("shows the workspace sidebar on authenticated pages", async ({
    page,
  }) => {
    await signIn(page);
    // waitUntil: "commit" because sign-in navigates via next/navigation's router.replace,
    // a client-side transition that never fires a `load` event — the default wait state.
    await page.waitForURL(/\/home/, { timeout: 30_000, waitUntil: "commit" });

    // The sidebar is the app's primary navigation and used to be gated behind GET /me,
    // so it vanished on every route change. Asserting it here would catch a regression
    // back to that behaviour.
    // "Talent dashboard", not "Dashboard": the redesign grouped the candidate's flat
    // nav into sections and renamed this item, since "Dashboard" alone said nothing
    // about whose data it showed. Kept `exact` so a future duplicate label is caught.
    const sidebar = page.getByRole("complementary");
    const dashboard = sidebar.getByRole("link", {
      name: "Talent dashboard",
      exact: true,
    });
    await expect(dashboard).toBeVisible();

    await dashboard.click();
    await page.waitForURL(/\/dashboard/, {
      timeout: 30_000,
      waitUntil: "commit",
    });

    // Still visible after navigating: the shell must not blank out between routes.
    await expect(
      sidebar.getByRole("link", { name: "Home", exact: true }),
    ).toBeVisible();
  });

  test("rejects bad credentials without navigating", async ({ page }) => {
    await page.goto("/sign-in");
    await page.getByLabel(/email/i).fill(EMAIL);
    await page.getByLabel(/password/i).fill("definitely-not-the-password");
    await page
      .locator("form")
      .getByRole("button", { name: /sign in/i })
      .click();

    // The form surfaces the API's raw error detail, which is `invalid_credentials`
    // for a wrong password (verified against POST /auth/login, which 401s with that
    // body). Matching the underscore form rather than prose keeps this honest about
    // what the UI actually renders today.
    await expect(page.getByText(/invalid_credentials/i).first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(page).toHaveURL(/\/sign-in/);
  });
});
