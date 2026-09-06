import { MinigameResponse } from "../../types/minigame.types";

export const sortByPriority = (
  minigames: MinigameResponse[],
): MinigameResponse[] => [...minigames].sort((a, b) => a.priority - b.priority);

export const buildReorderedIds = (
  orderedMinigames: MinigameResponse[],
  activeId: string,
  overId: string,
): string[] => {
  const ids = orderedMinigames.map((item) => item.minigame_id);
  const activeIndex = ids.indexOf(activeId);
  const overIndex = ids.indexOf(overId);
  if (activeIndex === -1 || overIndex === -1) return ids;

  const reordered = [...ids];
  reordered.splice(activeIndex, 1);
  reordered.splice(overIndex, 0, activeId);
  return reordered;
};
