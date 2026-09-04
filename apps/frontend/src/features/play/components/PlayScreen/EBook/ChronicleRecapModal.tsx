import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePlayStore } from "../../../stores/play.store";
import { ChronicleRecapModalProps } from "./ebook.types";

export function ChronicleRecapModal({
  isOpen,
  onClose,
}: ChronicleRecapModalProps) {
  const navigate = useNavigate();
  const playthrough = usePlayStore((s) => s.playthrough);
  const theme = usePlayStore((s) => s.ebook_theme);
  const isSepia = theme === "antique-sepia";

  const [rating, setRating] = useState<number>(5);
  const [review, setReview] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);
  const [isSubmitted, setIsSubmitted] = useState<boolean>(false);

  if (!isOpen || !playthrough) return null;

  const totalTurns = playthrough.turns.length;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSubmit = () => {
    setIsSubmitted(true);
    setTimeout(() => {
      onClose();
      navigate("/play");
    }, 1500);
  };

  const modalStyle = isSepia
    ? "bg-[#faf4e8] border-[#d8c7a8] text-[#2c2217]"
    : "bg-[#09090b] border-zinc-800 text-zinc-100 shadow-2xl shadow-black";

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div
        className={`w-full max-w-lg p-6 sm:p-8 rounded-2xl border shadow-2xl space-y-6 animate-scale-up ${modalStyle}`}
      >
        <header className="text-center space-y-1.5 border-b border-inherit/20 pb-4">
          <span className="font-mono text-xs uppercase tracking-widest opacity-60 font-semibold">
            The Chronicle Concluded
          </span>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold">
            {playthrough.scenario_title}
          </h2>
          <p className="font-mono text-xs opacity-75">
            An adventure of {playthrough.character_name} • {totalTurns} Chapters
            Recorded
          </p>
        </header>

        {isSubmitted ? (
          <div className="p-6 rounded-xl border border-inherit/30 text-center space-y-2 bg-inherit/10">
            <h3 className="font-mono text-sm uppercase font-bold">
              Your Chronicle Is Inscribed!
            </h3>
            <p className="font-serif text-xs opacity-80">
              Returning to Discovery feed...
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="p-4 rounded-xl border border-inherit/30 bg-inherit/10 text-xs font-serif italic leading-relaxed">
              "{playthrough.opening_premise}"
            </div>

            <div className="flex items-center justify-between font-mono text-xs">
              <span>Share this Chronicle:</span>
              <button
                type="button"
                onClick={handleCopyLink}
                className="px-3 py-1.5 rounded-lg border border-inherit/30 hover:bg-zinc-800/50 transition-colors cursor-pointer"
              >
                {copied ? "✓ Copied Link" : "📋 Copy Share Link"}
              </button>
            </div>

            <div className="space-y-2 text-center">
              <label className="font-mono text-xs uppercase tracking-wider block opacity-75">
                Rate This Tale
              </label>
              <div className="flex items-center justify-center gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    className="text-2xl hover:scale-125 transition-transform cursor-pointer"
                  >
                    <span
                      className={
                        star <= rating
                          ? isSepia
                            ? "text-[#2c2217]"
                            : "text-zinc-100"
                          : "opacity-20"
                      }
                    >
                      ★
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <textarea
              rows={3}
              value={review}
              onChange={(e) => setReview(e.target.value)}
              placeholder="Record your thoughts on this adventure..."
              className="w-full bg-transparent border border-inherit/30 rounded-xl p-3 text-sm font-serif focus:outline-none focus:border-zinc-500 resize-none"
            />

            <footer className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl border border-inherit/30 hover:bg-zinc-800/50 font-mono text-xs cursor-pointer"
              >
                Keep Reading
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                className={`px-5 py-2.5 rounded-xl font-mono text-xs font-bold shadow-md cursor-pointer transition-colors ${
                  isSepia
                    ? "bg-[#2c2217] hover:bg-[#433523] text-[#faf4e8]"
                    : "bg-zinc-100 hover:bg-white text-zinc-950"
                }`}
              >
                Inscribe & Exit
              </button>
            </footer>
          </div>
        )}
      </div>
    </div>
  );
}
