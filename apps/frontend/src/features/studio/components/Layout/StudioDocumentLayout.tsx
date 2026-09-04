import React, { useEffect, useState, useRef } from "react";
import { Step1Meta } from "../NewbieWizard/Step1Meta";
import { Step2Lore } from "../NewbieWizard/Step2Lore";
import { StepPlayerSetup } from "../NewbieWizard/StepPlayerSetup";
import { Step3Narrator } from "../NewbieWizard/Step3Narrator";
import { Step4Review } from "../NewbieWizard/Step4Review";
import { StudioChatDrawer } from "./StudioChatDrawer";

const sections = [
  { id: "meta", label: "The Basics" },
  { id: "lore", label: "World Lore" },
  { id: "setup", label: "Player Setup" },
  { id: "narrator", label: "The Narrator" },
  { id: "review", label: "Review & Publish" },
];

export const StudioDocumentLayout: React.FC = () => {
  const [activeSection, setActiveSection] = useState("meta");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      { root: container, rootMargin: "-20% 0px -60% 0px", threshold: 0.1 },
    );

    sections.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="flex flex-1 overflow-hidden bg-zinc-950 font-sans text-zinc-300">
      {/* Left Pane: Table of Contents */}
      <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex-shrink-0 hidden md:flex flex-col p-6">
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-6">
          Contents
        </h3>
        <nav className="space-y-1">
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => scrollTo(s.id)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                activeSection === s.id
                  ? "bg-zinc-900 text-zinc-100 font-medium border-l-2 border-zinc-100"
                  : "text-zinc-500 hover:text-zinc-300 border-l-2 border-transparent"
              }`}
            >
              {s.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Center Pane: Main Scroll Area */}
      <main
        ref={containerRef}
        className="flex-1 overflow-y-auto scroll-smooth p-8 lg:p-16 space-y-32 relative pb-64"
      >
        <div id="meta" className="scroll-mt-12 max-w-4xl mx-auto">
          <Step1Meta />
        </div>
        <div id="lore" className="scroll-mt-12 max-w-4xl mx-auto">
          <Step2Lore />
        </div>
        <div id="setup" className="scroll-mt-12 max-w-4xl mx-auto">
          <StepPlayerSetup />
        </div>
        <div id="narrator" className="scroll-mt-12 max-w-4xl mx-auto">
          <Step3Narrator />
        </div>
        <div id="review" className="scroll-mt-12 max-w-4xl mx-auto">
          <Step4Review />
        </div>
      </main>

      <StudioChatDrawer activeSection={activeSection} />
    </div>
  );
};
