import { useState, ChangeEvent } from "react";
import { usePlayStore } from "../../../stores/play.store";

export function EBookAudioControl() {
  const [isOpen, setIsOpen] = useState(false);
  const theme = usePlayStore((s) => s.ebook_theme);
  const isMuted = usePlayStore((s) => s.is_audio_muted);
  const volume = usePlayStore((s) => s.audio_volume);
  const activeMood = usePlayStore((s) => s.active_mood);
  const toggleMute = usePlayStore((s) => s.toggleAudioMute);
  const setVolume = usePlayStore((s) => s.setAudioVolume);

  const isSepia = theme === "antique-sepia";

  const handleToggleMute = () => {
    toggleMute();
  };

  const handleVolumeChange = (event: ChangeEvent<HTMLInputElement>) => {
    const newVol = parseFloat(event.target.value);
    setVolume(newVol);
  };

  const handleTogglePopover = () => {
    setIsOpen((prev) => !prev);
  };

  const speakerIcon = isMuted ? "🔇" : volume < 0.4 ? "🔉" : "🔊";
  const moodLabel = activeMood
    ? activeMood.charAt(0).toUpperCase() + activeMood.slice(1)
    : "Ambient";

  const popoverStyle = isSepia
    ? "bg-[#faf4e8] border-[#d8c7a8] text-[#2c2217]"
    : "bg-zinc-900 border-zinc-700 text-zinc-200";

  return (
    <div className="relative flex items-center">
      <div className="flex items-center rounded-xl border border-inherit/20 overflow-hidden font-mono text-xs">
        <button
          type="button"
          onClick={handleToggleMute}
          className="p-1.5 px-2 hover:bg-zinc-800/40 flex items-center gap-1 cursor-pointer transition-colors"
          title={
            isMuted
              ? "Unmute soundtrack"
              : `Soundtrack (${moodLabel}) — Click to mute`
          }
        >
          <span>{speakerIcon}</span>
          <span className="hidden sm:inline">{moodLabel}</span>
        </button>

        <button
          type="button"
          onClick={handleTogglePopover}
          className="p-1.5 px-1.5 hover:bg-zinc-800/40 border-l border-inherit/20 cursor-pointer text-[10px]"
          title="Adjust soundtrack volume"
        >
          ⚙️
        </button>
      </div>

      {isOpen && (
        <div
          className={`absolute right-0 top-full mt-2 p-3 rounded-xl border shadow-xl flex flex-col gap-2 z-50 w-44 backdrop-blur-md transition-all ${popoverStyle}`}
        >
          <div className="flex justify-between items-center text-[11px] font-mono">
            <span>Soundtrack</span>
            <span>{isMuted ? "Muted" : `${Math.round(volume * 100)}%`}</span>
          </div>

          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-zinc-700 rounded-lg"
          />

          <div className="text-[10px] opacity-70 font-mono flex items-center gap-1 mt-0.5">
            <span>Mood:</span>
            <span className="font-semibold text-emerald-400 capitalize">
              {activeMood}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
