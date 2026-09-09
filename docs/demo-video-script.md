# wevr — Demo Video Production Script

**Target runtime:** 2:45 (Devpost limit: 3:00)
**Tools:** ScreenStudio (screen capture + edit), ElevenLabs (voiceover)
**VO tone:** Movie-trailer narrator — deep, deliberate, weighty delivery. Read every line slower and with more gravity than a normal product-demo VO would call for.
**Format:** Ordered beats with target durations, not rigid timestamps — cut to these beats in whatever order your actual clips land, but keep the relative weighting (Creation gets the most time, Outro the least).

## Decisions this script assumes (don't relitigate mid-edit)

- Pitch leads with **Studio as a creator/production tool**; Play is the payoff, not the hook.
- The scenario built on camera is **Master mode**, shown via a few representative steps only — not the full authoring flow.
- **No on-screen text cards or integration badges anywhere.** All cinematic feel comes from VO delivery, not graphics.
- Win/lose stakes are **mentioned, never triggered** on camera — triggering one on demand was ruled out as too fragile for a live recording.
- The Replit-embedded minigame is shown as a **configured, connected option** in Studio — not actually played through.
- Capture the app's **live in-app audio** during the Play beat so the real mood-music crossfade is heard, not added later.
- Closing VO line is **"Keep weaving your fate."**, delivered over the end card.

---

## Beat 1 — Cold Open / Hook
**Target: ~8s**

**SHOT:** Open on the wevr landing page or logo, static or a slow push-in. No text card — just the visual and the narrator.

**VO:**
> "Every story needs someone to run it. wevr is the one who never gets tired."

**AUDIO:** Mute app audio here; this is narrator-only.

---

## Beat 2 — Creation (Studio, Master Mode, with AERO)
**Target: ~65s**

This is the longest beat, and its centerpiece is **AERO** — the AI co-designer built into Studio (`AIChatSidebar`, mounted as a slide-out drawer). AERO isn't autocomplete: it reads the scenario's actual live state (existing entities, facts, conditions, end conditions) and proposes structured, reviewable **action cards** — an entity to add, a win condition to add, etc. — that the creator applies with one click. This is the single most "agentic" moment in the whole video and deserves to be the visual anchor of this beat, not a footnote.

**SHOT SEQUENCE:**
1. On the Studio dashboard, click **"New scenario."**
2. On the mode toggle, click **"Master"** (let "Newbie" flash briefly first so both formats are visible for a second — VO covers it, no need to explain).
3. Fill in **"Scenario title,"** click **"Create Master-Mode Scenario."** Land in the tabbed editor.
4. On the **"People, Places & Things"** tab, click the arrow tab on the right edge of the screen to open the **AERO** drawer.
5. Click the quick-prompt chip **"Add a villain faction with 3 members"** (or type a similar prompt). Let AERO's response stream in — hold on this, it's the moment that sells the whole feature.
6. When the action card(s) appear, click **"+ Add Entity"** (or **"Apply All (n)"** if AERO proposed more than one) — show the entity actually land in the list behind the drawer.
7. Switch tabs to **"Win & Lose Conditions"** while keeping AERO open. Click the quick-prompt chip **"Suggest a win condition for this scenario."** When the card appears, click **"Review Win/Lose Condition"** — this opens the expression review modal; apply it. This is the moment the VO calls out real stakes. Do not attempt to trigger this condition later; it's shown existing, not firing.
8. Close AERO. Cut to the cover art field, click **"Generate with AI."**
9. Cut to the **"Mood Music"** tab — one mood card, short prompt into "Describe the track to generate...", click **"Generate with AI."** Cut to the completed track with **"Confirm"** visible — don't wait through generation live.
10. Cut to **"Setup & Narrator,"** click **"Publish Scenario."** Hold on the success banner: **"Scenario published — it is now live in discovery."**

**VO (read across the full sequence above, pacing to match the cuts):**
> "This is Studio — where a creator becomes a director. And they don't work alone. Meet AERO: an AI co-designer that reads your world as you build it, and proposes the next piece — a character, a rule, a way to win, a way to lose. You review. You approve. The story stays yours. Then let the machine do what machines are good at: painting the cover, scoring the soundtrack. Every choice here is a choice the story will keep."

**AUDIO:** App audio can stay low/muted through this beat — it's mostly UI interaction, not narrated gameplay. Narrator carries it.

---

## Beat 3 — Play: AI Narration + Live Scene Imagery + Mood Music
**Target: ~50s**

**SHOT SEQUENCE:**
1. From the scenario's page, click **"Play now."** Move through setup quickly (cut past the loading screen).
2. Land on the play screen. Show the **"Inscribing Chapter 1..."** streaming text appear with its blinking cursor — hold long enough for a viewer to register it's live, then let it can cut short (don't wait for the full paragraph if it's long).
3. Once the turn resolves, show the **generated scene image** rendering full-width below the chapter text — this is an important beat, hold on it for a second.
4. Open the action drawer via **"Take Action,"** pick a mode (e.g. **"Do"**), type a short action into the textarea, hit **"Submit ↵."**
5. Let a second turn stream in. This time, glance at the mood pill in the header (speaker icon + mood name, e.g. "Tension") as the tone of the narration shifts — briefly show the tooltip **"Soundtrack (Tension) — Click to mute"** if it's easy to catch on screen.
6. Optional third short turn if time allows, to reinforce the loop.

**VO:**
> "Then the story begins — and it doesn't wait for you to be ready. Gemini narrates what happens next, turn by turn, live. It paints the scene as it unfolds. And it listens to its own story closely enough to know when the mood has changed — so the music changes with it."

**AUDIO:** **Capture live in-app audio for this entire beat.** Let the actual mood-music crossfade play under (and briefly over) the narrator's voice as the mood shifts — this is deliberate; it's proof the feature is real, not a claim.

---

## Beat 4 — Minigame Showcase
**Target: ~30s**

**SHOT SEQUENCE (part A — built-in minigame, played live, ~22s):**
1. Trigger the Dodge minigame overlay (via whatever turn action causes it in your prepared scenario). Show the **"Challenge"** badge and the full-screen takeover.
2. Hold briefly on the instructions screen: eyebrow **"Ashfall Dodge,"** heading **"Survive the storm,"** control hints (**"WASD to move,"** etc.).
3. Click **"Start encounter."** Play for a few seconds — enough to show real movement and a hazard or two, not the full clock.
4. Cut to the resolution text (**"Survived!"** or similar) — doesn't need to be a full playthrough, a representative clip is fine.

**SHOT SEQUENCE (part B — Replit option, shown not played, ~8s):**
5. Cut to Studio's **"Minigames"** tab. Click **"New Minigame,"** select **"Custom: Replit Embed"** from the type dropdown, show the URL field with a Replit URL already entered.
6. Click **"Test Connection."** Hold on the green **"Connected!"** result. Do not click "Preview minigame" and do not play it through.

**VO:**
> "Some moments deserve more than words. wevr can drop a player into a real-time challenge mid-story — built in, ready to go. Or a creator can bring their own: build a minigame on Replit, connect it here, and it becomes part of the story too."

**AUDIO:** Let the Dodge minigame's own sound effects play live under the VO for part A. Mute or lower app audio for part B (it's a config screen, no meaningful game audio).

---

## Beat 5 — Outro / End Card
**Target: ~8s**

**SHOT:** Plain end card — wevr logo, hosted URL, repo link, "Built for Agentic Cinema: The Blockbuster Hackathon." No animation needed beyond a simple fade.

**VO:**
> "wevr. Keep weaving your fate."

**AUDIO:** Fade out app/game audio under this line; narrator only for the last few words.

---

## Total: ~161s (2:41) — within the 2:45 target, under Devpost's 3:00 limit.

## Pre-recording checklist

- [ ] Build the Master-mode scenario used in Beat 2 *before* recording starts, or record its creation once, cleanly, and reuse that exact scenario for Beats 3-4.
- [ ] Confirm Gemini/Vertex AI credentials are live so cover art and scenario music actually generate on camera (they fail gracefully but silently if not — don't discover this mid-recording).
- [ ] Have a real Replit URL hosting a minigame that actually calls `MinigameSDK.ready()`, so the "Test Connection" click in Beat 4 genuinely shows "Connected!" rather than the failure state.
- [ ] Decide in advance which action(s) in your scenario trigger the Dodge minigame, so Beat 4 doesn't require live improvisation to find it.
- [ ] Run through the AERO prompts in Beat 2 ("Add a villain faction with 3 members," "Suggest a win condition for this scenario") at least once before recording — it's a live AI call and can be slow or phrase things oddly; know roughly what to expect so you're not narrating over a surprise.
- [ ] Run the VO script through ElevenLabs once early to sanity-check total spoken length before locking picture.
