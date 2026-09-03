import React, { useEffect, useRef, useState } from "react";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import { NARRATION_FONT_LABELS, NARRATION_FONTS } from "@/shared/constants/narration-fonts";
import { useScenario } from "../../hooks/useScenario";
import { NarrationFontPickerProps } from "./NarrationFontPicker.types";

const FONT_OPTIONS: SelectOption[] = NARRATION_FONTS.map((font) => ({
  value: font,
  label: NARRATION_FONT_LABELS[font],
}));

export const NarrationFontPicker: React.FC<NarrationFontPickerProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario } = useScenario(scenarioId);
  const [font, setFont] = useState<string>(NARRATION_FONTS[0]);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setFont(scenario.narration_font ?? NARRATION_FONTS[0]);
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
      <h2 className="text-base font-semibold text-zinc-100">
        Narration Font
      </h2>
      <Select
        aria-label="Narration font"
        options={FONT_OPTIONS}
        value={font}
        onChange={handleChange}
      />
    </div>
  );
};
