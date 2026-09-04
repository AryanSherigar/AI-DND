export interface AvatarPreset {
  id: string;
  name: string;
  role: string;
  url: string;
  iconBg: string;
  accent: string;
}

export interface BannerPreset {
  id: string;
  name: string;
  url: string;
  description: string;
}

export const AVATAR_PRESETS: AvatarPreset[] = [
  {
    id: "mage",
    name: "Arcane Magus",
    role: "Spellcaster",
    url: "https://api.dicebear.com/7.x/bottts/svg?seed=Archmage&backgroundColor=18181b",
    iconBg: "from-purple-900 to-indigo-950",
    accent: "#a855f7",
  },
  {
    id: "knight",
    name: "Iron Paladin",
    role: "Warrior",
    url: "https://api.dicebear.com/7.x/bottts/svg?seed=Paladin&backgroundColor=18181b",
    iconBg: "from-amber-900 to-yellow-950",
    accent: "#f59e0b",
  },
  {
    id: "rogue",
    name: "Shadowblade",
    role: "Infiltrator",
    url: "https://api.dicebear.com/7.x/bottts/svg?seed=Shadowblade&backgroundColor=18181b",
    iconBg: "from-zinc-900 to-neutral-950",
    accent: "#71717a",
  },
  {
    id: "bard",
    name: "Wandering Skald",
    role: "Storyteller",
    url: "https://api.dicebear.com/7.x/bottts/svg?seed=BardSkald&backgroundColor=18181b",
    iconBg: "from-emerald-900 to-teal-950",
    accent: "#10b981",
  },
  {
    id: "druid",
    name: "Grove Keeper",
    role: "Naturalist",
    url: "https://api.dicebear.com/7.x/bottts/svg?seed=DruidGrove&backgroundColor=18181b",
    iconBg: "from-green-950 to-emerald-900",
    accent: "#22c55e",
  },
  {
    id: "warlock",
    name: "Eldritch Binder",
    role: "Occultist",
    url: "https://api.dicebear.com/7.x/bottts/svg?seed=Eldritch&backgroundColor=18181b",
    iconBg: "from-rose-950 to-purple-950",
    accent: "#e11d48",
  },
];

export const BANNER_PRESETS: BannerPreset[] = [
  {
    id: "portal",
    name: "The Obsidian Portal",
    url: "/hero-portal.png",
    description: "Gateway across astral boundaries",
  },
  {
    id: "grimoire",
    name: "The Living Grimoire",
    url: "/images/hero.png",
    description: "Bound in dragonhide and gold trim",
  },
  {
    id: "abyss",
    name: "The Abyssal Spire",
    url: "/images/abyss.png",
    description: "Cold ruins at the edge of night",
  },
  {
    id: "crimson",
    name: "Crimson Battlefield",
    url: "/images/crimson.png",
    description: "Blood-soaked soil under a twin moon",
  },
  {
    id: "sands",
    name: "Gilded Sunken Dunes",
    url: "/images/sands.png",
    description: "Lost pyramids bathed in gold dust",
  },
];

export const DEFAULT_AVATAR = AVATAR_PRESETS[0].url;
export const DEFAULT_BANNER = BANNER_PRESETS[1].url;
