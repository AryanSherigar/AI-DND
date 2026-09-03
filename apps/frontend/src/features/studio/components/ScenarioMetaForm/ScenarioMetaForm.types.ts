import {
  ScenarioComplexityTier,
  ScenarioPlayerCountSupport,
} from "../../types/scenario.types";

export interface ScenarioMetaFormState {
  title: string;
  logline: string;
  genreTags: string[];
  complexityTier: ScenarioComplexityTier;
  contentTag: string | null;
  playerCountSupport: ScenarioPlayerCountSupport;
}

export interface ScenarioMetaFormProps {
  scenarioId: string;
}
