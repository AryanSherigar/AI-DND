import { EntityHighlightItem, TurnLogItem } from "../../../types/play.types";

export interface EBookHeaderProps {
  onBack: () => void;
  onOpenCodex: () => void;
  onOpenChronicle: () => void;
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
