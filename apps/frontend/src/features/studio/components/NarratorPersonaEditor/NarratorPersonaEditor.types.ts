export interface NarratorPersonaEditorProps {
  scenarioId: string;
}

export interface CheckpointPersonaOverride {
  checkpoint_id: string;
  trigger_description: string;
  persona_override: string;
}
