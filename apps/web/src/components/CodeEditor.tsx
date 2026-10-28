"use client";

import dynamic from "next/dynamic";

// Monaco is the single heaviest dependency in the app. Statically imported, it was
// downloaded by every assessment page — including MCQ assessments, which never render an
// editor at all. ssr: false because Monaco needs a DOM and cannot be server-rendered
// anyway, so there is nothing lost by deferring it to the client.
const Editor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex size-full items-center justify-center bg-foreground text-sm text-muted-foreground">
      Loading editor…
    </div>
  ),
});

export function CodeEditor({
  value,
  onChange,
  language = "python",
  height = "24rem",
}: {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  height?: string;
}) {
  return (
    <div
      className="rounded-md border border-border overflow-hidden"
      style={{ height }}
    >
      <Editor
        height={height}
        language={language}
        theme="vs-dark"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        options={{
          minimap: { enabled: false },
          fontSize: 13,
          scrollBeyondLastLine: false,
        }}
      />
    </div>
  );
}
