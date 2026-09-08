import React, { useEffect, useState, useRef } from "react";
import {
  IconInfoCircle,
  IconBook2,
  IconUsers,
  IconMasksTheater,
  IconRocket,
} from "@tabler/icons-react";
import { AppShell } from "@/shared/components/layout/AppShell";
import { SidebarButton } from "@/shared/components/layout/SidebarButton";
import { AIChatSidebar } from "../AIChatSidebar/AIChatSidebar";
import { Step1Meta } from "../NewbieWizard/Step1Meta";
import { Step2Lore } from "../NewbieWizard/Step2Lore";
import { StepPlayerSetup } from "../NewbieWizard/StepPlayerSetup";
import { Step3Narrator } from "../NewbieWizard/Step3Narrator";
import { Step4Review } from "../NewbieWizard/Step4Review";

const sections = [
  { id: "meta", label: "The basics", icon: <IconInfoCircle size={18} /> },
  { id: "lore", label: "World lore", icon: <IconBook2 size={18} /> },
  { id: "setup", label: "Player setup", icon: <IconUsers size={18} /> },
  {
    id: "narrator",
    label: "The narrator",
    icon: <IconMasksTheater size={18} />,
  },
  { id: "review", label: "Review & publish", icon: <IconRocket size={18} /> },
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
    <div className="flex min-h-0 flex-1 font-sans text-content-muted">
      <AppShell
        nav={sections.map((s) => (
          <SidebarButton
            key={s.id}
            icon={s.icon}
            label={s.label}
            isActive={activeSection === s.id}
            onClick={() => scrollTo(s.id)}
          />
        ))}
        rightPanel={<AIChatSidebar activeSection={activeSection} />}
        rightPanelTitle="AERO"
        rightPanelSubtitle="your story-writing companion"
        showFloatingNav={false}
      >
        <main
          ref={containerRef}
          className="relative flex-1 space-y-32 overflow-y-auto scroll-smooth p-8 pb-64 lg:p-16"
        >
          <div id="meta" className="mx-auto max-w-4xl scroll-mt-12">
            <Step1Meta />
          </div>
          <div id="lore" className="mx-auto max-w-4xl scroll-mt-12">
            <Step2Lore />
          </div>
          <div id="setup" className="mx-auto max-w-4xl scroll-mt-12">
            <StepPlayerSetup />
          </div>
          <div id="narrator" className="mx-auto max-w-4xl scroll-mt-12">
            <Step3Narrator />
          </div>
          <div id="review" className="mx-auto max-w-4xl scroll-mt-12">
            <Step4Review />
          </div>
        </main>
      </AppShell>
    </div>
  );
};
