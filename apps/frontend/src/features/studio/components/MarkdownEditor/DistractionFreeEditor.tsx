import React, { useState } from "react";
import ReactMarkdown, { Components } from "react-markdown";
import rehypeSanitize from "rehype-sanitize";

interface DistractionFreeEditorProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  className?: string;
}

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold mt-6 mb-4 text-content">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-xl font-bold mt-5 mb-3 text-content">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-bold mt-4 mb-2 text-content">{children}</h3>
  ),
  ul: ({ children }) => <ul className="my-1">{children}</ul>,
  li: ({ children }) => (
    <li className="ml-5 list-disc text-content-muted my-1">{children}</li>
  ),
  p: ({ children }) => (
    <p className="text-content-muted leading-relaxed mb-3">{children}</p>
  ),
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
              <ReactMarkdown
                rehypePlugins={[rehypeSanitize]}
                components={markdownComponents}
              >
                {value}
              </ReactMarkdown>
            ) : (
              <p className="text-content-faint italic">Nothing to preview</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
