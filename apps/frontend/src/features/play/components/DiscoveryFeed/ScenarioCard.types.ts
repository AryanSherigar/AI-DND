import { ScenarioMock } from "../../types/scenario";

export interface ScenarioCardProps {
  scenario: ScenarioMock;
  isDimmed?: boolean;
  onHoverStart?: () => void;
  onHoverEnd?: () => void;
}
