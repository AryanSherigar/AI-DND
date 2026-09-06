import React from "react";
import { ChromaticImage } from "@/shared/components/ui/aceternity/chromatic-image";

const LOGIN_HERO_SRC = "/images/login-hero.webp";

export const LoginHero: React.FC = () => {
  return (
    <ChromaticImage
      src={LOGIN_HERO_SRC}
      alt="A person standing beneath a red light"
      backgroundColor="#0d0f14"
      tilt={0}
      zoom={0.12}
      displacement={0.03}
      chromaticShift={0.006}
      className="h-full w-full [filter:brightness(1.28)_contrast(0.9)_saturate(0.82)] dark:bg-neutral-100"
    />
  );
};
