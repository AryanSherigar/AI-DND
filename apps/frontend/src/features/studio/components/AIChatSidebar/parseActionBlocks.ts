import { ActionBlock, ActionTarget } from "../../types/assistant.types";

export interface TextSegment {
  type: "text";
  content: string;
}

export interface ActionSegment {
  type: "action";
  block: ActionBlock;
}

export type MessageSegment = TextSegment | ActionSegment;

const ACTION_BLOCK_REGEX =
  /```action:([a-z_]+)(?:[ \t]+(\{[^}\n]*\}))?\s*\n([\s\S]*?)```/gi;

const parseMetadata = (
  rawMeta?: string,
): { type?: string; name?: string } | undefined => {
  if (!rawMeta) return undefined;
  try {
    return JSON.parse(rawMeta);
  } catch {
    return undefined;
  }
};

const normalizeTarget = (raw: string): ActionTarget => {
  const clean = raw.toLowerCase().trim();
  if (clean === "card" || clean === "storycard") return "story_card";
  if (clean === "prompt" || clean === "opening") return "opening_prompt";
  return clean as ActionTarget;
};

export const parseMessageSegments = (content: string): MessageSegment[] => {
  const segments: MessageSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = ACTION_BLOCK_REGEX.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: "text",
        content: content.slice(lastIndex, match.index),
      });
    }

    const target = normalizeTarget(match[1]);
    const metadata = parseMetadata(match[2]);
    const blockContent = match[3].trim();

    segments.push({
      type: "action",
      block: { target, metadata, content: blockContent },
    });

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    segments.push({
      type: "text",
      content: content.slice(lastIndex),
    });
  }

  return segments;
};
