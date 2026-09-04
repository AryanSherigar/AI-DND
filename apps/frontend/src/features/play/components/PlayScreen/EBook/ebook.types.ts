import {
  ChapterDelta,
  DiceRoll,
  EntityHighlightItem,
  MasterEntity,
  Objective,
  PlayerStat,
  TurnLogItem,
} from "../../../types/play.types";

export interface EBookHeaderProps {
  onBack: () => void;
  onOpenCodex: () => void;
  onOpenChronicle: () => void;
  // Master mode only — omitted (or empty) renders no badge row.
  activeConditions?: string[];
}

export interface StatusBadgeRowProps {
  conditions: string[];
}

export interface ChapterSummaryStripProps {
  delta: ChapterDelta;
}

export interface DiceRollCardProps {
  roll: DiceRoll;
}

export type CharacterDrawerTab =
  "stats" | "inventory" | "factions" | "objectives";

export interface CharacterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  playerStats: PlayerStat[];
  playerInventory: MasterEntity[];
  entities: MasterEntity[];
  objectives: Objective[];
}

export interface EBookPrologueCardProps {
  premise: string;
  characterName: string;
  onStartAction: () => void;
}

export interface EBookTurnEntryProps {
  turn: TurnLogItem;
  turnIndex: number;
  isLatest: boolean;
  knownEntities: EntityHighlightItem[];
  onSelectEntity: (entity: EntityHighlightItem, rect: DOMRect) => void;
}

export interface EBookBottomBarProps {
  isNarrating: boolean;
  isSpectator: boolean;
  hasTurns: boolean;
  onTakeAction: () => void;
  onContinue: () => void;
  onRetry: () => void;
  onEditAction: () => void;
  onOpenCodex: () => void;
  // Master mode only — omitted renders no character-sheet trigger.
  onOpenCharacterSheet?: () => void;
  // Multiplayer turn-order gate. Defaults to true (newbie/solo never gate).
  canAct?: boolean;
  // Display name of whoever acts next, shown when canAct is false.
  waitingOnLabel?: string | null;
}

export interface EBookActionDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (actionText: string) => void;
  isNarrating: boolean;
}

export interface EntityInspectTooltipProps {
  entity: EntityHighlightItem | null;
  anchorRect: DOMRect | null;
  onClose: () => void;
}

export interface ChronicleRecapModalProps {
  isOpen: boolean;
  onClose: () => void;
}
