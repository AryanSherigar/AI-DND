import React, { useState } from "react";
import { Separator } from "@/shared/components/ui/Separator";
import { MapCanvas } from "./MapCanvas";
import { MapConnectionEditor } from "./MapConnectionEditor";
import { MapEditorProps } from "./MapEditor.types";
import { MapList } from "./MapList";

export const MapEditor: React.FC<MapEditorProps> = ({ scenarioId }) => {
  const [selectedMapId, setSelectedMapId] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">Maps</h1>
        <p className="mt-1 text-xs text-zinc-500">
          Draw one or more maps, then pin your Location entities onto them.
          Movement between locations happens through the player's own narration
          during play — pins and connections give the narrator context, they
          never gate what the player can do.
        </p>
      </div>
      <MapList
        scenarioId={scenarioId}
        selectedMapId={selectedMapId}
        onSelectMap={setSelectedMapId}
      />
      {selectedMapId && (
        <>
          <Separator />
          <MapCanvas scenarioId={scenarioId} mapId={selectedMapId} />
        </>
      )}
      <Separator />
      <MapConnectionEditor scenarioId={scenarioId} />
    </div>
  );
};
