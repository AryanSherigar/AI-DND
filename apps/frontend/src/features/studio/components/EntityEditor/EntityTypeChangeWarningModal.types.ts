import { EntityTypeChangePreviewResponse } from "../../types/entity.types";

export interface EntityTypeChangeWarningModalProps {
  isOpen: boolean;
  newTypeLabel: string;
  preview: EntityTypeChangePreviewResponse | null;
  onConfirm: () => void;
  onCancel: () => void;
}
