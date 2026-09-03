import { useEffect } from "react";
import { usePlayStore } from "../../stores/play.store";
import { BackgroundMist } from "./BackgroundMist";
import { PlayHeader } from "./PlayHeader";
import { WorldCodexSidebar } from "./WorldCodexSidebar";
import { CharacterSheetSidebar } from "./CharacterSheetSidebar";
import { TurnHistory } from "./TurnHistory/TurnHistory";
import { ActionInput } from "./ActionInput";
import { SharePlaythroughModal } from "./Modals/SharePlaythroughModal";
import { EditCharacterWarningModal } from "./Modals/EditCharacterWarningModal";
import { EndPlaythroughModal } from "./Modals/EndPlaythroughModal";
import { Toast } from "@/shared/components/feedback/Toast";

export function PlayScreen() {
  const degraded_message = usePlayStore((s) => s.degraded_message);
  const clearDegradedMessage = usePlayStore((s) => s.clearDegradedMessage);
  const is_left_sidebar_open = usePlayStore((s) => s.is_left_sidebar_open);
  const is_right_sidebar_open = usePlayStore((s) => s.is_right_sidebar_open);
  const toggleLeftSidebar = usePlayStore((s) => s.toggleLeftSidebar);
  const toggleRightSidebar = usePlayStore((s) => s.toggleRightSidebar);
  const setLeftSidebarOpen = usePlayStore((s) => s.setLeftSidebarOpen);
  const setRightSidebarOpen = usePlayStore((s) => s.setRightSidebarOpen);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setLeftSidebarOpen(false);
        setRightSidebarOpen(false);
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [setLeftSidebarOpen, setRightSidebarOpen]);

  return (
    <div className="relative h-screen h-[100dvh] w-full bg-stone-950 text-stone-100 flex flex-col overflow-hidden font-sans selection:bg-amber-500/30 selection:text-amber-200">
      {/* Background Mist Motion Layer */}
      <BackgroundMist opacity={0.55} blobCount={8} />

      {/* Header */}
      <PlayHeader />

      {/* Main 3-Column Workspace */}
      <div className="relative flex-1 flex min-h-0 h-[calc(100vh-3.5rem)] z-10 overflow-hidden">
        {/* Left Sidebar: World Codex */}
        <WorldCodexSidebar
          isOpen={is_left_sidebar_open}
          onToggle={toggleLeftSidebar}
        />

        {/* Mobile Left Sidebar Backdrop */}
        {is_left_sidebar_open && (
          <div
            onClick={toggleLeftSidebar}
            className="fixed inset-0 bg-black/60 z-30 lg:hidden backdrop-blur-xs"
          />
        )}

        {/* Center Column: Narrative Feed & Floating Action Input */}
        <main className="flex-1 flex flex-col min-w-0 h-full bg-transparent relative overflow-hidden">
          <TurnHistory />
          <ActionInput />
        </main>

        {/* Mobile Right Sidebar Backdrop */}
        {is_right_sidebar_open && (
          <div
            onClick={toggleRightSidebar}
            className="fixed inset-0 bg-black/60 z-30 lg:hidden backdrop-blur-xs"
          />
        )}

        {/* Right Sidebar: Character Sheet */}
        <CharacterSheetSidebar
          isOpen={is_right_sidebar_open}
          onToggle={toggleRightSidebar}
        />
      </div>

      {/* Modals Layer */}
      <SharePlaythroughModal />
      <EditCharacterWarningModal />
      <EndPlaythroughModal />

      {degraded_message && (
        <Toast
          message={degraded_message}
          type="error"
          onClose={clearDegradedMessage}
        />
      )}
    </div>
  );
}
