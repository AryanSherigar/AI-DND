import React from "react";
import { Loader } from "./Loader";

export const RouteLoadingSpinner: React.FC = () => (
  <div className="min-h-[50vh] w-full flex items-center justify-center p-8">
    <Loader size="lg" label="Entering the realm..." />
  </div>
);
