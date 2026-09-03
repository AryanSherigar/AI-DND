import { EntityResponse } from "../../types/entity.types";

export interface EntityRowProps {
  entity: EntityResponse;
  onEdit: (entity: EntityResponse) => void;
  onDelete: (entityId: string) => void;
}
