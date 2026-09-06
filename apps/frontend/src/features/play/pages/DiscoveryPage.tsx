import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { TopSearchBar } from "../components/DiscoveryFeed/TopSearchBar";
import { WideScenarioCard } from "../components/DiscoveryFeed/WideScenarioCard";
import { WideScenarioCardSkeleton } from "../components/DiscoveryFeed/WideScenarioCardSkeleton";
import { AdvancedFiltersModal } from "../components/DiscoveryFeed/AdvancedFiltersModal";
import { useDiscovery } from "../hooks/useDiscovery";

export const DiscoveryPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAdvancedFiltersOpen, setIsAdvancedFiltersOpen] = useState(false);
  const { data: filteredScenarios, isLoading } = useDiscovery(searchParams);

  const handleSearchUpdate = (query: string): void => {
    const newParams = new URLSearchParams(searchParams);
    if (query) newParams.set("q", query);
    else newParams.delete("q");
    setSearchParams(newParams);
  };

  const handlePillSelect = (filterKey: string, value: string): void => {
    const newParams = new URLSearchParams(searchParams);
    if (value === "all") newParams.delete(filterKey);
    else newParams.set(filterKey, value);
    setSearchParams(newParams);
  };

  const handleClearFilters = (): void => setSearchParams(new URLSearchParams());

  return (
    <>
      <TopSearchBar
        searchParams={searchParams}
        onSearchUpdate={handleSearchUpdate}
        onPillSelect={handlePillSelect}
        onOpenAdvanced={() => setIsAdvancedFiltersOpen(true)}
        onClearFilters={handleClearFilters}
      />

      <div className="custom-scrollbar flex-1 overflow-y-auto px-4 py-6 pb-24 md:px-10">
        <div className="mx-auto max-w-5xl">
          {isLoading ? (
            <div className="flex flex-col gap-4">
              {[0, 1, 2, 3].map((index) => (
                <WideScenarioCardSkeleton key={index} />
              ))}
            </div>
          ) : filteredScenarios.length > 0 ? (
            <div className="flex flex-col gap-2 md:gap-4">
              {filteredScenarios.map((scenario) => {
                const cardKey =
                  "scenario_id" in scenario ? scenario.scenario_id : scenario.id;
                return (
                  <WideScenarioCard key={String(cardKey)} scenario={scenario} />
                );
              })}
            </div>
          ) : (
            <div className="mt-6 flex flex-col items-center justify-center rounded-xl border border-border-subtle bg-surface/60 px-6 py-20 text-center">
              <h3 className="mb-2 font-fell-sc text-xl text-content">
                Nothing matches yet
              </h3>
              <p className="mb-6 font-sans text-sm text-content-faint">
                Loosen a filter or try a different search.
              </p>
              <button
                onClick={handleClearFilters}
                className="rounded-md border border-border-subtle bg-surface px-4 py-2 font-sans text-sm text-content-muted transition hover:bg-surface-overlay hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>
      </div>

      <AdvancedFiltersModal
        isOpen={isAdvancedFiltersOpen}
        onClose={() => setIsAdvancedFiltersOpen(false)}
        searchParams={searchParams}
        onApply={(newParams) => setSearchParams(newParams)}
      />
    </>
  );
};
