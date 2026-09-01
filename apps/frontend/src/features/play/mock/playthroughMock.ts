import { PlaythroughData } from "../types/play.types";

export const INITIAL_MOCK_PLAYTHROUGH: PlaythroughData = {
  playthrough_id: "mock-session-001",
  scenario_id: "scenario-shadows-over-eldoria",
  scenario_title: "Shadows Over Eldoria",
  creator_name: "ArchmageVaelin",
  cover_image_url:
    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80",
  opening_premise:
    "The ancient Obsidian Spire has stood silent for three centuries above the mist-shrouded valley of Eldoria. Tonight, a blood-red light emanates from its peak, breaking the magical wards that protected the village below. As the village warden, you step into the darkness holding only your iron lantern and a rusted sword.",
  world_lore:
    "Eldoria is a realm steeped in forgotten elemental sorcery. Long before the Sun-King era, seven dragon lords forged the Obsidian Spire to tether wild etheric currents. When the Spire fell dormant, the valley prospered, though elder texts warned that one day the blood celestial eclipse would awaken the slumbering shadows within.",
  key_facts: [
    "The Obsidian Spire draws power from blood celestial eclipses.",
    "Iron lanterns bypass spectral glamours produced by shadow wraiths.",
    "Elder Warden Kaelen vanished into the Spire forty years ago.",
  ],
  story_cards: [
    {
      id: "card-1",
      title: "The Iron Lantern",
      category: "Relic",
      content:
        "Engraved with dwarf-runes of warding. Emits a warm amber flame that repels low-level shadow wraiths.",
    },
    {
      id: "card-2",
      title: "Whispering Mists",
      category: "Environment",
      content:
        "The valley mists carry faint echoes of forgotten incantations. Those who listen too closely risk losing their path.",
    },
  ],
  character_name: "Valerius Flameheart",
  custom_fields: [
    {
      key: "background",
      label: "Origin Background",
      value: "Former Royal Sentinel",
    },
    {
      key: "starting_item",
      label: "Favored Tool",
      value: "Rune-inscribed Compass",
    },
    {
      key: "alignment",
      label: "Moral Compass",
      value: "Protector of the Innocent",
    },
  ],
  turns: [
    {
      id: "turn-1",
      turn_number: 1,
      action_mode: "do",
      action_text:
        "I raise my iron lantern to illuminate the dark stone archway at the base of the Spire.",
      narration_text:
        "The amber light flares bright against the midnight gloom, carving a warm circle in the oppressive fog. Before you looms a heavy oak door reinforced with black iron bands. Moisture glistens on the ancient wood, and faint scratch marks near the iron latch suggest something recently clawed its way inside.",
      created_at: new Date(Date.now() - 3600000).toISOString(),
    },
    {
      id: "turn-2",
      turn_number: 2,
      action_mode: "see",
      action_text:
        "I inspect the scratch marks near the latch to determine what made them.",
      narration_text:
        "Bending close, you trace the deep grooves with a gloved finger. The gouges cut deeply through the iron banding—far beyond human strength. A sticky black residue coats the splintered edges, emitting a faint odor of ozonated frost.",
      created_at: new Date(Date.now() - 1800000).toISOString(),
    },
  ],
  is_spectator: false,
};

const MOCK_NARRATIONS: Record<string, string> = {
  say: "Your voice echoes off the damp stone walls, stirring cold air from deep within the passageway. From the shadows beyond, a soft rustle answers your words, as though something lingering in the gloom has been patiently waiting for a visitor.",
  do: "Stepping forward with measured caution, your boots crunch on dry gravel. The shadows twist as your lantern beam sweeps across rusted chains dangling from the ceiling. Further ahead, a dark stairwell descends deeper into the earth.",
  story:
    "A low rumble vibrates through the stone floor as distant machinery turns deep beneath the Spire. Dust cascades from the vault ceiling, and the ambient mist pulses with a deep crimson glow.",
  see: "Scanning the surrounding corridor, you notice etched dwarven runes along the baseboard that glimmer in rhythm with your lantern flame. A concealed iron lever is embedded in the mortar of the northern pillar.",
};

export function simulateTokenStream(
  mode: string,
  onToken: (token: string) => void,
  onComplete: () => void,
): () => void {
  const fullText = MOCK_NARRATIONS[mode] || MOCK_NARRATIONS.do;
  const tokens = fullText.split(" ");
  let current_index = 0;
  let is_cancelled = false;

  const timer = setInterval(() => {
    if (is_cancelled) {
      clearInterval(timer);
      return;
    }
    if (current_index < tokens.length) {
      const nextToken =
        tokens[current_index] +
        (current_index === tokens.length - 1 ? "" : " ");
      onToken(nextToken);
      current_index += 1;
    } else {
      clearInterval(timer);
      onComplete();
    }
  }, 90);

  return () => {
    is_cancelled = true;
    clearInterval(timer);
  };
}
