import React, { useState } from "react";
import { IconStar, IconStarFilled, IconLock } from "@tabler/icons-react";
import { ScenarioReviewResponse } from "../../types/scenario";
import { SectionHeading } from "./SectionHeading";

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

const Stars: React.FC<{ value: number; size?: number }> = ({
  value,
  size = 14,
}) => (
  <span className="flex items-center gap-0.5 text-accent">
    {[1, 2, 3, 4, 5].map((star) =>
      star <= value ? (
        <IconStarFilled key={star} size={size} />
      ) : (
        <IconStar key={star} size={size} className="text-content-faint" />
      ),
    )}
  </span>
);

export const ScenarioReviewsSection: React.FC<ScenarioReviewsSectionProps> = ({
  reviews,
  totalReviews,
  averageRating,
  canReview,
  onSubmitReview,
  isSubmittingReview,
}) => {
  const [rating, setRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState(false);

  const handleSubmit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault();
    setErrorMsg(null);
    try {
      await onSubmitReview({ rating, comment: comment.trim() || undefined });
      setSuccessMsg(true);
      setComment("");
      setTimeout(() => setSuccessMsg(false), 4000);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Couldn't submit — you need at least 10 turns played.",
      );
    }
  };

  return (
    <section>
      <SectionHeading
        label="Reviews"
        trailing={
          <div className="flex items-center gap-2 font-mono text-xs text-content-faint">
            <span className="text-lg font-semibold text-content">
              {averageRating ? averageRating.toFixed(1) : "—"}
            </span>
            <Stars value={Math.round(averageRating)} />
            <span>({totalReviews})</span>
          </div>
        }
      />

      {canReview ? (
        <form
          onSubmit={handleSubmit}
          className="mb-6 rounded-xl border border-border-subtle bg-surface p-4"
        >
          <div className="flex items-center justify-between">
            <span className="font-sans text-sm text-content-muted">
              Rate this scenario
            </span>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  aria-label={`${star} stars`}
                  className="text-accent transition-transform hover:scale-110 focus-visible:outline-none"
                >
                  {star <= (hoverRating || rating) ? (
                    <IconStarFilled size={20} />
                  ) : (
                    <IconStar size={20} className="text-content-faint" />
                  )}
                </button>
              ))}
            </div>
          </div>

          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="What worked, what didn't — the narrative, the choices, the pacing."
            rows={3}
            className="mt-3 w-full resize-none rounded-lg border border-border-subtle bg-surface-inset p-3 font-sans text-sm text-content placeholder:text-content-faint focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
          />

          {errorMsg && (
            <p className="mt-2 rounded-md border border-danger/40 bg-danger/10 px-2.5 py-1.5 font-sans text-xs text-danger">
              {errorMsg}
            </p>
          )}
          {successMsg && (
            <p className="mt-2 rounded-md border border-success/40 bg-success/10 px-2.5 py-1.5 font-sans text-xs text-success">
              Review posted.
            </p>
          )}

          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={isSubmittingReview}
              className="rounded-full bg-content px-5 py-2 font-sans text-sm font-semibold text-surface transition hover:bg-white disabled:opacity-50"
            >
              {isSubmittingReview ? "Posting…" : "Post review"}
            </button>
          </div>
        </form>
      ) : (
        <p className="mb-6 flex items-center gap-2 font-sans text-sm text-content-faint">
          <IconLock size={15} />
          Play 10 turns of this scenario to leave a review.
        </p>
      )}

      {reviews.length === 0 ? (
        <p className="font-sans text-sm text-content-faint">
          No reviews yet.
        </p>
      ) : (
        <ul className="divide-y divide-border-subtle">
          {reviews.map((rev) => (
            <li key={rev.review_id} className="py-4 first:pt-0">
              <div className="flex items-center justify-between gap-3">
                <span className="font-sans text-sm font-medium text-content">
                  {rev.user_display_name}
                </span>
                <div className="flex items-center gap-2">
                  <Stars value={rev.rating} size={12} />
                  <span className="font-mono text-xs text-content-faint">
                    {new Date(rev.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              {rev.comment && (
                <p className="mt-1.5 font-sans text-sm leading-relaxed text-content-muted">
                  {rev.comment}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};
