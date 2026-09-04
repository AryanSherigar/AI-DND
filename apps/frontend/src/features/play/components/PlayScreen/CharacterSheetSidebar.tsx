import { usePlayStore } from "../../stores/play.store";

interface CharacterSheetSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function CharacterSheetSidebar({
  isOpen,
  onToggle,
}: CharacterSheetSidebarProps) {
  const playthrough = usePlayStore((s) => s.playthrough);
  const openWarningModal = usePlayStore((s) => s.openWarningModal);

  if (!playthrough) return null;

  return (
    <aside
      className={`fixed lg:relative top-0 right-0 h-full z-40 bg-stone-950/95 border-l border-stone-900 backdrop-blur-md transition-all duration-300 flex flex-col shrink-0 ${
        isOpen
          ? "w-80 opacity-100 translate-x-0"
          : "w-0 opacity-0 translate-x-full lg:translate-x-0 pointer-events-none"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-stone-900">
        <button
          onClick={onToggle}
          className="p-1 rounded text-stone-400 hover:text-stone-200 hover:bg-stone-900 transition-colors"
          title="Collapse Character Sheet"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>
        <div className="flex items-center gap-2.5">
          <h2 className="font-mono text-xs tracking-wider uppercase text-stone-400 font-medium">
            Character Sheet
          </h2>
          <svg
            className="w-5 h-5 text-stone-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
            />
          </svg>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scrollbar-minimal">
        {/* Character Card Banner */}
        <div className="p-4 rounded-xl bg-stone-900/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-stone-800 border border-stone-700/60 flex items-center justify-center text-stone-200 font-serif text-lg font-semibold shrink-0">
              {playthrough.character_name.charAt(0)}
            </div>
            <div>
              <div className="font-serif text-stone-100 font-semibold text-base leading-tight">
                {playthrough.character_name}
              </div>
            </div>
          </div>
        </div>

        {/* Setup Fields */}
        <div className="space-y-3">
          <h3 className="font-mono text-[11px] uppercase text-stone-400 tracking-wider font-medium">
            Player Setup Choices
          </h3>
          {playthrough.custom_fields.map((field) => (
            <div
              key={field.key}
              className="p-3.5 rounded-lg bg-stone-900/40 flex flex-col gap-1"
            >
              <span className="font-mono text-[11px] uppercase text-stone-400 tracking-wider">
                {field.label}
              </span>
              <span className="font-serif text-sm text-stone-200 font-medium">
                {field.value}
              </span>
            </div>
          ))}
        </div>

        {/* Edit Button */}
        <div className="pt-2">
          <button
            onClick={openWarningModal}
            className="w-full py-2.5 px-3 rounded-lg bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-xs transition-colors flex items-center justify-center gap-2 cursor-pointer"
          >
            <svg
              className="w-3.5 h-3.5 text-stone-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.75}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
            Edit Character Details
          </button>
        </div>
      </div>
    </aside>
  );
}
