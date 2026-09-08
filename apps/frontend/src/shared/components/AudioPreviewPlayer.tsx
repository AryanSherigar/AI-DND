import React from "react";
import { AudioPreviewPlayerProps } from "./AudioPreviewPlayer.types";

export const AudioPreviewPlayer: React.FC<AudioPreviewPlayerProps> = ({
  src,
  className = "",
}) => {
  return (
    <audio
      controls
      src={src}
      className={`w-full h-10 ${className}`}
      aria-label="Track preview"
    />
  );
};
