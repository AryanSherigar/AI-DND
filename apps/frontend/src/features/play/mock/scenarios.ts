import { ScenarioMock } from "../types/scenario";

export const mockScenarios: ScenarioMock[] = [
  {
    id: "1",
    title: "The Crimson Citadel",
    logline:
      "Infiltrate the bleeding tower of the blood mages before the crimson moon rises.",
    rating: 4.8,
    playerCount: 1245,
    genre: "High Fantasy",
    author: "ArchMage42",
    coverImageUrl: "/images/crimson.png",
    setupInputs: [
      {
        id: "field-1",
        key: "character_origin",
        label: "Lineage of Blood",
        type: "single_select",
        description:
          "Your ancestors pledged their blood to an ancient covenant.",
        required: true,
        options: [
          {
            id: "opt-1",
            label: "House of Sunfire (Paladin)",
            value: "sunfire",
          },
          { id: "opt-2", label: "Veil of Shadows (Rogue)", value: "shadows" },
          { id: "opt-3", label: "Coven of Arcana (Mage)", value: "arcana" },
        ],
        defaultValue: "sunfire",
      },
      {
        id: "field-2",
        key: "starting_relic",
        label: "Starting Relic",
        type: "single_select",
        description: "Choose a heirloom carried past the Citadel gates.",
        required: false,
        options: [
          { id: "rel-1", label: "Shattered Sun Amulet", value: "amulet" },
          { id: "rel-2", label: "Vial of Silver Blood", value: "vial" },
          { id: "rel-3", label: "Runic Dagger of the Fallen", value: "dagger" },
        ],
      },
      {
        id: "field-3",
        key: "secret_motive",
        label: "Secret Infiltration Motive",
        type: "textarea",
        placeholder:
          "Why do you seek the core of the Crimson Citadel? (e.g. avenge a lost sibling, retrieve a forbidden tome)",
        required: false,
        options: [],
      },
    ],
  },
  {
    id: "2",
    title: "Echoes of the Abyss",
    logline:
      "A cosmic horror mystery set on a deep-space mining station where the crew has begun to hear voices.",
    rating: 4.5,
    playerCount: 890,
    genre: "Sci-Fi",
    author: "VoidWalker",
    coverImageUrl: "/images/abyss.png",
    setupInputs: [
      {
        id: "field-space-1",
        key: "station_role",
        label: "Station Assignment",
        type: "single_select",
        description: "Your role aboard Deep-Mining Station Erebus-9.",
        required: true,
        options: [
          { id: "role-1", label: "Lead Engineer", value: "engineer" },
          { id: "role-2", label: "Security Specialist", value: "security" },
          { id: "role-3", label: "Xeno-Cartographer", value: "cartographer" },
        ],
      },
      {
        id: "field-space-2",
        key: "personal_quirk",
        label: "Psychological Anomaly",
        type: "text",
        placeholder:
          "e.g. Insomnia, auditory hallucinations, irrational fear of silence",
        required: false,
        options: [],
      },
    ],
  },
  {
    id: "3",
    title: "Sands of Aethelgard",
    logline:
      "Survive the harsh desert and uncover the lost civilization buried beneath the dunes.",
    rating: 4.9,
    playerCount: 2310,
    genre: "Adventure/Survival",
    author: "DuneMaster",
    coverImageUrl: "/images/sands.png",
  },
  {
    id: "4",
    title: "The Lost Kingdom of Vanaheim",
    logline:
      "A cozy slice-of-life journey about rebuilding a forgotten village from the ground up.",
    rating: 4.2,
    playerCount: 560,
    genre: "Slice of Life",
    author: "LoreKeeper",
    coverImageUrl: "/images/hero.png",
  },
  {
    id: "5",
    title: "Whispers of the Frost",
    logline: "Solve a chilling murder mystery in an isolated snowbound lodge.",
    rating: 4.7,
    playerCount: 1780,
    genre: "Noir / Detective",
    author: "WinterBorn",
    coverImageUrl: "/images/abyss.png",
  },
  {
    id: "6",
    title: "Blade of the Sun God",
    logline:
      "Escape the crumbling ruins of a post-apocalyptic Earth using solar-powered ancient tech.",
    rating: 4.6,
    playerCount: 940,
    genre: "Post-Apocalyptic/Dystopian",
    author: "SolarFlare",
    coverImageUrl: "/images/sands.png",
  },
];

export const trendingScenarios: ScenarioMock[] = Array.from(
  { length: 12 },
  (_, i) => ({
    ...mockScenarios[i % mockScenarios.length],
    id: `trending-${i + 1}`,
  }),
);

export const epicAdventures = mockScenarios.slice(2, 6);
export const newArrivals = [
  mockScenarios[5],
  mockScenarios[1],
  mockScenarios[4],
  mockScenarios[0],
];
