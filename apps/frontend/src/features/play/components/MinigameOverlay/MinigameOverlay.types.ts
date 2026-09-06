import { MinigameResultPayload } from "@/shared/types/minigame.types";

// What a minigame implementation (DodgeMinigame, ReplitEmbedMinigame) hands
// back on completion — everything MinigameResultPayload needs except
// minigame_id, which MinigameOverlay already knows from active_minigame and
// attaches itself before calling submitMinigameResult.
export type MinigameOutcomeResult = Omit<MinigameResultPayload, "minigame_id">;
