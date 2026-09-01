import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePlayStore } from "../../../stores/play.store";

export function EndPlaythroughModal() {
  const navigate = useNavigate();
  const isOpen = usePlayStore((s) => s.is_end_modal_open);
  const closeModal = usePlayStore((s) => s.closeEndModal);
  const playthrough = usePlayStore((s) => s.playthrough);

  const [rating, setRating] = useState<number>(5);
  const [review, setReview] = useState<string>("");
  const [isSubmitted, setIsSubmitted] = useState<boolean>(false);

  if (!isOpen || !playthrough) return null;

  const totalTurns = playthrough.turns.length;

  const handleSubmitRating = () => {
    setIsSubmitted(true);
    setTimeout(() => {
      closeModal();
      navigate("/play");
    }, 1500);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-stone-950 border border-amber-900/40 rounded-2xl p-6 shadow-2xl space-y-6 animate-scale-up">
        {/* Header */}
        <div className="text-center space-y-1 border-b border-amber-900/20 pb-4">
          <div className="font-mono text-xs uppercase text-amber-500 tracking-widest font-bold">
            Journey Completed
          </div>
          <h3 className="font-serif text-2xl text-amber-100 font-bold">
            {playthrough.scenario_title}
          </h3>
          <p className="font-mono text-xs text-stone-400">
            Played by{" "}
            <span className="text-amber-300 font-semibold">
              {playthrough.character_name}
            </span>{" "}
            • {totalTurns} Turns Recorded
          </p>
        </div>

        {isSubmitted ? (
          <div className="p-6 rounded-xl bg-amber-950/40 border border-amber-500/40 text-center space-y-2">
            <svg
              className="w-10 h-10 text-amber-400 mx-auto animate-bounce"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            <h4 className="font-mono text-sm uppercase text-amber-200 font-bold">
              Thank You For Playing!
            </h4>
            <p className="font-serif text-xs text-stone-300">
              Returning to Discovery feed...
            </p>
          </div>
        ) : (
          <>
            {/* Star Rating */}
            <div className="space-y-2 text-center">
              <label className="font-mono text-xs text-amber-400/90 uppercase tracking-wider block">
                Rate This Scenario
              </label>
              <div className="flex items-center justify-center gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    className="text-2xl transition-transform hover:scale-125 focus:outline-none cursor-pointer"
                  >
                    <span
                      className={
                        star <= rating ? "text-amber-400" : "text-stone-700"
                      }
                    >
                      ★
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Review Comment Box */}
            <div className="space-y-1.5">
              <label className="font-mono text-xs text-stone-400 block">
                Write a Review (Optional)
              </label>
              <textarea
                rows={3}
                value={review}
                onChange={(e) => setReview(e.target.value)}
                placeholder="Share your experience playing this scenario..."
                className="w-full bg-stone-900 text-amber-100 font-serif text-sm p-3 rounded-lg border border-amber-900/30 focus:border-amber-500 focus:outline-none resize-none"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={closeModal}
                className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-xs rounded border border-stone-700 transition-colors cursor-pointer"
              >
                Keep Playing
              </button>
              <button
                type="button"
                onClick={handleSubmitRating}
                className="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 text-stone-950 font-mono text-xs font-bold rounded shadow-lg shadow-amber-500/20 transition-all cursor-pointer"
              >
                Submit & Exit
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
