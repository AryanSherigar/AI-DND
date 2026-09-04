import React from "react";
import { UserProfile } from "../types/profile.types";
import { DEFAULT_AVATAR, DEFAULT_BANNER } from "../constants/profilePresets";
import { ProfileStatsRibbon } from "./ProfileStatsRibbon";

export interface ProfileHeaderProps {
  profile: UserProfile;
  isOwner: boolean;
  onEditClick: () => void;
}

export const ProfileHeader: React.FC<ProfileHeaderProps> = ({
  profile,
  isOwner,
  onEditClick,
}) => {
  const bannerImage = profile.banner_url || DEFAULT_BANNER;
  const avatarImage = profile.avatar_url || DEFAULT_AVATAR;

  const formattedDate = new Date(profile.created_at).toLocaleDateString(
    undefined,
    {
      year: "numeric",
      month: "long",
    },
  );

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-amber-500/20 bg-zinc-950 shadow-2xl">
      {/* Banner Cover */}
      <div className="relative aspect-[21/7] w-full overflow-hidden md:aspect-[24/7]">
        <img
          src={bannerImage}
          alt={`${profile.display_name}'s banner`}
          className="h-full w-full object-cover opacity-75 transition-transform duration-700 hover:scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-r from-zinc-950/80 via-transparent to-zinc-950/80" />
      </div>

      {/* Profile Details Container */}
      <div className="relative z-10 -mt-16 px-6 pb-8 md:-mt-20 md:px-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          {/* Avatar and Identity */}
          <div className="flex flex-col sm:flex-row items-center sm:items-end gap-5 text-center sm:text-left">
            <div className="relative group">
              <div className="h-28 w-28 md:h-32 md:w-32 rounded-full overflow-hidden border-2 border-amber-500/60 bg-zinc-900 shadow-[0_0_25px_rgba(212,175,106,0.3)] shrink-0">
                <img
                  src={avatarImage}
                  alt={profile.display_name}
                  className="h-full w-full object-cover"
                />
              </div>
              {isOwner && (
                <button
                  onClick={onEditClick}
                  aria-label="Edit Profile Avatar"
                  className="absolute inset-0 rounded-full bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity text-white text-xs font-mono"
                >
                  Change
                </button>
              )}
            </div>

            <div className="space-y-1.5 max-w-xl">
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2.5">
                <h1 className="font-fell-sc text-3xl font-extrabold text-white md:text-4xl drop-shadow-md">
                  {profile.display_name}
                </h1>
                {isOwner && (
                  <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-400">
                    YOU
                  </span>
                )}
              </div>

              <p className="font-serif italic text-sm text-zinc-300 line-clamp-2">
                {profile.bio || "No chronicle inscribed yet."}
              </p>

              <p className="font-mono text-xs text-zinc-500">
                Adventurer since {formattedDate}
              </p>
            </div>
          </div>

          {/* Edit Profile Action */}
          {isOwner && (
            <button
              onClick={onEditClick}
              className="px-5 py-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 font-mono text-sm tracking-wider shadow-[0_0_15px_rgba(212,175,106,0.15)] transition-all shrink-0 self-center sm:self-end"
            >
              ✦ Edit Chronicle
            </button>
          )}
        </div>

        {/* Stats Ribbon */}
        <div className="mt-8 pt-6 border-t border-zinc-800/80">
          <ProfileStatsRibbon stats={profile.stats} />
        </div>
      </div>
    </div>
  );
};
