import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { usePlayStore } from "../../stores/play.store";
import { CharacterDrawer } from "./EBook/CharacterDrawer";
import { ChronicleRecapModal } from "./EBook/ChronicleRecapModal";
import { EBookActionDrawer } from "./EBook/EBookActionDrawer";
import { EBookBottomBar } from "./EBook/EBookBottomBar";
import { EBookCanvas } from "./EBook/EBookCanvas";
import { EBookCodexDrawer } from "./EBook/EBookCodexDrawer";
import { EBookHeader } from "./EBook/EBookHeader";
import { Toast } from "@/shared/components/feedback/Toast";

export function MasterPlayScreen() {
  const navigate = useNavigate();
  const playthrough = usePlayStore((s) => s.playthrough);
  const theme = usePlayStore((s) => s.ebook_theme);
  const isNarrating = usePlayStore((s) => s.is_narrating);
  const isLeftSidebarOpen = usePlayStore((s) => s.is_left_sidebar_open);
  const isCharacterDrawerOpen = usePlayStore((s) => s.is_right_sidebar_open);
  const isActionDrawerOpen = usePlayStore((s) => s.is_action_drawer_open);
  const isChronicleModalOpen = usePlayStore((s) => s.is_chronicle_modal_open);
  const degradedMessage = usePlayStore((s) => s.degraded_message);

  const toggleLeftSidebar = usePlayStore((s) => s.toggleLeftSidebar);
  const setLeftSidebarOpen = usePlayStore((s) => s.setLeftSidebarOpen);
  const toggleRightSidebar = usePlayStore((s) => s.toggleRightSidebar);
  const setRightSidebarOpen = usePlayStore((s) => s.setRightSidebarOpen);
  const openActionDrawer = usePlayStore((s) => s.openActionDrawer);
  const closeActionDrawer = usePlayStore((s) => s.closeActionDrawer);
  const openChronicleModal = usePlayStore((s) => s.openChronicleModal);
  const closeChronicleModal = usePlayStore((s) => s.closeChronicleModal);
  const continueTurn = usePlayStore((s) => s.continueTurn);
  const retryLastTurn = usePlayStore((s) => s.retryLastTurn);
  const editLastAction = usePlayStore((s) => s.editLastAction);
  const submitTurn = usePlayStore((s) => s.submitTurn);
  const clearDegradedMessage = usePlayStore((s) => s.clearDegradedMessage);

  // Both drawers stay closed by default, matching NewbiePlayScreen's clean
  // reading-first shell.
  useEffect(() => {
    setLeftSidebarOpen(false);
    setRightSidebarOpen(false);
  }, [setLeftSidebarOpen, setRightSidebarOpen]);

  if (!playthrough) return null;

  const isSepia = theme === "antique-sepia";
  const containerTheme = isSepia
    ? "bg-[#f4ebd9] text-[#2c2217] selection:bg-[#e2d5be]"
    : "bg-black text-zinc-200 selection:bg-zinc-800 selection:text-white";

  return (
    <div
      className={`relative h-screen h-[100dvh] w-full flex flex-col overflow-hidden font-sans transition-colors ${containerTheme}`}
    >
      <EBookHeader
        onBack={() => navigate("/play")}
        onOpenCodex={toggleLeftSidebar}
        onOpenChronicle={openChronicleModal}
        activeConditions={playthrough.active_conditions}
      />

      <div className="relative flex-1 min-h-0 w-full flex justify-center overflow-hidden z-10">
        <EBookCanvas />
      </div>

      <EBookBottomBar
        isNarrating={isNarrating}
        isSpectator={playthrough.is_spectator}
        hasTurns={playthrough.turns.length > 0}
        canAct={playthrough.can_act}
        waitingOnLabel={playthrough.next_actor_label}
        onTakeAction={openActionDrawer}
        onContinue={continueTurn}
        onRetry={retryLastTurn}
        onEditAction={editLastAction}
        onOpenCodex={toggleLeftSidebar}
        onOpenCharacterSheet={toggleRightSidebar}
      />

      <EBookActionDrawer
        isOpen={isActionDrawerOpen}
        onClose={closeActionDrawer}
        onSubmit={submitTurn}
        isNarrating={isNarrating}
      />

      <EBookCodexDrawer
        isOpen={isLeftSidebarOpen}
        onClose={toggleLeftSidebar}
      />

      <CharacterDrawer
        isOpen={isCharacterDrawerOpen}
        onClose={toggleRightSidebar}
        playerStats={playthrough.player_stats}
        playerInventory={playthrough.player_inventory}
        entities={playthrough.entities}
        objectives={playthrough.objectives}
      />

      <ChronicleRecapModal
        isOpen={isChronicleModalOpen}
        onClose={closeChronicleModal}
      />

      {degradedMessage && (
        <Toast
          message={degradedMessage}
          type="error"
          onClose={clearDegradedMessage}
        />
      )}
    </div>
  );
}
