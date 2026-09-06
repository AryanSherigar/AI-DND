/**
 * Rune Strike — example minigame demonstrating the MinigameSDK contract.
 *
 * This file is the part a creator is meant to replace with their own game.
 * The only two things that matter for the platform integration are:
 *   1. MinigameSDK.ready() is called once the page can actually be played.
 *   2. MinigameSDK.reportResult({ outcome_tag, score }) is called exactly
 *      once, when the game ends (win or lose).
 * Everything else below is just this particular game's logic.
 */
(function () {
  "use strict";

  var GAME_DURATION_SECONDS = 10;
  var HITS_TO_WIN = 8;
  var TICK_MS = 100;

  var arena = document.getElementById("arena");
  var target = document.getElementById("target");
  var timerEl = document.getElementById("timer");
  var hitsEl = document.getElementById("hits");
  var overlay = document.getElementById("overlay");
  var overlayMessage = document.getElementById("overlay-message");
  var restartButton = document.getElementById("restart");

  var hits = 0;
  var remainingSeconds = GAME_DURATION_SECONDS;
  var tickHandle = null;
  var hasReportedResult = false;

  function randomPosition() {
    var arenaRect = arena.getBoundingClientRect();
    var maxX = Math.max(arenaRect.width - target.offsetWidth, 0);
    var maxY = Math.max(arenaRect.height - target.offsetHeight, 0);
    return {
      x: Math.random() * maxX,
      y: Math.random() * maxY,
    };
  }

  function moveTarget() {
    var position = randomPosition();
    target.style.left = position.x + "px";
    target.style.top = position.y + "px";
  }

  function updateHud() {
    timerEl.textContent = remainingSeconds.toFixed(1);
    hitsEl.textContent = String(hits);
  }

  function handleTargetClick() {
    if (hasReportedResult) {
      return;
    }
    hits += 1;
    updateHud();
    if (hits >= HITS_TO_WIN) {
      finishGame("win");
      return;
    }
    moveTarget();
  }

  function tick() {
    remainingSeconds = Math.max(remainingSeconds - TICK_MS / 1000, 0);
    updateHud();
    if (remainingSeconds <= 0) {
      finishGame("lose");
    }
  }

  function finishGame(outcomeTag) {
    if (hasReportedResult) {
      return;
    }
    hasReportedResult = true;
    clearInterval(tickHandle);
    target.disabled = true;

    overlayMessage.textContent =
      outcomeTag === "win" ? "Rune bound! Victory." : "Time's up. The rune fades.";
    overlayMessage.setAttribute("data-outcome", outcomeTag);
    overlay.hidden = false;

    MinigameSDK.reportResult({ outcome_tag: outcomeTag, score: hits });
  }

  function resetGame() {
    hits = 0;
    remainingSeconds = GAME_DURATION_SECONDS;
    hasReportedResult = false;
    target.disabled = false;
    overlay.hidden = true;
    updateHud();
    moveTarget();
    clearInterval(tickHandle);
    tickHandle = setInterval(tick, TICK_MS);
  }

  target.addEventListener("click", handleTargetClick);
  restartButton.addEventListener("click", resetGame);

  window.addEventListener("load", function () {
    resetGame();
    MinigameSDK.ready();
  });
})();
