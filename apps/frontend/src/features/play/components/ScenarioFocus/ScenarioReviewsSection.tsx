import React, { useState } from "react";
import { ScenarioReviewResponse } from "../../types/scenario";

interface ScenarioReviewsSectionProps {
  reviews: ScenarioReviewResponse[];
  totalReviews: number;
  averageRating: number;
  canReview: boolean;
  onSubmitReview: (data: {
    rating: number;
    comment?: string;
  }) => Promise<unknown>;
  isSubmittingReview: boolean;
}

export const ScenarioReviewsSection: React.FC<ScenarioReviewsSectionProps> = ({
  reviews,
  totalReviews,
  averageRating,
  canReview,
  onSubmitReview,
  isSubmittingReview,
}) => {
  const [rating, setRating] = useState<number>(5);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [comment, setComment] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await onSubmitReview({ rating, comment: comment.trim() || undefined });
      setSuccessMsg(true);
      setComment("");
      setTimeout(() => setSuccessMsg(false), 4000);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to submit review. Ensure you have played >= 10 turns.";
      setErrorMsg(msg);
    }
  };

  const renderStars = (count: number) => {
    return (
      <div className="flex items-center gap-0.5 text-amber-400">
        {[1, 2, 3, 4, 5].map((star) => (
          <span key={star} className="text-base">
            {star <= count ? "★" : "☆"}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 md:p-8 shadow-xl space-y-6">
      {/* Header & Overall Rating summary */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-zinc-800 pb-4 gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">⭐</span>
          <h2 className="font-fell-sc text-2xl font-bold text-amber-200/90">
            Player Reviews & Ratings
          </h2>
        </div>
        <div className="flex items-center gap-3 font-mono">
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-extrabold text-white">
              {averageRating ? averageRating.toFixed(1) : "0.0"}
            </span>
            <span className="text-sm text-zinc-500">/ 5</span>
          </div>
          {renderStars(Math.round(averageRating))}
          <span className="text-xs text-zinc-400">
            ({totalReviews} reviews)
          </span>
        </div>
      </div>

      {/* Review Submission Box */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-5 space-y-4">
        {canReview ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <span className="font-mono text-sm font-bold text-zinc-200">
                Leave your Adventurer's Review:
              </span>
              {/* Interactive Star Picker */}
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                    className="text-2xl text-amber-400 transition-transform hover:scale-125 focus:outline-none"
                  >
                    {star <= (hoverRating || rating) ? "★" : "☆"}
                  </button>
                ))}
              </div>
            </div>

            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Share your thoughts on the narrative, encounters, and choices in this scenario..."
              rows={3}
              className="w-full rounded-xl border border-zinc-800 bg-zinc-900 p-3 font-sans text-sm text-zinc-200 placeholder-zinc-500 focus:border-emerald-500 focus:outline-none"
            />

            {errorMsg && (
              <div className="rounded-md border border-red-500/30 bg-red-950/50 p-2.5 font-mono text-xs text-red-300">
                {errorMsg}
              </div>
            )}

            {successMsg && (
              <div className="rounded-md border border-emerald-500/30 bg-emerald-950/50 p-2.5 font-mono text-xs text-emerald-300">
                ✓ Review submitted successfully!
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isSubmittingReview}
                className="rounded-xl bg-emerald-500 px-5 py-2.5 font-sans font-bold text-zinc-950 shadow-md transition-all hover:bg-emerald-400 disabled:opacity-50"
              >
                {isSubmittingReview ? "Submitting..." : "Post Review"}
              </button>
            </div>
          </form>
        ) : (
          <div className="flex items-center gap-3 p-2 font-mono text-xs text-zinc-400">
            <span className="text-lg">🔒</span>
            <span>
              <strong className="text-zinc-200">Review Access Locked:</strong>{" "}
              You must complete at least <strong>10 turns</strong> in a
              playthrough of this scenario to leave a review.
            </span>
          </div>
        )}
      </div>

      {/* Reviews List */}
      <div className="space-y-3">
        {reviews.length === 0 ? (
          <div className="p-6 text-center font-mono text-sm text-zinc-500">
            No reviews yet. Be the first adventurer to complete 10 turns and
            rate this scenario!
          </div>
        ) : (
          reviews.map((rev) => (
            <div
              key={rev.review_id}
              className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-4 space-y-2"
            >
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="font-bold text-zinc-200">
                  {rev.user_display_name}
                </span>
                <div className="flex items-center gap-3">
                  {renderStars(rev.rating)}
                  <span className="text-zinc-500">
                    {new Date(rev.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              {rev.comment && (
                <p className="text-sm font-sans text-zinc-300 leading-relaxed">
                  {rev.comment}
                </p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
