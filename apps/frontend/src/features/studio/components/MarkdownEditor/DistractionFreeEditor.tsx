import React, { useState } from "react";

interface DistractionFreeEditorProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  className?: string;
}

const renderMarkdown = (text: string) => {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, index) => {
    const parsedLine = line
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>");

    if (parsedLine.startsWith("### ")) {
      return (
        <h3
          key={index}
          className="text-lg font-bold mt-4 mb-2 text-content"
          dangerouslySetInnerHTML={{ __html: parsedLine.slice(4) }}
        />
      );
    }
    if (parsedLine.startsWith("## ")) {
      return (
        <h2
          key={index}
          className="text-xl font-bold mt-5 mb-3 text-content"
          dangerouslySetInnerHTML={{ __html: parsedLine.slice(3) }}
        />
      );
    }
    if (parsedLine.startsWith("# ")) {
      return (
        <h1
          key={index}
          className="text-2xl font-bold mt-6 mb-4 text-content"
          dangerouslySetInnerHTML={{ __html: parsedLine.slice(2) }}
        />
      );
    }
    if (parsedLine.startsWith("- ")) {
      return (
        <li
          key={index}
          className="ml-5 list-disc text-content-muted my-1"
          dangerouslySetInnerHTML={{ __html: parsedLine.slice(2) }}
        />
      );
    }
    if (parsedLine.trim() === "") {
      return <div key={index} className="h-4"></div>;
    }
    return (
      <p
        key={index}
        className="text-content-muted leading-relaxed mb-1"
        dangerouslySetInnerHTML={{ __html: parsedLine }}
      />
    );
  });
};

export const DistractionFreeEditor: React.FC<DistractionFreeEditorProps> = ({
  value,
  onChange,
  placeholder,
  className = "",
}) => {
  const [mode, setMode] = useState<"write" | "preview">("write");

  return (
    <div
      className={`rounded-md relative flex flex-col border border-border-subtle bg-surface-inset transition-colors focus-within:border-content resize-y overflow-hidden min-h-[150px] ${className}`}
    >
      {/* Tabs */}
      <div className="flex items-center gap-4 px-4 border-b border-border-subtle bg-surface/50">
        <button
          onClick={() => setMode("write")}
          className={`py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors ${
            mode === "write"
              ? "border-content text-content"
              : "border-transparent text-content-faint hover:text-content-muted"
          }`}
        >
          Write
        </button>
        <button
          onClick={() => setMode("preview")}
          className={`py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors ${
            mode === "preview"
              ? "border-content text-content"
              : "border-transparent text-content-faint hover:text-content-muted"
          }`}
        >
          Preview
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 relative flex flex-col min-h-0">
        {mode === "write" ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full h-full flex-1 bg-transparent px-6 py-6 text-content-muted placeholder:text-content-faint focus:outline-none font-sans resize-none leading-relaxed"
          />
        ) : (
          <div className="w-full h-full flex-1 overflow-y-auto px-6 py-6 font-sans">
            {value ? (
              renderMarkdown(value)
            ) : (
              <p className="text-content-faint italic">Nothing to preview</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
