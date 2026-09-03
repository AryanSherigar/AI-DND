import React, { useEffect } from "react";

export interface ToastProps {
  message: string;
  type?: "error" | "success" | "info";
  onClose: () => void;
  durationMs?: number;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type = "error",
  onClose,
  durationMs = 5000,
}) => {
  useEffect(() => {
    const timer = setTimeout(onClose, durationMs);
    return () => clearTimeout(timer);
  }, [onClose, durationMs]);

  const styles = {
    error: "border-red-500/50 bg-red-950/90 text-red-200 shadow-red-950/50",
    success:
      "border-emerald-500/50 bg-emerald-950/90 text-emerald-200 shadow-emerald-950/50",
    info: "border-amber-500/50 bg-amber-950/90 text-amber-200 shadow-amber-950/50",
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-2xl font-mono text-xs animate-in fade-in slide-in-from-bottom-4 duration-200">
      <div className={`flex items-center gap-3 ${styles[type]}`}>
        <span>{type === "error" ? "⚠️" : type === "success" ? "✓" : "ℹ"}</span>
        <span className="max-w-xs sm:max-w-sm truncate">{message}</span>
        <button
          onClick={onClose}
          className="text-zinc-400 hover:text-zinc-100 transition-colors ml-2 font-bold"
        >
          ✕
        </button>
      </div>
    </div>
  );
};
