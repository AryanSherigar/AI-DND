export interface DodgeMinigameConfig {
  difficulty: number; // 1-5
}

export interface DodgeMinigameOutcome {
  outcome_tag: "win" | "lose";
  score: number;
}

export interface DodgeMinigameProps {
  dodgeConfig: DodgeMinigameConfig;
  onComplete: (result: DodgeMinigameOutcome) => void;
}
