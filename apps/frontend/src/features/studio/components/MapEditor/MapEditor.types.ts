export interface MapEditorProps {
  scenarioId: string;
}

export interface MapListProps {
  scenarioId: string;
  selectedMapId: string | null;
  onSelectMap: (mapId: string) => void;
}

export interface MapCanvasProps {
  scenarioId: string;
  mapId: string;
}

export interface MapConnectionEditorProps {
  scenarioId: string;
}
