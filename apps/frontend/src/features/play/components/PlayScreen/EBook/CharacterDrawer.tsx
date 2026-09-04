import { useEffect, useState } from "react";
import { MasterEntity } from "../../../types/play.types";
import { CharacterDrawerProps, CharacterDrawerTab } from "./ebook.types";
import { useEBookThemeTokens } from "./ebookTheme";

const FACTION_ENTITY_TYPES = new Set(["faction", "organization"]);

function isFactionEntity(entity: MasterEntity): boolean {
  return FACTION_ENTITY_TYPES.has(entity.entity_type);
}

export function CharacterDrawer({
  isOpen,
  onClose,
  playerStats,
  playerInventory,
  entities,
  objectives,
}: CharacterDrawerProps) {
  const tokens = useEBookThemeTokens();
  const [activeTab, setActiveTab] = useState<CharacterDrawerTab>("stats");
  const factions = entities.filter(isFactionEntity);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/70 z-40 backdrop-blur-xs transition-opacity"
        />
      )}
      <aside
        className={`fixed top-0 right-0 h-full w-80 sm:w-96 z-50 border-l shadow-2xl transition-transform duration-300 flex flex-col ${tokens.panelBg} ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-inherit/20">
          <div className="flex items-center gap-2">
            <span className="text-base">🧭</span>
            <h2 className="font-mono text-xs tracking-wider uppercase font-semibold">
              Character
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded opacity-60 hover:opacity-100 transition-opacity font-mono text-xs cursor-pointer"
            title="Close (Esc)"
          >
            ✕ Close
          </button>
        </div>

        <CharacterDrawerTabs
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          accentBorder={tokens.accentBorder}
        />

        <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-minimal font-mono text-sm">
          {activeTab === "stats" && (
            <StatsTab stats={playerStats} tokens={tokens} />
          )}
          {activeTab === "inventory" && (
            <InventoryTab items={playerInventory} tokens={tokens} />
          )}
          {activeTab === "factions" && (
            <FactionsTab factions={factions} tokens={tokens} />
          )}
          {activeTab === "objectives" && (
            <ObjectivesTab objectives={objectives} tokens={tokens} />
          )}
        </div>
      </aside>
    </>
  );
}

interface TabsProps {
  activeTab: CharacterDrawerTab;
  onSelectTab: (tab: CharacterDrawerTab) => void;
  accentBorder: string;
}

function CharacterDrawerTabs({
  activeTab,
  onSelectTab,
  accentBorder,
}: TabsProps) {
  const tabs: { key: CharacterDrawerTab; label: string }[] = [
    { key: "stats", label: "Stats" },
    { key: "inventory", label: "Inventory" },
    { key: "factions", label: "Factions" },
    { key: "objectives", label: "Objectives" },
  ];

  return (
    <div className="flex border-b border-inherit/20 font-mono text-[11px]">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onSelectTab(tab.key)}
          className={`flex-1 py-3 text-center transition-colors border-b-2 cursor-pointer ${
            activeTab === tab.key
              ? `${accentBorder} font-bold`
              : "border-transparent opacity-60 hover:opacity-100"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="opacity-60 text-xs italic">{text}</p>;
}

function StatsTab({
  stats,
  tokens,
}: {
  stats: CharacterDrawerProps["playerStats"];
  tokens: ReturnType<typeof useEBookThemeTokens>;
}) {
  if (stats.length === 0) return <EmptyState text="No tracked stats yet." />;
  return (
    <>
      {stats.map((stat) => (
        <div
          key={stat.key}
          className={`flex items-center justify-between rounded-lg border px-3 py-2 ${tokens.cardBg}`}
        >
          <span>{stat.label}</span>
          <span className="font-bold">{String(stat.value)}</span>
        </div>
      ))}
    </>
  );
}

function InventoryTab({
  items,
  tokens,
}: {
  items: MasterEntity[];
  tokens: ReturnType<typeof useEBookThemeTokens>;
}) {
  if (items.length === 0) return <EmptyState text="Your inventory is empty." />;
  return (
    <>
      {items.map((item) => (
        <div
          key={item.entity_id}
          className={`rounded-lg border px-3 py-2 ${tokens.cardBg}`}
        >
          {item.canonical_name}
        </div>
      ))}
    </>
  );
}

function FactionsTab({
  factions,
  tokens,
}: {
  factions: MasterEntity[];
  tokens: ReturnType<typeof useEBookThemeTokens>;
}) {
  if (factions.length === 0) {
    return <EmptyState text="No known factions." />;
  }
  return (
    <>
      {factions.map((faction) => (
        <div
          key={faction.entity_id}
          className={`rounded-lg border px-3 py-2 space-y-1 ${tokens.cardBg}`}
        >
          <p className="font-bold">{faction.canonical_name}</p>
          {Object.entries(faction.attributes).map(([key, value]) => (
            <div
              key={key}
              className="flex items-center justify-between text-xs"
            >
              <span className="opacity-70">
                {faction.attributes_schema[key]?.label ?? key}
              </span>
              <span>{String(value)}</span>
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

function ObjectivesTab({
  objectives,
  tokens,
}: {
  objectives: CharacterDrawerProps["objectives"];
  tokens: ReturnType<typeof useEBookThemeTokens>;
}) {
  if (objectives.length === 0) {
    return <EmptyState text="No known objectives yet." />;
  }
  const wins = objectives.filter((o) => o.outcome_tag === "win");
  const losses = objectives.filter((o) => o.outcome_tag === "lose");
  return (
    <>
      {wins.length > 0 && (
        <ObjectiveGroup label="Goals" items={wins} tokens={tokens} icon="🏆" />
      )}
      {losses.length > 0 && (
        <ObjectiveGroup
          label="Avoid"
          items={losses}
          tokens={tokens}
          icon="⚠️"
        />
      )}
    </>
  );
}

function ObjectiveGroup({
  label,
  items,
  tokens,
  icon,
}: {
  label: string;
  items: CharacterDrawerProps["objectives"];
  tokens: ReturnType<typeof useEBookThemeTokens>;
  icon: string;
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-[10px] uppercase tracking-wider opacity-60">
        {label}
      </h3>
      {items.map((item) => (
        <div
          key={item.outcome_title}
          className={`rounded-lg border px-3 py-2 ${tokens.cardBg}`}
        >
          <p className="font-bold">
            {icon} {item.outcome_title}
          </p>
          <p className="text-xs opacity-75 mt-1">{item.outcome_text}</p>
        </div>
      ))}
    </div>
  );
}
