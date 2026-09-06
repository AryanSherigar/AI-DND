/**
 * MinigameSDK — a tiny postMessage wrapper for AI-DND "replit_embed" minigames.
 *
 * Include this file unmodified via <script src="minigame-sdk.js"></script>.
 * It is dependency-free vanilla JS and defines a single global: window.MinigameSDK.
 *
 * Contract (must stay in sync with the AI-DND platform's receiving side and
 * the README in this same directory):
 *   Child (this Repl) -> Parent (the AI-DND platform, via window.parent):
 *     1. { type: "minigame:ready" }
 *        Sent exactly once, when your page has finished loading and the
 *        player can actually start playing.
 *     2. { type: "minigame:result", outcome_tag: "win" | "lose", score?: number }
 *        Sent exactly once, when the minigame concludes.
 */
(function (global) {
  "use strict";

  var VALID_OUTCOME_TAGS = ["win", "lose"];

  /**
   * NOTE: We post with target origin "*" rather than a specific origin.
   * This SDK runs inside a creator's own Repl, and at authoring time it has
   * no way to know which origin the AI-DND platform will be embedding it
   * from (local dev, staging, production all differ). Using "*" here is a
   * deliberate choice, not an oversight — origin *validation* is the
   * receiving parent's job (it checks the message against the
   * replit_embed_url the creator configured in Studio), not this SDK's.
   */
  function postToParent(message) {
    global.parent.postMessage(message, "*");
  }

  function ready() {
    postToParent({ type: "minigame:ready" });
  }

  function reportResult(result) {
    result = result || {};
    var outcomeTag = result.outcome_tag;
    var score = result.score;

    if (VALID_OUTCOME_TAGS.indexOf(outcomeTag) === -1) {
      // NOTE: We still send the message even when outcome_tag looks wrong.
      // Failing loudly but silently (i.e. not sending anything) would leave
      // the player's minigame stuck with no way to resolve — the platform's
      // timeout/retry path is a worse outcome than forwarding a possibly
      // malformed tag and letting the platform's own validation decide.
      console.warn(
        'MinigameSDK.reportResult: outcome_tag should be "win" or "lose", got: ' +
          JSON.stringify(outcomeTag)
      );
    }

    if (score !== undefined && typeof score !== "number") {
      console.warn(
        "MinigameSDK.reportResult: score should be a number if provided, got: " +
          typeof score
      );
    }

    var message = { type: "minigame:result", outcome_tag: outcomeTag };
    if (score !== undefined) {
      message.score = score;
    }
    postToParent(message);
  }

  global.MinigameSDK = {
    ready: ready,
    reportResult: reportResult,
  };
})(window);
