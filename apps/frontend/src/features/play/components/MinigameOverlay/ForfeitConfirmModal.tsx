import { ForfeitConfirmModalProps } from "./ForfeitConfirmModal.types";

export function ForfeitConfirmModal({
  isOpen,
  onConfirm,
  onCancel,
}: ForfeitConfirmModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="absolute inset-0 z-30 flex items-center justify-center bg-black/80 p-6 text-center text-white"
      role="dialog"
      aria-modal="true"
      aria-labelledby="forfeit-dialog-title"
    >
      <div className="max-w-md space-y-4 rounded border border-white/20 bg-zinc-950 p-6 shadow-2xl">
        <h3
          id="forfeit-dialog-title"
          className="text-lg font-semibold text-white"
        >
          Forfeit Challenge?
        </h3>
        <p className="text-sm text-zinc-300">
          Conceding will end this encounter immediately as a timeout. The story
          will continue with the scenario&apos;s timeout consequences.
        </p>
        <div className="flex justify-center gap-3 pt-2">
          <button
            type="button"
            className="rounded bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 transition-colors hover:bg-zinc-700"
            onClick={onCancel}
          >
            Keep Playing
          </button>
          <button
            type="button"
            className="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-500"
            onClick={onConfirm}
          >
            Yes, Forfeit
          </button>
        </div>
      </div>
    </div>
  );
}
