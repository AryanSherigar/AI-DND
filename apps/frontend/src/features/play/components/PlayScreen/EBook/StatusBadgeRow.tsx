import { StatusBadgeRowProps } from "./ebook.types";
import { useEBookThemeTokens } from "./ebookTheme";

export function StatusBadgeRow({ conditions }: StatusBadgeRowProps) {
  const tokens = useEBookThemeTokens();

  if (conditions.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-4 py-1.5 font-mono text-[10px] uppercase tracking-wider">
      {conditions.map((condition) => (
        <span
          key={condition}
          className={`px-2 py-0.5 rounded-full border ${tokens.badgeBg}`}
        >
          {condition}
        </span>
      ))}
    </div>
  );
}
