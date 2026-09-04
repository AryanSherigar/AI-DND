import React from "react";
import { useUserReviews } from "../../hooks/useUserReviews";
import { UserReviewCard } from "../cards/UserReviewCard";

export interface ReviewsTabProps {
  userId: string;
}

export const ReviewsTab: React.FC<ReviewsTabProps> = ({ userId }) => {
  const { data: reviews, isLoading, isError } = useUserReviews(userId);

  if (isLoading) {
    return (
      <div className="py-16 text-center font-mono text-zinc-400">
        Fetching traveler chronicles and reviews...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-16 text-center font-mono text-rose-400">
        Failed to load reviews from the archives.
      </div>
    );
  }

  const items = reviews || [];

  return (
    <div className="space-y-6">
      <div className="font-mono text-xs uppercase tracking-wider text-zinc-400">
        Authored Reviews ({items.length})
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 p-12 text-center">
          <p className="font-serif italic text-zinc-400">
            No reviews have been penned by this adventurer yet.
          </p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {items.map((review) => (
            <UserReviewCard key={review.review_id} review={review} />
          ))}
        </div>
      )}
    </div>
  );
};
