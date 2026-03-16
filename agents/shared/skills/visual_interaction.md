---
name: Visual Interaction Protocol
description: General protocol for navigating GUIs, browsers, and visual interfaces — plan, act, verify loop with vision intelligence
type: feedback
---

# Visual Interaction Protocol

A structured cognitive framework for any task that involves interacting with visual interfaces (browsers, apps, desktops). This protocol applies to **any goal**, not just specific tasks.

## Core Principle

**You have no eyes. You must build a mental model of the world through deliberate observation, action, and verification — never assumption.**

---

## Phase 1: Strategic Planning (Think Before Touching)

Before touching anything, state your plan **out loud** (in your reasoning):

1. **What is my goal?** (one sentence)
2. **What are the prerequisites?** (what do I need before I can even start?)
3. **What is my general sequence of steps?** (high-level, not detailed — you don't know what you'll encounter)

**Do NOT over-plan details.** You don't know what you don't know. The physical/visual world requires exploration. Plan strategically, execute tactically.

### Example
> Goal: Play chess against a bot on chess.com
> Prerequisites: A browser (Chrome preferred), the URL, screen space that doesn't block the user's terminal
> General steps: (1) Arrange windows, (2) Navigate to the page, (3) Find and click "Play", (4) Start a game

---

## Phase 2: Environment Respect

Before opening or changing anything visible:

1. **Capture the current state** — What apps are open? Where is the user's terminal? What are its coordinates and size?
2. **Get screen dimensions** — Know the total canvas you're working with.
3. **Calculate your space** — Position your window (browser, app) so it does NOT obstruct the user's workspace.
4. **Open/resize accordingly** — Place your window in the remaining space.

**Why:** The user lives in this environment. Blocking their terminal means they can't communicate with you. Always preserve their workspace.

---

## Phase 3: Act Like a Human

When performing interactions:

- **Type a URL → press Enter.** Don't analyze autocomplete dropdowns, don't click suggestions. Humans type and hit Enter.
- **Click buttons directly.** Don't hover, don't wait for tooltips, don't read every element first.
- **One action at a time.** Do one thing, then verify. Don't chain 5 actions blindly.
- **Don't get distracted by noise.** Popups, ads, cookie banners — handle them only if they block your path. Otherwise ignore.

---

## Phase 4: Observe — The 6-Dimension Scan

After any navigation or significant action, **take a screenshot** and send it to the vision model with this prompt structure:

### The Observation Prompt Template

```
Context: I am trying to [GOAL]. I just [ACTION I TOOK].

Hypothesis: I expect to see [WHAT I THINK SHOULD BE ON SCREEN].

Could you confirm whether my hypothesis is correct?

Then, please analyze the screen systematically:
1. Left to right — what do you see?
2. Right to left — anything you missed?
3. Top to bottom — what's the vertical layout?
4. Bottom to top — anything at the bottom you might overlook?
5. Center outward — what's the most prominent element?
6. Edges inward — what's at the periphery?

Collapse these 6 perspectives into a single, truthful description of everything on screen.
```

### Why 6 Dimensions?

Each scan direction catches things the others miss. The center-outward scan catches modals and prominent CTAs. The edge-inward scan catches nav bars, footers, and dismissible banners. Collapsing all 6 gives you **the truth**.

---

## Phase 5: Decide Next Action

From the observation, identify:

1. **What is the most relevant interactive element** for my goal? (a button, a link, a form field)
2. **What is it called?** (text label, aria label, id)
3. **Where is it?** (general position — you may need coordinates later)

Then decide your action: click it, type into it, scroll, etc.

---

## Phase 6: Execute with Plan A / Plan B

Always have two approaches:

### Plan A: Programmatic (fast, reliable)
- Use DOM inspection (Playwright, browser tools) to find the element by selector, ID, text content, or aria label
- Trigger a programmatic click/interaction
- This is faster and doesn't require coordinate math

### Plan B: Coordinate-based (fallback)
- If Plan A fails (anti-bot protection, dynamic elements, iframes), ask the vision model:
  ```
  I need to click the [ELEMENT DESCRIPTION] button.
  Based on this screenshot, what are the pixel coordinates
  of that element's center?
  ```
- Use the coordinates to simulate a mouse click
- **Be aware of resolution scaling** — screenshot resolution may differ from actual screen coordinates. Do the math.

### When to use which:
- **Try Plan A first** — it's faster and more reliable
- **Fall back to Plan B** only when Plan A fails or isn't feasible
- **You can also combine them** — use DOM to confirm existence, vision for coordinates

---

## Phase 7: Verify After Every Action

**You never know if your action worked until you check.** After every significant interaction:

### Fast verification (Playwright/DOM):
- Did the element disappear from the DOM?
- Did a new element appear?
- Did a CSS class change (e.g., `hidden`, `display: none`)?
- Did the URL change?

### Deep verification (Vision):
- Take a screenshot and send it with an **expectation tree**:

```
I just clicked [ELEMENT]. My expectations:

IF successful:
- The [modal/page/element] should have [changed/disappeared/appeared]
- I should now see [expected new state]

IF unsuccessful:
- The screen should look the same as before
- Or there might be an error message

Which case is it? If successful, what should I do next to continue
toward my goal of [GOAL]?
```

### Why expectation trees matter:
By giving the vision model your branching expectations, you get **actionable** responses. Instead of a vague description, you get "Yes, case 1 — the modal is gone and I can see a Play button at the bottom right."

---

## Phase 8: Iterate

Repeat Phases 4-7 until the goal is achieved. Each cycle:
1. Observe (screenshot + 6-dimension scan)
2. Decide (what to interact with next)
3. Execute (Plan A, then Plan B if needed)
4. Verify (fast check + vision confirmation if needed)

---

## Anti-Patterns to Avoid

| Bad | Good |
|-----|------|
| Taking 5 actions without checking results | One action, then verify |
| Guessing what's on screen | Taking a screenshot and asking |
| Getting distracted by dropdowns/suggestions | Ignoring noise, acting like a human |
| Retrying the same failed action 10 times | Switching to Plan B after 2 failures |
| Sending a screenshot without context | Always including goal, hypothesis, and expectations |
| Over-planning details before seeing the screen | Planning strategically, exploring tactically |
| Blocking the user's terminal/workspace | Measuring and positioning windows deliberately |
| Asking vision "what do you see?" with no context | Asking with goal, hypothesis, and 6-dimension scan |

---

## Quick Reference Checklist

Before starting any visual interaction task:

- [ ] State goal and prerequisites out loud
- [ ] Capture current window positions (protect user's workspace)
- [ ] Get screen dimensions
- [ ] Position your window without blocking the user

For each step:

- [ ] Act like a human (simple, direct actions)
- [ ] Screenshot after action
- [ ] Send to vision with: context, hypothesis, 6-dimension scan request
- [ ] Identify next interactive element
- [ ] Execute with Plan A (DOM) or Plan B (coordinates)
- [ ] Verify with expectation tree
- [ ] Proceed or adjust based on verification
