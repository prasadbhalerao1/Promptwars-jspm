// Client-side Pyodide (WASM Python) execution — doc 03 §2/§5's non-negotiable design:
// candidate code never runs on the backend, ever. Loaded from the CDN (not bundled)
// since Pyodide's runtime + stdlib assets are large binary files that don't belong in
// the Next.js webpack bundle — this is the standard integration pattern for Pyodide in
// a bundled web app.
//
// Convention (matches the pre-existing assessment stub page's example and doc 03 §9's
// worked example): every coding assessment's entry point is a single function named
// `solve_problem` taking one argument.

import type { HiddenTest, TestResult } from "@/lib/api";
import { PYODIDE_INDEX_URL } from "@/lib/env";

let pyodidePromise: Promise<PyodideInterface> | null = null;

// Minimal shape of what we actually use from the Pyodide instance.
interface PyodideInterface {
  runPython: (code: string) => unknown;
  globals: { set: (name: string, value: unknown) => void };
}

// `loadPyodide` is attached to `window` by the CDN script loaded in `getPyodide`.
declare global {
  interface Window {
    loadPyodide?: (options: {
      indexURL: string;
    }) => Promise<PyodideInterface>;
  }
}

/** Injects the CDN loader script once, resolving when `window.loadPyodide` exists.
 *
 * This is deliberately a runtime `<script>` tag rather than `import("pyodide")`. The npm
 * package's entry pulls in `node:fs`, `node:path` and `node:child_process` for its
 * Node.js code path; webpack cannot resolve the `node:` scheme and fails the module
 * build, which made this whole route return a 500 under `next dev --webpack` (the
 * script `npm run dev` actually runs) and broke `next build --webpack` outright.
 * Turbopack tolerated it, which is why the failure only showed on one of the two
 * bundlers. Since the runtime and stdlib were already being fetched from the CDN, the
 * package was never needed at runtime -- only its type signature was. */
function loadPyodideScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.loadPyodide) {
      resolve();
      return;
    }
    const src = `${PYODIDE_INDEX_URL}pyodide.js`;
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${src}"]`,
    );
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error("Could not load the Python runtime.")),
        { once: true },
      );
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () =>
      reject(new Error("Could not load the Python runtime."));
    document.head.appendChild(script);
  });
}

async function getPyodide(): Promise<PyodideInterface> {
  if (!pyodidePromise) {
    pyodidePromise = loadPyodideScript().then(() => {
      if (!window.loadPyodide) {
        throw new Error("Could not load the Python runtime.");
      }
      return window.loadPyodide({ indexURL: PYODIDE_INDEX_URL });
    });
    // A failed load must not be cached, or every later attempt reuses the rejection
    // and the user can never retry without a full reload.
    pyodidePromise.catch(() => {
      pyodidePromise = null;
    });
  }
  return pyodidePromise;
}

function valuesEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

/** Runs `code` against each hidden test's input in an isolated WASM instance, comparing
 * to the expected output locally. Returns pass/fail only — the caller submits this
 * result array to the backend, never the raw comparison details (doc 03 §2). */
export async function runHiddenTests(
  code: string,
  tests: HiddenTest[],
): Promise<TestResult[]> {
  const pyodide = await getPyodide();
  const results: TestResult[] = [];

  for (let i = 0; i < tests.length; i++) {
    const test = tests[i];
    const testName = `test_${i + 1}`;
    try {
      pyodide.globals.set("__test_input", test.input);
      pyodide.runPython(code);
      const actual = pyodide.runPython("solve_problem(__test_input)");
      results.push({
        test_name: testName,
        passed: valuesEqual(actual, test.expected),
      });
    } catch {
      results.push({ test_name: testName, passed: false });
    }
  }

  return results;
}
