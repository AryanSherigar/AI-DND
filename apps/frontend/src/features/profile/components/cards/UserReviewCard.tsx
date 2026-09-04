import React from "react";
import { Link } from "react-router-dom";
import { UserReviewSummary } from "../../types/profile.types";

export interface UserReviewCardProps {
  review: UserReviewSummary;
}

export const UserReviewCard: React.FC<UserReviewCardProps> = ({ review }) => {
  const formattedDate = new Date(review.created_at).toLocaleDateString(
    undefined,
    {
      year: "numeric",
      month: "short",
      day: "numeric",
    },
  );

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 transition-all hover:border-amber-500/30 hover:bg-zinc-900/80 shadow-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800 pb-3 mb-3">
        <Link
          to={`/scenario/${review.scenario_id}`}
          className="font-fell-sc text-lg font-bold text-white hover:text-amber-300 transition-colors"
        >
          {review.scenario_title}
        </Link>

        <div className="flex items-center gap-3">
          {/* Star Rating */}
          <div className="flex items-center text-amber-400 font-mono text-sm">
            {"★".repeat(review.rating)}
            {"☆".repeat(Math.max(0, 5 - review.rating))}
          </div>
          <span className="font-mono text-xs text-zinc-500">
            {formattedDate}
          </span>
        </div>
      </div>

      <p className="font-serif italic text-sm text-zinc-300 leading-relaxed">
        {review.review_text
          ? `“${review.review_text}”`
          : "No written comment provided."}
      </p>
    </div>
  );
};
