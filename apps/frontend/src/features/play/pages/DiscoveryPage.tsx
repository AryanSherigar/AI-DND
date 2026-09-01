import React, { useState } from "react";
import { DiscoverySidebar } from "../components/DiscoverySidebar";
import { TopSearchBar } from "../components/TopSearchBar";
import { WideScenarioCard } from "../components/WideScenarioCard";
import { AdvancedFiltersModal } from "../components/AdvancedFiltersModal";
import { useSearchParams } from "react-router-dom";
import { useDiscovery } from "../hooks/useDiscovery";

export const DiscoveryPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAdvancedFiltersOpen, setIsAdvancedFiltersOpen] = useState(false);
  const { data: filteredScenarios, isLoading } = useDiscovery(searchParams);

  // Mock handling search update
  const handleSearchUpdate = (query: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (query) {
      newParams.set("q", query);
    } else {
      newParams.delete("q");
    }
    setSearchParams(newParams);
  };

  const handlePillSelect = (filterKey: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value === "all") {
      newParams.delete(filterKey);
    } else {
      newParams.set(filterKey, value);
    }
    setSearchParams(newParams);
  };

  return (
    <div className="flex h-screen bg-[#0d0f14] text-white overflow-hidden">
      {/* Sidebar Navigation */}
      <DiscoverySidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Search Bar & Filters */}
        <TopSearchBar
          searchParams={searchParams}
          onSearchUpdate={handleSearchUpdate}
          onPillSelect={handlePillSelect}
          onOpenAdvanced={() => setIsAdvancedFiltersOpen(true)}
          onClearFilters={() => setSearchParams(new URLSearchParams())}
        />

        {/* Scrollable Feed List */}
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-12 pb-24 custom-scrollbar">
          <div className="max-w-5xl space-y-2">
            <div className="text-zinc-500 font-mono text-sm border-b border-zinc-800/50 pb-4 mb-4">
              Showing results for{" "}
              <span className="text-zinc-300">
                {searchParams.get("q") || "all scenarios"}
              </span>
            </div>

            {isLoading ? (
              <div className="text-zinc-500">Loading...</div>
            ) : filteredScenarios.length > 0 ? (
              <div className="flex flex-col gap-2 md:gap-4">
                {filteredScenarios.map((scenario) => (
                  <WideScenarioCard key={scenario.id} scenario={scenario} />
                ))}
              </div>
            ) : (
              <div className="py-20 text-center flex flex-col items-center justify-center border border-dashed border-zinc-800 rounded-xl">
                <h3 className="text-xl font-fell-sc text-zinc-400 mb-2">
                  No adventures found
                </h3>
                <p className="text-zinc-500 font-mono text-sm mb-6">
                  Try adjusting your filters or search query.
                </p>
                <button
                  onClick={() => setSearchParams(new URLSearchParams())}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg font-mono text-sm transition-colors"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Advanced Filters Modal */}
      <AdvancedFiltersModal
        isOpen={isAdvancedFiltersOpen}
        onClose={() => setIsAdvancedFiltersOpen(false)}
        searchParams={searchParams}
        onApply={(newParams) => setSearchParams(newParams)}
      />
    </div>
  );
};
