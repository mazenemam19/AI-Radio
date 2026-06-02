# Specification: Echo FM Rebranding & Landing Page

## Overview
Complete professional rebranding of Echo FM, transforming the one-page control panel into a high-fidelity website. This includes a new creative landing page and a fully restyled control panel to match the new visual identity.

## Rebranding Definition (Antigravity Sync)
*   **Visual Style:** Hybrid "Structured Minimalism" (Clean whitespace meet precise data grids).
*   **Color Palette:** **"Echo Deep"**
    *   Primary: `#1E293B` (Deep Slate)
    *   Secondary: `#334155` (Slate)
    *   Accent: `#10B981` (Smooth Emerald)
    *   Text: `#0F172A` (Ink)
    *   BG: `#F8FAFC` (Off-white)
*   **Typography:** **"Casual Tech"**
    *   Headings: `Space Grotesk` (Modern, smooth, technical)
    *   Body: `Inter` (Standard professional readability)

## Functional Requirements
1.  **New Landing Page (`index.html`):**
    *   **Hero:** "The News, Reimagined" tagline + Listen CTA.
    *   **How it Works:** Visual automation flow (News Feed → AI Synthesis → Radio Broadcast).
    *   **Meet the Crew:** Persona cards for the Anchor, Reporter, Weatherbot, and Philosopher.
2.  **Station Control Panel (`control.html`):**
    *   **Complete UI Overhaul:** Move away from the CRT/Terminal look to the new "Echo Deep" style.
    *   Maintain all functional buttons (Bake, Refresh, Serve).
    *   Use the new color palette for all status indicators.
3.  **Global UI Elements:**
    *   Consistent Navigation Bar & Footer.
    *   Responsive design for mobile/tablet.

## Non-Functional Requirements
*   **Pure Static Bake:** Zero-JS-framework (Plain HTML/CSS/Vanilla JS) to maintain station stability.
*   **Loudness:** Visual elements must maintain WCAG AA contrast ratios.

## Acceptance Criteria
*   Landing page accurately displays station telemetry.
*   Navigation between Landing and Control Panel is seamless.
*   Control panel buttons remain functional after restyling.
*   Visual identity is consistent across all pages.
