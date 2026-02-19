# Sovereign Intelligence API — Landing Page

A single-page, static landing page for `sovereign-api.com` that serves as the central hub for marketing, onboarding, and agent discovery.

## Proposed Changes

### Landing Page Structure

| Section | Purpose | Audience |
|---------|---------|----------|
| **Hero** | "The First OpenAI-Compatible API That Accepts Crypto" + CTA | Humans |
| **How It Works** | 3-step visual flow: Earn → Pay → Think | Both |
| **Live API Demo** | Fetches `/v1/models` live, shows JSON | Devs + Agents |
| **Pricing Table** | 3 models, transparent sats pricing | Both |
| **SDK Quickstart** | Drop-in code example in Python | Devs |
| **For Agents** | Machine-readable endpoint info + `.well-known/ai-plugin.json` | Agents |
| **Links** | Blog, Moltbook, Twitter, API docs | Both |

### Style Direction

- **Dark mode** — Fits the hacker/builder aesthetic
- **Neon accent gradients** — Cyan/green glow on dark, feels "sovereign" and "crypto"
- **Monospace code blocks** — For the developer audience
- **Animated terminal** — The live API demo will look like a terminal fetching data
- **No external dependencies** — Pure HTML/CSS/JS, zero frameworks

### Files

#### [NEW] [index.html](file:///c:/Users/rovie%20segubre/agent/landing/index.html)
Single-file landing page with embedded CSS and JS. Sections: Hero, How It Works, Live Demo, Pricing, SDK, For Agents, Footer.

#### [NEW] [.well-known/ai-plugin.json](file:///c:/Users/rovie%20segubre/agent/landing/.well-known/ai-plugin.json)
Machine-readable file that AI agents can discover — standard format for AI plugin discovery. Points to the API endpoint, describes capabilities.

### Deployment Strategy

Host as static files on the GCP server at port 80 alongside the API, or via **Cloudflare Pages** (free, instant, global CDN). Cloudflare Pages is preferred since it keeps the static site separate from the API server.

## Verification Plan

### Automated Tests
- Open the page in browser, verify all sections render
- Click "Try Live Demo" — confirm it fetches from the real API
- Test mobile responsiveness at 375px width

### Manual Verification
- Share the URL and confirm it loads correctly
