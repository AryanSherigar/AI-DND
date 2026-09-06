import React from "react";
import { ArrowRightIcon } from "@/shared/components/icons/CleanIcons";
import { EnterNowButtonProps } from "./EnterNowButton.types";

const renderInnerCore = () => (
  <span className="relative flex items-center gap-3 px-8 py-4 rounded-full bg-[#0d0f14] text-white font-mono font-semibold text-base md:text-lg tracking-wider transition-colors duration-300 group-hover:bg-[#141822] shadow-[inset_0_1px_1px_rgba(255,255,255,0.25),inset_0_-1px_2px_rgba(0,0,0,0.8)] overflow-hidden">
    <span
      aria-hidden="true"
      className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/15 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full pointer-events-none"
    />
    <span>ENTER NOW</span>
    <ArrowRightIcon className="w-5 h-5 text-zinc-300 transition-all duration-300 ease-out group-hover:text-white group-hover:translate-x-1.5" />
  </span>
);

export const EnterNowButton: React.FC<EnterNowButtonProps> = ({
  onClick,
  className = "",
}) => {
  return (
    <div className={`relative inline-flex group ${className}`}>
      <span
        aria-hidden="true"
        className="absolute -inset-1.5 rounded-full bg-white opacity-20 blur-xl transition-all duration-500 group-hover:opacity-45 group-hover:blur-2xl group-hover:scale-105 pointer-events-none"
      />
      <button
        type="button"
        onClick={onClick}
        className="relative inline-flex items-center justify-center p-[2px] overflow-hidden rounded-full transition-transform duration-300 ease-out group-hover:scale-105 group-active:scale-95 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
      >
        <span
          aria-hidden="true"
          className="absolute -inset-[150%] animate-aurora-spin bg-[conic-gradient(from_0deg_at_50%_50%,rgba(255,255,255,0.95)_0%,rgba(255,255,255,0.2)_25%,transparent_50%,rgba(255,255,255,0.2)_75%,rgba(255,255,255,0.95)_100%)] pointer-events-none"
        />
        {renderInnerCore()}
      </button>
    </div>
  );
};
