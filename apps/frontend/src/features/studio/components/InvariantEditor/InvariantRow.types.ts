import { InvariantResponse } from "../../types/invariant.types";

export interface InvariantRowProps {
  invariant: InvariantResponse;
  onEdit: (invariant: InvariantResponse) => void;
  onDelete: (invariantId: string) => void;
}
