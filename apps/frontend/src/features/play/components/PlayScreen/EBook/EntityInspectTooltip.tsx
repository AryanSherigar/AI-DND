import { useEffect, useRef } from "react";
import { usePlayStore } from "../../../stores/play.store";
import { EntityInspectTooltipProps } from "./ebook.types";

export function EntityInspectTooltip({
  entity,
  anchorRect,
  onClose,
}: EntityInspectTooltipProps) {
  const theme = usePlayStore((s) => s.ebook_theme);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        tooltipRef.current &&
        !tooltipRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [onClose]);

  if (!entity || !anchorRect) return null;

  const top = Math.min(
    window.innerHeight - 200,
    Math.max(16, anchorRect.bottom + 8),
  );
  const left = Math.min(
    window.innerWidth - 300,
    Math.max(16, anchorRect.left - 40),
  );

  const isSepia = theme === "antique-sepia";
  const bgClass = isSepia
    ? "bg-[#f5ebd7] text-[#2c2217] border-[#d8c7a8] shadow-lg shadow-amber-950/10"
    : "bg-[#09090b] text-zinc-100 border-zinc-800 shadow-2xl shadow-black";

  return (
    <div
      ref={tooltipRef}
      style={{ top: `${top}px`, left: `${left}px` }}
      className={`fixed z-50 w-72 max-w-[90vw] p-3.5 rounded-xl border shadow-xl backdrop-blur-md text-xs transition-all animate-fade-in ${bgClass}`}
    >
      <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-inherit/20">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-serif font-bold text-sm truncate">
            {entity.name}
          </span>
          <span
            className={`px-1.5 py-0.5 rounded font-mono text-[9px] uppercase tracking-wider font-medium ${
              isSepia
                ? "bg-[#e2d5be]/60 text-[#2c2217]"
                : "bg-zinc-800 text-zinc-300 border border-zinc-700/60"
            }`}
          >
            {entity.category}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded opacity-60 hover:opacity-100 transition-opacity cursor-pointer"
          aria-label="Close tooltip"
        >
          ✕
        </button>
      </div>
      <p className="font-serif leading-relaxed line-clamp-4">
        {entity.summary}
      </p>
    </div>
  );
}
