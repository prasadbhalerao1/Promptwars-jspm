import { expect, test, type Page } from "@playwright/test";

/**
 * The interview lobby's four device-permission branches.
 *
 * These were the last untested paths from the interview work: the camera-release fix was
 * verified in a real browser, but the branches that decide what a candidate *sees* when
 * permission is refused — or when there is no hardware at all — never were.
 *
 * Why `getUserMedia` is stubbed rather than driven through Playwright's permission API:
 * `playwright.config.ts` launches Chromium with `--use-fake-ui-for-media-stream`, which
 * auto-accepts every media prompt. That flag exists so the happy path works on a machine
 * with no webcam, but it makes denial unreachable through `context.clearPermissions()` —
 * the fake UI grants before the permission store is ever consulted. Overriding the method
 * itself is the only way to reach the rejection branches while keeping that flag.
 *
 * The stub rejects with the exact `DOMException` names the browser uses, because the
 * component branches on `err.name` (`NotFoundError` → "no device", `NotAllowedError` →
 * "denied"). Asserting on those names is the point: a refactor that stopped distinguishing
 * them would still render *a* message, and only these tests would notice it is the wrong one.
 */

const EMAIL = process.env.E2E_CANDIDATE_EMAIL ?? "demo_candidate@trace.dev";
const PASSWORD = process.env.E2E_CANDIDATE_PASSWORD ?? "password123";

/** Replaces `navigator.mediaDevices.getUserMedia` before any app code runs.
 *
 * `addInitScript` rather than `page.evaluate`: the lobby calls getUserMedia from an effect
 * that fires on mount, so patching after navigation would race the component and usually
 * lose. */
async function stubGetUserMedia(
  page: Page,
  behaviour: "grant" | "deny" | "no-device" | "unsupported",
) {
  await page.addInitScript((mode) => {
    // `unsupported` models an insecure context or an old browser: the API is absent
    // entirely, which the component checks for before it ever calls the method.
    if (mode === "unsupported") {
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        get: () => undefined,
      });
      return;
    }

    const fail = (name: string, message: string) => () => {
      const err = new Error(message);
      err.name = name;
      return Promise.reject(err);
    };

    const impl =
      mode === "deny"
        ? fail("NotAllowedError", "Permission denied")
        : mode === "no-device"
          ? fail("NotFoundError", "Requested device not found")
          : // "grant": hand back a real, silent, black MediaStream from a canvas +
            // WebAudio, so the preview, the track toggles and the release-on-unmount
            // path all operate on genuine MediaStreamTracks rather than a mock object.
            async () => {
              const canvas = document.createElement("canvas");
              canvas.width = 320;
              canvas.height = 240;
              canvas.getContext("2d")!.fillRect(0, 0, 320, 240);
              const video = (
                canvas as HTMLCanvasElement & {
                  captureStream(fps?: number): MediaStream;
                }
              ).captureStream(30);
              const ctx = new AudioContext();
              const dest = ctx.createMediaStreamDestination();
              ctx.createOscillator().connect(dest);
              return new MediaStream([
                ...video.getVideoTracks(),
                ...dest.stream.getAudioTracks(),
              ]);
            };

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { ...navigator.mediaDevices, getUserMedia: impl },
    });
  }, behaviour);
}

async function signIn(page: Page) {
  await page.goto("/sign-in");

  // Wait for hydration before typing. On a cold dev server the markup paints well before
  // React attaches its handlers, and `fill` into a not-yet-controlled input is silently
  // discarded when hydration replaces the DOM — the form then submits empty and the page
  // simply never navigates. Asserting the value stuck is what makes this deterministic.
  const email = page.getByLabel(/email/i);
  const password = page.getByLabel(/password/i);
  await email.fill(EMAIL);
  await expect(email).toHaveValue(EMAIL, { timeout: 30_000 });
  await password.fill(PASSWORD);
  await expect(password).toHaveValue(PASSWORD);

  // Scoped to the form: the site header also has a "Sign in" control, and it now
  // correctly exposes role="button", so an unscoped match is ambiguous.
  await page
    .locator("form")
    .getByRole("button", { name: /sign in/i })
    .click();
  // Client-side router.replace never fires `load`; see candidate-login-dashboard.spec.ts.
  await page.waitForURL(/\/home/, { timeout: 30_000, waitUntil: "commit" });

  // `commit` resolves the moment the URL changes, which is *before* AuthProvider has
  // written the token to localStorage. Navigating on that signal alone raced the write
  // and landed on /interviews signed-out. Waiting for the token itself is the honest
  // barrier — it is the exact state the next navigation depends on.
  await page.waitForFunction(
    () => !!localStorage.getItem("access_token"),
    null,
    {
      timeout: 30_000,
    },
  );
}

/** Drives the practice-interview form, which is the reachable route into the lobby.
 *
 * This deliberately exercises the real `generate-questions` endpoint instead of mocking
 * it — the topics the lobby renders come from that call, and a mocked list would prove
 * nothing about the flow a candidate actually takes. */
async function openLobby(page: Page) {
  await page.goto("/interviews");
  // The form is collapsed behind a disclosure button until requested.
  await page
    .getByRole("button", { name: /create practice interview/i })
    .click();

  await page.getByLabel(/role title/i).fill("Backend Engineer");
  await page
    .getByLabel(/role description/i)
    .fill("Python and FastAPI services, PostgreSQL, async APIs.");
  await page.getByRole("button", { name: /generate topics/i }).click();

  // Generation is a live LLM call against a possibly-cold API, so this waits on the
  // generated topics rather than a fixed delay. `exact` matters: "Start Over" sits
  // beside "Continue" and a loose name match would take whichever renders first.
  await expect(page.getByText(/topic 1/i)).toBeVisible({ timeout: 120_000 });
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: /ready to join\?/i }),
  ).toBeVisible({ timeout: 30_000 });
}

test.describe("interview lobby — device permission states", () => {
  test("granted: preview is live and both toggles are usable", async ({
    page,
  }) => {
    await stubGetUserMedia(page, "grant");
    await signIn(page);
    await openLobby(page);

    // A <video> element only renders on the granted branch.
    await expect(page.locator("video")).toBeVisible();

    const camera = page.getByRole("button", { name: /camera on/i });
    const mic = page.getByRole("button", { name: /mic on/i });
    await expect(camera).toBeEnabled();
    await expect(mic).toBeEnabled();

    // Toggling flips the track's `enabled` flag, which drives the label.
    await camera.click();
    await expect(
      page.getByRole("button", { name: /camera off/i }),
    ).toBeVisible();
    await expect(page.getByText(/camera is off/i)).toBeVisible();

    await mic.click();
    await expect(page.getByRole("button", { name: /mic off/i })).toBeVisible();
  });

  test("denied: explains how to re-enable and still allows joining", async ({
    page,
  }) => {
    await stubGetUserMedia(page, "deny");
    await signIn(page);
    await openLobby(page);

    await expect(
      page.getByText(/camera and microphone blocked/i),
    ).toBeVisible();
    await expect(page.getByText(/allow access in your browser/i)).toBeVisible();
    await expect(page.locator("video")).toHaveCount(0);

    // Toggles are meaningless without a stream, so they must be disabled rather than
    // throwing when clicked.
    await expect(
      page.getByRole("button", { name: /camera on/i }),
    ).toBeDisabled();
    await expect(page.getByRole("button", { name: /mic on/i })).toBeDisabled();

    // The load-bearing assertion: the interview is answerable by text, so a refused
    // camera must never strand the candidate.
    await expect(
      page.getByRole("button", { name: /join interview/i }),
    ).toBeEnabled();
  });

  test("no device: distinguishes missing hardware from refusal", async ({
    page,
  }) => {
    await stubGetUserMedia(page, "no-device");
    await signIn(page);
    await openLobby(page);

    await expect(
      page.getByText(/no camera or microphone found/i),
    ).toBeVisible();
    // The remedy differs from the denied case, so the copy must too — this is the
    // assertion that would catch the two branches being collapsed into one.
    await expect(page.getByText(/works entirely by text/i)).toBeVisible();
    await expect(page.getByText(/allow access in your browser/i)).toHaveCount(
      0,
    );
    await expect(
      page.getByRole("button", { name: /join interview/i }),
    ).toBeEnabled();
  });

  test("unsupported: degrades without throwing when the API is absent", async ({
    page,
  }) => {
    await stubGetUserMedia(page, "unsupported");
    await signIn(page);
    await openLobby(page);

    await expect(page.getByText(/can't access media devices/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /join interview/i }),
    ).toBeEnabled();
  });
});
