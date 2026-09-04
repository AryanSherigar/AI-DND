import React, { useState } from "react";
import { useParams, useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { Header } from "@/shared/components/layout/Header";
import { useProfile } from "../hooks/useProfile";
import { ProfileHeader } from "../components/ProfileHeader";
import { EditProfileModal } from "../components/EditProfileModal";
import { CreationsTab } from "../components/tabs/CreationsTab";
import { CampaignsTab } from "../components/tabs/CampaignsTab";
import { BookmarksTab } from "../components/tabs/BookmarksTab";
import { ReviewsTab } from "../components/tabs/ReviewsTab";

type ProfileTab = "creations" | "campaigns" | "bookmarks" | "reviews";

export const ProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<ProfileTab>("creations");
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const isOwner = Boolean(!id || (user && user.user_id === id));
  const { data: profile, isLoading, isError } = useProfile(id || "me");

  // If visiting /profile without auth, redirect to login
  if (!id && !isAuthLoading && !isAuthenticated) {
    return <Navigate to="/login?redirect=/profile" replace />;
  }

  if (isLoading || isAuthLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center text-zinc-400 font-mono gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
        <span>Consulting the realm archives...</span>
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 text-center space-y-4">
        <div className="text-4xl">📜</div>
        <h1 className="font-fell-sc text-3xl font-bold text-white">
          Adventurer Not Found
        </h1>
        <p className="font-mono text-sm text-zinc-400 max-w-md">
          The requested chronicle or adventurer could not be found in the realm
          archives.
        </p>
        <button
          onClick={() => navigate("/discover")}
          className="rounded-xl bg-zinc-900 border border-zinc-800 px-6 py-3 font-mono text-sm text-amber-300 hover:bg-zinc-800 transition-colors"
        >
          ← Return to Discovery Feed
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 selection:bg-amber-500/30 selection:text-amber-200 pb-20">
      <Header />

      <main className="max-w-7xl mx-auto px-4 md:px-8 pt-24 space-y-8">
        {/* Profile Hero with Stats */}
        <ProfileHeader
          profile={profile}
          isOwner={isOwner}
          onEditClick={() => setIsEditModalOpen(true)}
        />

        {/* Tab Navigation Hub */}
        <div className="border-b border-zinc-800/80">
          <nav className="flex space-x-6 font-mono text-sm tracking-wider">
            <button
              onClick={() => setActiveTab("creations")}
              className={`pb-4 px-1 border-b-2 font-bold transition-all ${
                activeTab === "creations"
                  ? "border-amber-400 text-amber-300 shadow-[0_2px_10px_rgba(212,175,106,0.3)]"
                  : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
              }`}
            >
              Creations
            </button>

            {isOwner && (
              <button
                onClick={() => setActiveTab("campaigns")}
                className={`pb-4 px-1 border-b-2 font-bold transition-all ${
                  activeTab === "campaigns"
                    ? "border-amber-400 text-amber-300 shadow-[0_2px_10px_rgba(212,175,106,0.3)]"
                    : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
                }`}
              >
                Campaigns
              </button>
            )}

            {isOwner && (
              <button
                onClick={() => setActiveTab("bookmarks")}
                className={`pb-4 px-1 border-b-2 font-bold transition-all ${
                  activeTab === "bookmarks"
                    ? "border-amber-400 text-amber-300 shadow-[0_2px_10px_rgba(212,175,106,0.3)]"
                    : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
                }`}
              >
                Bookmarks
              </button>
            )}

            <button
              onClick={() => setActiveTab("reviews")}
              className={`pb-4 px-1 border-b-2 font-bold transition-all ${
                activeTab === "reviews"
                  ? "border-amber-400 text-amber-300 shadow-[0_2px_10px_rgba(212,175,106,0.3)]"
                  : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
              }`}
            >
              Reviews
            </button>
          </nav>
        </div>

        {/* Active Tab Panel */}
        <div>
          {activeTab === "creations" && (
            <CreationsTab userId={profile.user_id} isOwner={isOwner} />
          )}
          {isOwner && activeTab === "campaigns" && <CampaignsTab />}
          {isOwner && activeTab === "bookmarks" && <BookmarksTab />}
          {activeTab === "reviews" && <ReviewsTab userId={profile.user_id} />}
        </div>
      </main>

      {/* Edit Profile Modal */}
      {isOwner && (
        <EditProfileModal
          profile={profile}
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
        />
      )}
    </div>
  );
};
