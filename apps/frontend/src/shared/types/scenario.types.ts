export type SetupInputType =
  "single_select" | "multi_select" | "text" | "textarea" | "number";

export interface SetupInputOption {
  id: string;
  label: string;
  value: string;
}

export interface SetupInputField {
  id: string;
  key: string;
  label: string;
  type: SetupInputType;
  description?: string;
  placeholder?: string;
  required: boolean;
  options: SetupInputOption[];
  defaultValue?: string | string[] | number;
  is_character_name?: boolean;
  predicate?: string;
}
