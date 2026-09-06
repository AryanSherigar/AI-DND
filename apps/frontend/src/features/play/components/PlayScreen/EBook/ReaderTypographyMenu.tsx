import React, { useEffect, useRef, useState } from "react";
import { usePlayStore } from "../../../stores/play.store";
import {
  FONT_GENRE_CATEGORIES,
  NARRATION_FONTS_CATALOG,
  resolveNarrationFont,
} from "@/shared/constants/narration-fonts";
import { loadNarrationFont } from "@/shared/lib/font-loader";
import { ReaderTypographyMenuProps } from "./ReaderTypographyMenu.types";

export const ReaderTypographyMenu: React.FC<ReaderTypographyMenuProps> = ({
  isSepia = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const scenarioFont = usePlayStore((s) => s.playthrough?.narration_font);
  const readerFontOverride = usePlayStore((s) => s.reader_font_override);
  const setReaderFontOverride = usePlayStore((s) => s.setReaderFontOverride);

  const defaultFontDef = resolveNarrationFont(scenarioFont);
  const effectiveFontDef = resolveNarrationFont(
    readerFontOverride ?? scenarioFont,
  );

  useEffect(() => {
    loadNarrationFont(effectiveFontDef.id);
  }, [effectiveFontDef.id]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleFontChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    const nextOverride = value === "default" ? null : value;
    setReaderFontOverride(nextOverride);
    loadNarrationFont(nextOverride ?? scenarioFont);
  };

  const popoverStyle = isSepia
    ? "bg-[#faf4e8] border-[#d8c7a8] text-[#2c2217]"
    : "bg-zinc-900 border-zinc-700 text-zinc-100";

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="p-1.5 px-2.5 rounded-xl border border-inherit/20 hover:bg-zinc-800/50 font-mono text-xs flex items-center gap-1 cursor-pointer transition-colors"
        title="Reader Typography & Font Settings"
        aria-label="Typography settings"
      >
        <span className="font-serif font-bold text-sm">Aa</span>
        <span className="hidden lg:inline text-[11px] opacity-80">
          {effectiveFontDef.label}
        </span>
      </button>

      {isOpen && (
        <div
          className={`absolute right-0 mt-2 w-64 p-3 rounded-xl border shadow-xl z-50 text-xs space-y-2.5 ${popoverStyle}`}
        >
          <div className="flex items-center justify-between border-b border-inherit/20 pb-2">
            <span className="font-mono font-semibold uppercase tracking-wider text-[11px]">
              Typography
            </span>
            <span className="font-mono text-[10px] opacity-70">
              {readerFontOverride ? "Custom Override" : "Scenario Default"}
            </span>
          </div>

          <div className="space-y-1">
            <label
              htmlFor="reader-font-select"
              className="font-mono text-[11px] opacity-75 block"
            >
              Narration Font
            </label>
            <select
              id="reader-font-select"
              aria-label="Reader Narration Font"
              value={readerFontOverride ?? "default"}
              onChange={handleFontChange}
              className="w-full bg-zinc-950/60 border border-inherit/30 rounded-lg p-2 font-mono text-xs focus:outline-none focus:border-amber-500"
            >
              <option value="default">
                Scenario Default ({defaultFontDef.label})
              </option>
              {FONT_GENRE_CATEGORIES.map((category) => (
                <optgroup key={category} label={category}>
                  {NARRATION_FONTS_CATALOG.filter(
                    (f) => f.category === category,
                  ).map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
};
