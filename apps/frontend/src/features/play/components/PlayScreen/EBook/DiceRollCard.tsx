import { DiceRollCardProps } from "./ebook.types";
import { useEBookThemeTokens } from "./ebookTheme";

export function DiceRollCard({ roll }: DiceRollCardProps) {
  const tokens = useEBookThemeTokens();

  return (
    <div
      className={`my-3 rounded-xl border px-4 py-3 flex items-center justify-between font-mono ${tokens.cardBg}`}
    >
      <div className="flex items-center gap-2 text-sm">
        <span className="text-lg">🎲</span>
        <span>{roll.expression}</span>
      </div>
      <span className="text-lg font-bold">{roll.total}</span>
    </div>
  );
}
