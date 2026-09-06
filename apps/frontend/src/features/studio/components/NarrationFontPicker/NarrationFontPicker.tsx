import React, { useEffect, useRef, useState } from "react";
import { Select, SelectOptionGroup } from "@/shared/components/ui/Select";
import {
  DEFAULT_NARRATION_FONT_ID,
  FONT_GENRE_CATEGORIES,
  NARRATION_FONTS_CATALOG,
  resolveNarrationFont,
} from "@/shared/constants/narration-fonts";
import { useScenario } from "../../hooks/useScenario";
import { NarrationFontPickerProps } from "./NarrationFontPicker.types";

const FONT_GROUPS: SelectOptionGroup[] = FONT_GENRE_CATEGORIES.map(
  (category) => ({
    label: category,
    options: NARRATION_FONTS_CATALOG.filter((f) => f.category === category).map(
      (f) => ({
        value: f.id,
        label: f.label,
      }),
    ),
  }),
);

export const NarrationFontPicker: React.FC<NarrationFontPickerProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario } = useScenario(scenarioId);
  const [font, setFont] = useState<string>(DEFAULT_NARRATION_FONT_ID);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      const resolved = resolveNarrationFont(scenario.narration_font);
      setFont(resolved.id);
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    const nextFont = e.target.value;
    setFont(nextFont);
    updateScenario({ narration_font: nextFont });
  };

  if (isLoading) {
    return <p className="text-sm text-zinc-500">Loading narration font...</p>;
  }

  return (
    <div className="space-y-2">
      <h2 className="text-base font-semibold text-zinc-100">Narration Font</h2>
      <Select
        aria-label="Narration font"
        groups={FONT_GROUPS}
        value={font}
        onChange={handleChange}
      />
    </div>
  );
};
