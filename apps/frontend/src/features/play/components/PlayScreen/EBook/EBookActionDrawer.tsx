import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { usePlayStore } from "../../../stores/play.store";
import { ActionMode } from "../../../types/play.types";
import { EBookActionDrawerProps } from "./ebook.types";

interface ModeOption {
  key: ActionMode;
  label: string;
  prefix: string;
  hint: string;
}

const MODES: ModeOption[] = [
  {
    key: "do",
    label: "Do",
    prefix: "I ",
    hint: "Perform a physical deed or travel",
  },
  {
    key: "say",
    label: "Say",
    prefix: 'I say: "',
    hint: "Speak dialogue or call out",
  },
  {
    key: "see",
    label: "See",
    prefix: "I examine ",
    hint: "Inspect surroundings or creatures",
  },
  {
    key: "story",
    label: "Story",
    prefix: "Narrate: ",
    hint: "Introduce a narrative shift",
  },
];

export function EBookActionDrawer({
  isOpen,
  onClose,
  onSubmit,
  isNarrating,
}: EBookActionDrawerProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeMode = usePlayStore((s) => s.active_mode);
  const setActiveMode = usePlayStore((s) => s.setActiveMode);
  const theme = usePlayStore((s) => s.ebook_theme);
  const isSepia = theme === "antique-sepia";

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [text]);

  const handleSubmit = () => {
    if (!text.trim() || isNarrating) return;
    onSubmit(text.trim());
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  if (!isOpen) return null;

  const currentMode = MODES.find((m) => m.key === activeMode) ?? MODES[0];
  const drawerStyle = isSepia
    ? "bg-[#f5ebd7] border-[#d8c7a8] text-[#2c2217] shadow-2xl shadow-amber-950/20"
    : "bg-[#09090b] border-zinc-800 text-zinc-100 shadow-2xl shadow-black";

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 p-3 sm:p-4 flex justify-center animate-slide-up">
      <div
        className={`w-full max-w-2xl p-4 sm:p-5 rounded-2xl border backdrop-blur-xl flex flex-col gap-3 ${drawerStyle}`}
      >
        <div className="flex items-center justify-between border-b border-inherit/20 pb-3">
          <div className="flex items-center gap-1 sm:gap-1.5 font-mono text-xs">
            {MODES.map((mode) => {
              const isActive = activeMode === mode.key;
              return (
                <button
                  key={mode.key}
                  type="button"
                  onClick={() => setActiveMode(mode.key)}
                  title={mode.hint}
                  className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                    isActive
                      ? isSepia
                        ? "bg-[#2c2217] text-[#faf4e8] font-bold shadow-sm"
                        : "bg-zinc-100 text-zinc-950 font-bold shadow-sm"
                      : "opacity-60 hover:opacity-100 hover:bg-zinc-800/40"
                  }`}
                >
                  {mode.label}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded opacity-60 hover:opacity-100 transition-opacity cursor-pointer font-mono text-xs"
            title="Collapse Action Bar (Esc)"
          >
            ✕ Close
          </button>
        </div>

        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            disabled={isNarrating}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Action (${currentMode.label}): ${currentMode.hint.toLowerCase()}...`}
            className="flex-1 bg-transparent border border-inherit/30 rounded-xl p-3 text-sm md:text-base font-serif focus:outline-none focus:border-zinc-500 resize-none leading-relaxed"
          />

          <button
            type="button"
            disabled={!text.trim() || isNarrating}
            onClick={handleSubmit}
            className={`px-5 py-3 rounded-xl font-mono text-xs font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer shrink-0 ${
              isSepia
                ? "bg-[#2c2217] hover:bg-[#433523] text-[#faf4e8]"
                : "bg-zinc-100 hover:bg-white text-zinc-950"
            }`}
          >
            Submit ↵
          </button>
        </div>

        <div className="flex items-center justify-between text-[11px] font-mono opacity-60 px-1">
          <span>
            Prefix:{" "}
            <em className="not-italic font-semibold">{currentMode.prefix}</em>
          </span>
          <span>Press Cmd/Ctrl + Enter to send</span>
        </div>
      </div>
    </div>
  );
}
