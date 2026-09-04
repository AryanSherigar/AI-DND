import React, { useState } from "react";
import { UserProfile } from "../types/profile.types";
import {
  AVATAR_PRESETS,
  BANNER_PRESETS,
  DEFAULT_AVATAR,
  DEFAULT_BANNER,
} from "../constants/profilePresets";
import { uploadAvatar, uploadBanner } from "../api/profileApi";
import { useUpdateProfile } from "../hooks/useUpdateProfile";

export interface EditProfileModalProps {
  profile: UserProfile;
  isOpen: boolean;
  onClose: () => void;
}

type TabType = "identity" | "avatar" | "banner";

export const EditProfileModal: React.FC<EditProfileModalProps> = ({
  profile,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("identity");
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio || "");
  const [avatarUrl, setAvatarUrl] = useState(
    profile.avatar_url || DEFAULT_AVATAR,
  );
  const [bannerUrl, setBannerUrl] = useState(
    profile.banner_url || DEFAULT_BANNER,
  );
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const updateMutation = useUpdateProfile();

  if (!isOpen) return null;

  const handleAvatarFileUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setErrorMessage(null);
    try {
      const url = await uploadAvatar(file);
      setAvatarUrl(url);
    } catch {
      setErrorMessage(
        "Failed to upload avatar. Allowed: JPEG, PNG, WebP < 5MB.",
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleBannerFileUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setErrorMessage(null);
    try {
      const url = await uploadBanner(file);
      setBannerUrl(url);
    } catch {
      setErrorMessage(
        "Failed to upload banner. Allowed: JPEG, PNG, WebP < 5MB.",
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    if (!displayName.trim()) {
      setErrorMessage("Display name cannot be empty.");
      return;
    }

    try {
      await updateMutation.mutateAsync({
        display_name: displayName.trim(),
        bio: bio.trim() || null,
        avatar_url: avatarUrl,
        banner_url: bannerUrl,
      });
      onClose();
    } catch {
      setErrorMessage("Failed to save profile changes. Please try again.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-2xl border border-amber-500/30 bg-zinc-950 p-6 md:p-8 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <h2 className="font-fell-sc text-2xl font-bold text-amber-300">
            Edit Adventurer Chronicle
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white transition-colors text-xl font-mono"
          >
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-zinc-800 my-5 gap-2 font-mono text-xs uppercase tracking-wider">
          <button
            type="button"
            onClick={() => setActiveTab("identity")}
            className={`pb-2 px-3 border-b-2 transition-all ${
              activeTab === "identity"
                ? "border-amber-400 text-amber-300 font-bold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Identity
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("avatar")}
            className={`pb-2 px-3 border-b-2 transition-all ${
              activeTab === "avatar"
                ? "border-amber-400 text-amber-300 font-bold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Avatar Portrait
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("banner")}
            className={`pb-2 px-3 border-b-2 transition-all ${
              activeTab === "banner"
                ? "border-amber-400 text-amber-300 font-bold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Banner Landscape
          </button>
        </div>

        {errorMessage && (
          <div className="mb-4 rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-xs font-mono text-rose-300">
            {errorMessage}
          </div>
        )}

        {/* Tab Contents */}
        <form onSubmit={handleSave} className="space-y-6">
          {activeTab === "identity" && (
            <div className="space-y-4">
              <div>
                <label className="block font-mono text-xs uppercase tracking-wider text-zinc-400 mb-1.5">
                  Adventurer Name
                </label>
                <input
                  type="text"
                  maxLength={255}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-white focus:border-amber-400 focus:outline-none"
                  placeholder="Enter your name..."
                  required
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="font-mono text-xs uppercase tracking-wider text-zinc-400">
                    Chronicle Bio / Lore Tagline
                  </label>
                  <span className="font-mono text-xs text-zinc-500">
                    {bio.length}/500
                  </span>
                </div>
                <textarea
                  rows={4}
                  maxLength={500}
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-white focus:border-amber-400 focus:outline-none"
                  placeholder="Inscribe your background, favorite roles, or adventurer motto..."
                />
              </div>
            </div>
          )}

          {activeTab === "avatar" && (
            <div className="space-y-4">
              <label className="block font-mono text-xs uppercase tracking-wider text-zinc-400 mb-2">
                Choose a Dark Fantasy Portrait Preset
              </label>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                {AVATAR_PRESETS.map((preset) => (
                  <button
                    type="button"
                    key={preset.id}
                    onClick={() => setAvatarUrl(preset.url)}
                    className={`flex flex-col items-center gap-1.5 p-2 rounded-xl border transition-all ${
                      avatarUrl === preset.url
                        ? "border-amber-400 bg-amber-400/10 shadow-[0_0_12px_rgba(212,175,106,0.3)]"
                        : "border-zinc-800 bg-zinc-900/60 hover:border-zinc-700"
                    }`}
                  >
                    <div className="h-12 w-12 rounded-full overflow-hidden border border-zinc-700">
                      <img
                        src={preset.url}
                        alt={preset.name}
                        className="h-full w-full object-cover"
                      />
                    </div>
                    <span className="font-mono text-[10px] text-zinc-300 truncate w-full text-center">
                      {preset.name.split(" ")[0]}
                    </span>
                  </button>
                ))}
              </div>

              <div className="pt-3 border-t border-zinc-800">
                <label className="block font-mono text-xs uppercase tracking-wider text-zinc-400 mb-2">
                  Or Upload Custom Portrait (JPEG, PNG, WebP &lt; 5MB)
                </label>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleAvatarFileUpload}
                  disabled={isUploading}
                  className="block w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                />
              </div>
            </div>
          )}

          {activeTab === "banner" && (
            <div className="space-y-4">
              <label className="block font-mono text-xs uppercase tracking-wider text-zinc-400 mb-2">
                Choose a Realm Banner Preset
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {BANNER_PRESETS.map((preset) => (
                  <button
                    type="button"
                    key={preset.id}
                    onClick={() => setBannerUrl(preset.url)}
                    className={`relative overflow-hidden rounded-xl border text-left transition-all ${
                      bannerUrl === preset.url
                        ? "border-amber-400 shadow-[0_0_15px_rgba(212,175,106,0.3)]"
                        : "border-zinc-800 hover:border-zinc-700 opacity-70 hover:opacity-100"
                    }`}
                  >
                    <div className="h-20 w-full overflow-hidden">
                      <img
                        src={preset.url}
                        alt={preset.name}
                        className="h-full w-full object-cover"
                      />
                    </div>
                    <div className="p-2 bg-zinc-900/90">
                      <span className="font-mono text-xs text-white font-bold block">
                        {preset.name}
                      </span>
                      <span className="font-sans text-[11px] text-zinc-400">
                        {preset.description}
                      </span>
                    </div>
                  </button>
                ))}
              </div>

              <div className="pt-3 border-t border-zinc-800">
                <label className="block font-mono text-xs uppercase tracking-wider text-zinc-400 mb-2">
                  Or Upload Custom Banner (JPEG, PNG, WebP &lt; 5MB)
                </label>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleBannerFileUpload}
                  disabled={isUploading}
                  className="block w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                />
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 border-t border-zinc-800 pt-5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-300 font-mono text-xs hover:bg-zinc-900 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={updateMutation.isPending || isUploading}
              className="px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 font-mono text-xs font-bold shadow-lg transition-all disabled:opacity-50"
            >
              {updateMutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
