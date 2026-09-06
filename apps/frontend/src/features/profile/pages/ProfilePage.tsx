import React, { useState, useEffect } from "react";
import {
  useParams,
  useNavigate,
  useSearchParams,
  Navigate,
} from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useProfile } from "../hooks/useProfile";
import { ProfileHeader } from "../components/ProfileHeader";
import { EditProfileModal } from "../components/EditProfileModal";
import { CreationsTab } from "../components/tabs/CreationsTab";
import { CampaignsTab } from "../components/tabs/CampaignsTab";
import { BookmarksTab } from "../components/tabs/BookmarksTab";
import { ReviewsTab } from "../components/tabs/ReviewsTab";

type ProfileTab = "creations" | "campaigns" | "bookmarks" | "reviews";

const VALID_TABS: ProfileTab[] = [
  "creations",
  "campaigns",
  "bookmarks",
  "reviews",
];

const parseProfileTab = (tabParam: string | null): ProfileTab => {
  if (tabParam && (VALID_TABS as string[]).includes(tabParam)) {
    return tabParam as ProfileTab;
  }
  return "creations";
};

export const ProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<ProfileTab>(() =>
    parseProfileTab(searchParams.get("tab")),
  );
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  useEffect(() => {
    const nextTab = parseProfileTab(searchParams.get("tab"));
    setActiveTab(nextTab);
  }, [searchParams]);

  const handleTabChange = (newTab: ProfileTab) => {
    setActiveTab(newTab);
    setSearchParams({ tab: newTab });
  };

  const isOwner = Boolean(!id || (user && user.user_id === id));
  const isProfileEnabled = Boolean(id) || (!isAuthLoading && isAuthenticated);

  const {
    data: profile,
    isLoading,
    isError,
  } = useProfile(id || "me", {
    enabled: isProfileEnabled,
    currentUserId: user?.user_id,
  });

  // If visiting /profile without auth, redirect to login
  if (!id && !isAuthLoading && !isAuthenticated) {
    return <Navigate to="/login?redirect=/profile" replace />;
  }

  if (isAuthLoading || (isProfileEnabled && isLoading)) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 font-mono text-content-faint">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
        <span>Consulting the realm archives...</span>
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center space-y-4 p-6 text-center text-content">
        <div className="text-4xl">📜</div>
        <h1 className="font-display text-3xl font-bold text-white">
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
    <div className="custom-scrollbar flex-1 overflow-y-auto text-content selection:bg-accent/30">
      <main className="mx-auto max-w-7xl space-y-8 px-4 pb-20 pt-20 md:px-8">
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
              onClick={() => handleTabChange("creations")}
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
                onClick={() => handleTabChange("campaigns")}
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
                onClick={() => handleTabChange("bookmarks")}
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
              onClick={() => handleTabChange("reviews")}
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
