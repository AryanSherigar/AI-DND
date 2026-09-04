import { EntityResponse } from "../../types/entity.types";
import { FactResponse } from "../../types/fact.types";

export interface FactRowProps {
  fact: FactResponse;
  entityById: Map<string, EntityResponse>;
  onEdit: (fact: FactResponse) => void;
  onDelete: (factId: string) => void;
}
