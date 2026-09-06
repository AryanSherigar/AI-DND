import React, { useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { useReplitHandshake } from "@/shared/hooks/useReplitHandshake";
import { REPLIT_TEST_CONNECTION_TIMEOUT_MS } from "../../constants/minigame";
import { ReplitTestConnectionButtonProps } from "./ReplitTestConnectionButton.types";

export const ReplitTestConnectionButton: React.FC<
  ReplitTestConnectionButtonProps
> = ({ embedUrl }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isTesting, setIsTesting] = useState(false);
  const { status, retry } = useReplitHandshake(
    iframeRef,
    isTesting ? embedUrl : null,
    REPLIT_TEST_CONNECTION_TIMEOUT_MS,
  );

  const handleTestConnection = (): void => {
    setIsTesting(true);
    retry();
  };

  const isWaiting = isTesting && status === "waiting";

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={handleTestConnection}
        disabled={!embedUrl.trim() || isWaiting}
      >
        {isWaiting ? "Testing…" : "Test Connection"}
      </Button>
      {isTesting && status === "ready" && (
        <p className="text-xs text-emerald-400">Connected!</p>
      )}
      {isTesting && status === "timed_out" && (
        <p className="text-xs text-danger">
          No response — check the URL and that your Repl calls
          MinigameSDK.ready().
        </p>
      )}
      {isTesting && (
        <iframe
          ref={iframeRef}
          src={embedUrl}
          title="Replit connection test"
          hidden
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      )}
    </div>
  );
};
