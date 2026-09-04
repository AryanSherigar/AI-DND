export type ActionTarget =
  | "title"
  | "logline"
  | "lore"
  | "opening_prompt"
  | "conflict"
  | "story_card"
  | "style"
  | "instructions";

export interface ActionBlock {
  target: ActionTarget;
  metadata?: {
    type?: string;
    name?: string;
  };
  content: string;
}

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface ConflictModalState {
  isOpen: boolean;
  target: ActionTarget;
  targetLabel: string;
  existingValue: string;
  newValue: string;
  metadata?: {
    type?: string;
    name?: string;
  };
}

export const ACTION_TARGET_LABELS: Record<ActionTarget, string> = {
  title: "Scenario Title",
  logline: "Logline / Summary",
  lore: "World Lore",
  opening_prompt: "Opening Scene Hook",
  conflict: "Main Conflict / Goal",
  story_card: "Story Card",
  style: "Narrative Style & Vibe",
  instructions: "AI Narrator Guardrails",
};
