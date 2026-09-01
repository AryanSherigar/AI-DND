import React, { useEffect, useState, useRef } from "react";
import { Step1Meta } from "../NewbieWizard/Step1Meta";
import { Step2Lore } from "../NewbieWizard/Step2Lore";
import { StepPlayerSetup } from "../NewbieWizard/StepPlayerSetup";
import { Step3Narrator } from "../NewbieWizard/Step3Narrator";
import { Step4Review } from "../NewbieWizard/Step4Review";
import { AIChatSidebar } from "../AIChatSidebar/AIChatSidebar";

const sections = [
  { id: "meta", label: "The Basics" },
  { id: "lore", label: "World Lore" },
  { id: "setup", label: "Player Setup" },
  { id: "narrator", label: "The Narrator" },
  { id: "review", label: "Review & Publish" },
];

export const StudioDocumentLayout: React.FC = () => {
  const [activeSection, setActiveSection] = useState("meta");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
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
      { root: container, rootMargin: "-20% 0px -60% 0px", threshold: 0.1 }
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
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-6">Contents</h3>
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
        <div id="meta" className="scroll-mt-12 max-w-4xl mx-auto"><Step1Meta /></div>
        <div id="lore" className="scroll-mt-12 max-w-4xl mx-auto"><Step2Lore /></div>
        <div id="setup" className="scroll-mt-12 max-w-4xl mx-auto"><StepPlayerSetup /></div>
        <div id="narrator" className="scroll-mt-12 max-w-4xl mx-auto"><Step3Narrator /></div>
        <div id="review" className="scroll-mt-12 max-w-4xl mx-auto"><Step4Review /></div>
      </main>

      {/* Right Pane: AI Chat Drawer Toggle */}
      {!isDrawerOpen && (
        <button
          onClick={() => setIsDrawerOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 bg-zinc-900 border border-r-0 border-zinc-800 p-2 text-zinc-500 hover:text-zinc-100 transition-colors z-40 shadow-xl"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </button>
      )}

      {/* Right Pane: AI Chat Drawer */}
      <div 
        className={`fixed right-0 top-[69px] h-[calc(100vh-69px)] w-80 bg-zinc-950 border-l border-zinc-800 transform transition-transform duration-300 z-50 flex flex-col ${
          isDrawerOpen ? "translate-x-0 shadow-2xl" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h3 className="text-xs font-semibold text-zinc-100 uppercase tracking-widest">Assistant</h3>
          <button onClick={() => setIsDrawerOpen(false)} className="text-zinc-500 hover:text-zinc-100">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="flex-1 overflow-hidden">
          <AIChatSidebar />
        </div>
      </div>
    </div>
  );
};
