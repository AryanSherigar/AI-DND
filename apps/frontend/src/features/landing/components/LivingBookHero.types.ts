import React from "react";

export interface LivingBookHeroProps {
  /** Path to the static background image */
  baseImageUrl?: string;
  /** Controls which rendering method is used for the mist */
  mistRenderMode?: "blobs" | "svg-turbulence";
  /** Number of pure CSS mist blobs to render (only used if mistRenderMode='blobs') */
  blobCount?: number;
  /** Number of drifting dust motes to render */
  dustCount?: number;
  /** Maximum opacity of the mist */
  mistOpacity?: number;
  /** Blur radius for mist layers in pixels */
  mistBlur?: number;
  /** Multiplier for the mouse parallax effect */
  parallaxIntensity?: number;
  /** Content to render above the hero (e.g. text) */
  children?: React.ReactNode;
}
