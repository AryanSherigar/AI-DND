import React from "react";
import { ScenarioMetaForm } from "../ScenarioMetaForm/ScenarioMetaForm";
import { OpeningSceneEditor } from "../OpeningSceneEditor/OpeningSceneEditor";
import { SetupSchemaEditor } from "../SetupSchemaEditor/SetupSchemaEditor";
import { NarratorPersonaEditor } from "../NarratorPersonaEditor/NarratorPersonaEditor";
import { NarrationFontPicker } from "../NarrationFontPicker/NarrationFontPicker";
import { ActionChipsEditor } from "../ActionChipsEditor/ActionChipsEditor";
import { RulesEditor } from "../RulesEditor/RulesEditor";
import { StudioSetupPanelProps } from "./MasterModeStudioLayout.types";

export const StudioSetupPanel: React.FC<StudioSetupPanelProps> = ({
  scenarioId,
}) => (
  <div className="max-w-3xl space-y-12">
    <ScenarioMetaForm scenarioId={scenarioId} />
    <OpeningSceneEditor scenarioId={scenarioId} />
    <SetupSchemaEditor scenarioId={scenarioId} />
    <NarratorPersonaEditor scenarioId={scenarioId} />
    <NarrationFontPicker scenarioId={scenarioId} />
    <ActionChipsEditor scenarioId={scenarioId} />
    <RulesEditor scenarioId={scenarioId} />
  </div>
);
