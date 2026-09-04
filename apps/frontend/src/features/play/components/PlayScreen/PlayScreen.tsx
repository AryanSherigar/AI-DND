import { usePlayStore } from "../../stores/play.store";
import { MasterPlayScreen } from "./MasterPlayScreen";
import { NewbiePlayScreen } from "./NewbiePlayScreen";

export function PlayScreen() {
  const mode = usePlayStore((s) => s.playthrough?.mode) ?? "newbie";
  return mode === "master" ? <MasterPlayScreen /> : <NewbiePlayScreen />;
}
