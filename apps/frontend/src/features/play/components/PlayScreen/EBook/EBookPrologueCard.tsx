import { usePlayStore } from "../../../stores/play.store";
import { EBookPrologueCardProps } from "./ebook.types";

export function EBookPrologueCard({
  premise,
  characterName,
  onStartAction,
}: EBookPrologueCardProps) {
  const theme = usePlayStore((s) => s.ebook_theme);
  const isSepia = theme === "antique-sepia";

  const cardStyle = isSepia
    ? "bg-[#faf4e8]/80 border-[#d8c7a8] text-[#2c2217]"
    : "bg-zinc-950/80 border-zinc-800/80 text-zinc-200";

  const bannerStyle = isSepia
    ? "text-[#8c6b45] border-[#d8c7a8]"
    : "text-zinc-400 border-zinc-800";

  return (
    <article
      className={`p-6 md:p-8 rounded-2xl border shadow-sm my-6 transition-colors ${cardStyle}`}
    >
      <div className="flex items-center justify-between pb-4 border-b border-inherit/20 mb-5">
        <div
          className={`font-mono text-xs uppercase tracking-widest font-semibold flex items-center gap-2 ${bannerStyle}`}
        >
          <span>✦</span>
          <span>Prologue</span>
          <span>✦</span>
        </div>
        <span className="font-mono text-xs px-2.5 py-1 rounded-full border border-inherit/30 opacity-80">
          Chronicle of {characterName}
        </span>
      </div>

      <p className="font-serif text-lg md:text-xl leading-relaxed italic mb-6">
        "{premise}"
      </p>

      <div className="flex items-center justify-between pt-3 border-t border-inherit/20 text-xs font-mono opacity-80">
        <span>The chronicle begins with your choice.</span>
        <button
          type="button"
          onClick={onStartAction}
          className="hover:underline font-semibold cursor-pointer opacity-90 hover:opacity-100"
        >
          Begin First Action →
        </button>
      </div>
    </article>
  );
}
