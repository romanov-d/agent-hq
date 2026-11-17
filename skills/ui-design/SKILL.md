---
name: ui-design
description: Build interfaces that look designed, not generated. Use when creating or restyling any UI - landing pages, dashboards, app screens, components, emails - and when the user says it looks generic, cheap, "like AI made it", or asks to make it look better.
---

# UI design

Generated interfaces look alike for the same reasons: default fonts, purple gradients,
three equal cards, emoji icons, everything centered, everything the same weight. Avoid
the defaults on purpose.

## 1. Decide before styling

Write three lines first:

- **Who** uses it and in what situation (a florist on a phone between orders; an
  engineer scanning logs on a big screen).
- **One feeling** it should give: calm, fast, premium, playful, serious.
- **One reference** direction in words: "editorial like a print magazine", "dense like
  a trading terminal", "soft like a wellness app".

If the project already has a design system, tokens or components, use them. Consistency
beats novelty.

## 2. Tokens, not one-off values

Define once and reuse: 1-2 font families, a type scale (e.g. 12/14/16/20/28/40), a
spacing scale (4/8/12/16/24/32/48), 2-3 radii, a neutral ramp of 6-8 steps and **one**
accent color (two at most). Support dark mode by redefining tokens, not by
duplicating CSS.

## 3. Hierarchy does the work

- One primary action per screen. Everything else is visibly secondary.
- Contrast in size and weight between levels; avoid everything medium.
- Align to a grid; left-align text blocks; vary section rhythm instead of stacking
  identical cards.
- Numbers in tabular figures; data in tables when people compare.

## 4. Remove before adding

Borders, shadows, gradients, badges and icons each need a job. Prefer spacing and
background tone to separate groups. Real copy beats lorem ipsum; real-looking data
beats "Item 1, Item 2".

## 5. Every state

Design empty, loading, error, long-text, many-items and no-permission states, not only
the happy path. Buttons have hover, focus-visible, active and disabled states. Forms
show errors next to the field and keep the user's input.

## 6. Accessibility and responsiveness

- Text contrast at least 4.5:1, interactive targets at least 40 px on touch.
- Works at 360 px wide without horizontal scroll; check 768 and 1440 too.
- Keyboard: every action reachable, focus visible, Escape closes overlays.
- Respect `prefers-reduced-motion`; animations under 250 ms and purposeful.

## 7. Look at it

Open the result in a browser at mobile and desktop widths and look at it as a user
would. Fix what looks off before reporting. Describe the design choices in one or two
sentences so the user can push back on direction, not pixels.

## Smells to fix on sight

Emoji used as icons; gradient text; more than two accent colors; centered paragraphs
longer than two lines; drop shadows on everything; identical three-column feature
grids; placeholder avatars; "Lorem ipsum"; walls of badges.
