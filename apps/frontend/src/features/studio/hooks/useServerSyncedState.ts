import { useEffect, useRef, useState } from "react";

/**
 * Buffers local edits to a value derived from server data, but re-syncs from
 * the server whenever it changes from outside this component (e.g. the AI
 * assistant applying a suggestion) — as long as the user has no unsaved local
 * edits pending. A plain "seed once from the initial fetch" useState never
 * notices an update that didn't come through this component's own Save.
 */
export const useServerSyncedState = <T>(
  serverValue: T | undefined,
): [T | undefined, (value: T) => void] => {
  const [local, setLocal] = useState<T | undefined>(undefined);
  const lastSyncedSnapshotRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (serverValue === undefined) return;
    const serverSnapshot = JSON.stringify(serverValue);
    const localSnapshot =
      local === undefined ? undefined : JSON.stringify(local);

    if (serverSnapshot === localSnapshot) {
      lastSyncedSnapshotRef.current = serverSnapshot;
      return;
    }
    const hasNoUnsavedEdits =
      local === undefined || localSnapshot === lastSyncedSnapshotRef.current;
    if (hasNoUnsavedEdits) {
      setLocal(serverValue);
      lastSyncedSnapshotRef.current = serverSnapshot;
    }
  }, [serverValue, local]);

  return [local, setLocal];
};
