import { EndConditionResponse } from "../../types/end_condition.types";

export const sortByPriority = (
  endConditions: EndConditionResponse[],
): EndConditionResponse[] =>
  [...endConditions].sort((a, b) => a.priority - b.priority);

export const buildReorderedIds = (
  orderedEndConditions: EndConditionResponse[],
  activeId: string,
  overId: string,
): string[] => {
  const ids = orderedEndConditions.map((item) => item.end_condition_id);
  const activeIndex = ids.indexOf(activeId);
  const overIndex = ids.indexOf(overId);
  if (activeIndex === -1 || overIndex === -1) return ids;

  const reordered = [...ids];
  reordered.splice(activeIndex, 1);
  reordered.splice(overIndex, 0, activeId);
  return reordered;
};
