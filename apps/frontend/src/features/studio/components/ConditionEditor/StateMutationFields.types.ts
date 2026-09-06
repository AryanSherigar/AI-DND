import { StateMutation } from "@/shared/types/stateMutation.types";

export interface StateMutationFieldsProps {
  value: StateMutation | null;
  onChange: (mutation: StateMutation | null) => void;
  /**
   * When false, the mutation is required: the "has mutation" checkbox is
   * hidden and the path/op/value fields render unconditionally. Used by
   * minigame outcome mutations (binary win/lose, tiered, timeout), which
   * are never optional the way an active condition's Effect C is.
   * Defaults to true, preserving existing ConditionEditor behavior.
   */
  isOptional?: boolean;
}
