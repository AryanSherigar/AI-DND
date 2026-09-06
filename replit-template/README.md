# AI-DND Replit Minigame Starter

This is a starter template for building a custom minigame that plugs into an
AI-DND master-mode scenario as a **`replit_embed`** minigame. You build and
host your minigame on [Replit](https://replit.com), paste the deployed URL
into Studio, and the AI-DND platform live-embeds it in a sandboxed iframe
during play. When the player finishes, your game reports the outcome back to
the platform and the story continues.

You don't need to know anything about `postMessage`, iframes, or origins —
`minigame-sdk.js` handles all of that for you. You just call two functions.

---

## 1. Get this template into your own Replit account

**Option A — Import from GitHub (works today):**

1. Go to [replit.com](https://replit.com) and sign in (or create a free account).
2. Click **Create Repl** → **Import from GitHub**.
3. Paste this repository's URL and point the import at the `replit-template/`
   subdirectory (Replit's GitHub import lets you select a subdirectory as the
   Repl root — if it doesn't, import the whole repo and then move/copy the
   contents of `replit-template/` into your Repl's root).
4. Click **Import**. Replit will detect `.replit` and set up a static-site
   Repl automatically.

**Option B — Fork the official template (coming soon):**

Once this repo publishes `replit-template/` as an official Replit Template,
you'll be able to click one link and get your own copy instantly, no manual
GitHub import needed.

> (a stable template URL will be added here once published)

---

## 2. Build your own minigame

Everything in this Repl is yours to change **except `minigame-sdk.js`** —
leave that file exactly as-is.

- `index.html` — your game's markup. Replace freely.
- `style.css` — your game's styling. Replace freely.
- `game.js` — your game's logic. Replace freely.
- `minigame-sdk.js` — **do not edit.** This is the SDK that talks to the
  AI-DND platform. Just make sure `<script src="minigame-sdk.js"></script>`
  loads before your own `game.js` in `index.html` (it already does in this
  template).

The example game included here ("Rune Strike" — click a moving target 8
times before a 10-second timer runs out) shows the two calls you need:

```js
// Call once, as soon as your page has loaded and the player can start playing.
MinigameSDK.ready();

// Call exactly once, when your game ends — win or lose.
MinigameSDK.reportResult({
  outcome_tag: "win", // or "lose"
  score: 8, // optional; any number, e.g. points, time remaining, hits
});
```

That's the entire contract. Build whatever game you want around those two
calls — a puzzle, a reaction-time test, a quiz, anything that runs in a
browser tab.

**Rules of thumb:**

- Call `ready()` **once**, when your game is actually playable (not before
  assets/images finish loading, if that matters for your game).
- Call `reportResult()` **exactly once**, when the game concludes. Calling it
  multiple times, or not at all, will confuse the platform's turn pipeline —
  guard against double-fires (see how `game.js`'s `hasReportedResult` flag
  does this).
- `outcome_tag` must be `"win"` or `"lose"`. `score` is optional.

---

## 3. Deploy it on Replit

1. Click **Deploy** in the top-right of your Repl.
2. Choose the **Static** deployment type — this template has no server-side
   logic, so a static deployment is the right fit (faster, cheaper, and
   doesn't need to stay "awake").
3. Follow Replit's prompts to confirm and deploy.
4. Replit will give you a stable, public URL (something like
   `https://your-repl-name.your-username.repl.co` or a custom domain if you
   set one up). That URL is what you'll paste into Studio.

---

## 4. Connect it to your AI-DND scenario

1. In Studio, open your master-mode scenario and go to the **Minigames** tab.
2. Add a minigame, set its type to **Replit Embed**.
3. Paste your deployed Replit URL into the URL field.
4. Click **Test Connection** to verify the handshake actually works — this
   loads your page in a hidden iframe and waits for the `minigame:ready`
   message your SDK sends. If it doesn't pass, double-check that
   `MinigameSDK.ready()` is actually being called and that your deployment
   is live (not sleeping/asleep on a free tier — give it a few seconds and
   retry).
5. Set your trigger condition, outcome mode, and mutations as normal, then
   save.

---

## The postMessage contract (for the curious / advanced creators)

`minigame-sdk.js` sends two message types from your page (the child) to the
AI-DND platform (the parent):

| When | Message |
|---|---|
| Once, on load | `{ type: "minigame:ready" }` |
| Once, on completion | `{ type: "minigame:result", outcome_tag: "win" \| "lose", score?: number }` |

> **Note:** the AI-DND platform validates the origin/source of these
> messages against the URL you configured in Studio. Your top-level page —
> the one actually deployed at that URL — must be the one calling
> `MinigameSDK.ready()` / `MinigameSDK.reportResult()`. Don't try to relay or
> spoof these messages from a nested iframe inside your own page; only
> messages coming from your configured deployment's origin are accepted.

---

## Publishing this as an official Replit Template (repo maintainers only)

This section is for whoever operates this repository, not for scenario
creators. To turn `replit-template/` into a one-click-fork official Replit
Template with a stable `replit.com/@<org>/<name>` URL:

1. Create a new Repl and import it from this repo's `replit-template/`
   subdirectory (same GitHub-import flow described in §1).
2. Run it and confirm the example game works end-to-end (click the target,
   confirm it reports a result — you can watch this with a simple local test
   harness page that logs `window.addEventListener("message", ...)`).
3. Open the Repl's options menu and select **Publish as Template**.
4. Fill in the template's name, description, and cover image, then publish.
5. Replit gives you a stable, forkable URL in the form
   `replit.com/@<org>/<name>`. Add that URL to §1 of this README, replacing
   the placeholder note.

No API calls are involved — this is a manual, one-time UI flow performed
whenever the template needs to be re-published (e.g. after a breaking change
to `minigame-sdk.js`'s contract).
