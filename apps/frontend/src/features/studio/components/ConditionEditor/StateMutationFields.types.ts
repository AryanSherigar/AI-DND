import { StateMutation } from "../../types/condition.types";

export interface StateMutationFieldsProps {
  value: StateMutation | null;
  onChange: (mutation: StateMutation | null) => void;
}
