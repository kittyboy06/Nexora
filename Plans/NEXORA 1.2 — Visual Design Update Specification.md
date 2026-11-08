# NEXORA 1.2 — Visual Design Update Specification

## Status and precedence

This document updates the visual direction in the earlier NEXORA 1.2 UI specification. Its requirements take precedence wherever colors, typography, decorative treatment, copy style, or theme behavior conflict with the earlier document.

This is a design specification only. It does not authorize application-code changes.

## 1. Design objective

NEXORA should look like a durable Windows productivity application made for long sessions, not a concept demonstration or a generated dashboard.

The visual character is **quiet, practical, and deliberate**:

- warm brown-based surfaces rather than blue/black “AI” styling;
- familiar readable typography rather than stylized display fonts;
- solid colors only, with no gradients;
- plain, specific interface labels rather than decorative microcopy;
- strong hierarchy through spacing, borders, weight, and color contrast;
- both light and dark themes with equal quality and coverage.

The product should feel trustworthy before it feels futuristic.

## 2. Non-negotiable anti-pattern rules

### 2.1 No generated-app visual cues

The following are prohibited in every NEXORA screen:

1. Dark navy/blue gradient page backgrounds, card gradients, mesh gradients, animated color washes, or aurora effects.
2. Large glowing or neon AI motifs, “orb” decorations, floating particles, glassmorphism panels, and decorative noise overlays.
3. Overly rounded cards used as the primary layout system. Use restrained radii and clear structure instead.
4. Excessive status chips, promotional callouts, or empty whitespace used only for visual drama.
5. Generic AI-assistant phrases such as “How can I help you today?”, “Let’s build something amazing”, “Your intelligent workspace”, or “Ready when you are”.
6. Emoji in navigation, buttons, badges, empty states, task status, or settings labels.
7. Labels beginning with `/` merely to imitate command-palette or developer-tool aesthetics. A slash is allowed only when it is real content, such as a file path, endpoint, or command the user explicitly needs to see.
8. Decorative icons that duplicate the label. Use one familiar Fluent/Windows icon only when it improves recognition.
9. “Vibe-coded” naming: avoid labels such as *Magic*, *Spark*, *Pulse*, *Cosmic*, *Neural*, *Hyper*, *Flow*, or *Smart Mode* unless they represent a real technical feature.

### 2.2 Content and copy rules

Use short, plain labels that describe the action or state.

| Avoid | Use instead |
|---|---|
| Ask NEXORA anything | New conversation |
| AI is thinking | Generating response |
| Magic task creation | Create task |
| Neural workflow | Task workflow |
| Explore the possibilities | Browse skills |
| Connect your universe | Add MCP server |
| Start your journey | Start desktop session |
| `/new`, `/model`, `/skills` labels | New chat, Model, Skills |

System messages must be factual: “The local model is unavailable.” “Approval is required before this action can continue.” “The task completed with two warnings.”

## 3. Visual direction

### 3.1 Named direction: Warm Utility

Warm Utility is a practical desktop visual language based on paper, walnut, clay, and ink. It uses solid brown and neutral surfaces, modest borders, and ordinary Windows typography. The interface is dense enough for work, but not cramped.

The recognisable design anchor is a **thin solid copper activity rule**. It appears beside an active task, a selected chat, and the current page heading. It is a structural marker, not an animated effect or decorative glow.

### 3.2 Layout principles

- Use stable rectangular regions: navigation, command bar, content, optional inspector.
- Let content width and alignment create hierarchy; avoid overlapping panels.
- Use spacing in a four-pixel rhythm: 4, 8, 12, 16, 24, 32, 48.
- Use a small corner radius: 4px for controls, 6px for panels, 8px only for dialogs and larger containers.
- Prefer one primary action per region. Secondary actions should be text buttons, split buttons, menus, or a toolbar.
- Use solid 1px separators and subtle surface contrast instead of shadows. Shadows are reserved for modal dialogs and floating menus.
- Do not animate background color or use continuous decorative animation.

## 4. Typography

### 4.1 Font selection

Use normal Windows fonts already familiar to Windows users:

- **Primary UI font:** Segoe UI Variable, falling back to Segoe UI.
- **Code, model names, paths, IDs, hashes:** Cascadia Mono, falling back to Consolas.
- **Do not use:** novelty display fonts, handwritten fonts, oversized serif headlines, monospaced text for normal UI, or “sci-fi” fonts.

### 4.2 Type scale

| Token | Size / line height | Weight | Use |
|---|---:|---:|---|
| Display | 32 / 40 | 600 | Rare: empty-state or welcome title only. |
| Page title | 24 / 32 | 600 | Main page title. |
| Section title | 18 / 24 | 600 | Major panel/section. |
| Subsection | 14 / 20 | 600 | Groups and cards. |
| Body | 14 / 20 | 400 | Default text. |
| Body compact | 13 / 18 | 400 | Tables, task timeline, supporting text. |
| Caption | 12 / 16 | 400 | Metadata, time, helper text. |
| Button | 14 / 20 | 600 | All standard buttons. |

Avoid all-caps headings except short table columns or very small category labels. If a category label is all caps, its letter spacing must remain subtle and it must never be used as decorative filler.

## 5. Color system

### 5.1 Core principles

1. Every surface is a **solid color**. No CSS/XAML gradient brushes are permitted.
2. Browns are structural colors, not a sepia filter. Preserve neutral whites and near-black text for readability.
3. Accent color communicates selection and active work; it is not used everywhere.
4. Theme changes alter the full token set. Do not simply invert text and background colors.
5. Status colors always appear with text and an icon. Color alone cannot communicate state.

### 5.2 Light theme tokens

| Token | Hex | Intended use |
|---|---|---|
| `Canvas` | `#F4F0E8` | Window background. |
| `Surface` | `#FFFDF8` | Primary content panels, dialogs. |
| `SurfaceMuted` | `#E9E1D4` | Navigation rail, secondary panels. |
| `SurfaceSelected` | `#E1D2BF` | Selected row or active navigation item. |
| `Border` | `#CDBEAB` | Separators, control borders. |
| `BorderStrong` | `#9E8368` | Focused/important structural boundary. |
| `TextPrimary` | `#2C2119` | Primary text. |
| `TextSecondary` | `#695747` | Supporting text. |
| `TextDisabled` | `#9A8B7D` | Disabled text. |
| `Accent` | `#855A36` | Selected states, active rule, primary buttons. |
| `AccentHover` | `#6D482B` | Hover/pressed accent. |
| `AccentText` | `#FFFFFF` | Text on accent. |
| `Success` | `#3E6A4D` | Completed/healthy. |
| `Warning` | `#9A651B` | Attention/approval waiting. |
| `Danger` | `#A33E35` | Error/stop/destructive. |
| `Info` | `#456177` | Informational state only. |

### 5.3 Dark theme tokens

| Token | Hex | Intended use |
|---|---|---|
| `Canvas` | `#201814` | Window background. |
| `Surface` | `#2A201B` | Primary content panels, dialogs. |
| `SurfaceMuted` | `#332720` | Navigation rail, secondary panels. |
| `SurfaceSelected` | `#493629` | Selected row or active navigation item. |
| `Border` | `#584337` | Separators, control borders. |
| `BorderStrong` | `#836451` | Focused/important structural boundary. |
| `TextPrimary` | `#F3EBDD` | Primary text. |
| `TextSecondary` | `#C8B8A5` | Supporting text. |
| `TextDisabled` | `#8D7C6D` | Disabled text. |
| `Accent` | `#C9905D` | Selected states, active rule, primary buttons. |
| `AccentHover` | `#DEA872` | Hover/pressed accent. |
| `AccentText` | `#2A1B11` | Text on accent. |
| `Success` | `#7EBA8A` | Completed/healthy. |
| `Warning` | `#E4B45F` | Attention/approval waiting. |
| `Danger` | `#F0897F` | Error/stop/destructive. |
| `Info` | `#89B7D4` | Informational state only. |

### 5.4 Semantic status mapping

| State | Label | Color token | Required supporting treatment |
|---|---|---|---|
| Running | Running | Accent | Copper rule + plain status text. |
| Healthy/completed | Complete / Healthy | Success | Check icon and date/time. |
| Awaiting user | Approval required | Warning | Explicit action buttons. |
| Failed | Failed | Danger | Error summary plus recovery action. |
| Paused | Paused | TextSecondary | Resume action. |
| Disabled | Disabled | TextDisabled | Reason or enable action. |

## 6. Theme behavior

### 6.1 Required options

Settings must offer:

1. **System default** — follows Windows theme preference.
2. **Light** — always use the Light token set.
3. **Dark** — always use the Dark token set.

The currently selected setting applies immediately and persists locally. Use the system’s high-contrast mode when it is enabled; do not override it with custom brown colors.

### 6.2 Theme coverage

Both themes must style every surface consistently:

- app shell and navigation;
- command bar, search, buttons, menus, tooltips;
- chat transcript and composer;
- work cards, task tables, timeline, DAG nodes;
- skill preview and Markdown renderer;
- MCP review, vault, and test log;
- research citations and quarantine lists;
- Desktop Vision session, capture indicator, and emergency stop;
- scheduler, memory, approvals, audit, settings;
- empty, loading, offline, disabled, error, and confirmation states.

No screen may use a leftover blue gradient, purple default control, or unreadable dark-mode inversion.

## 7. Component specifications

### 7.1 Navigation

- Solid `SurfaceMuted` background.
- Selected page uses `SurfaceSelected`, a 3px solid `Accent` left rule, and `TextPrimary` label.
- Use standard Fluent/WinUI glyphs with text labels. Never use emoji.
- Do not use floating or translucent navigation items.

### 7.2 Buttons

| Type | Visual treatment | Use |
|---|---|---|
| Primary | Solid Accent fill, AccentText text, 4px radius | One primary action per context. |
| Secondary | Solid Surface/SurfaceMuted fill, Border border | Supporting actions. |
| Tertiary | Text only, Accent text | Low-emphasis actions. |
| Destructive | Solid Danger fill only in explicit confirmation or emergency stop context | Cancel/delete/stop actions. |
| Split button | Standard WinUI split button; no custom flourish | Actions with an approved menu. |

All button labels must start with a verb where possible: **Create task**, **Open folder**, **Review server**, **Stop session**, **Export evidence**.

### 7.3 Panels and cards

- Use panels only to group related controls or results.
- Solid `Surface` fill, 1px `Border`, 6px radius.
- Do not place cards inside cards unless the inner region is a real interactive record (for example a task within a conversation).
- No gradient borders, glow, glass blur, or elevated “marketing” shadow.

### 7.4 Chat

- Chat background remains `Canvas`; messages are aligned through layout, not large colored bubbles.
- User message: subtle `SurfaceMuted` block or plain aligned text.
- Assistant message: plain `Surface` block with a small metadata row.
- Work cards: factual title, status, destination, model, permission state, and one primary action.
- Composer: solid `Surface`, clear border, standard Send button. Do not use placeholder copy such as “Ask anything.” Use “Write a message” or context-specific text.

### 7.5 Tables and lists

- Prefer tables for dense operational records: tasks, MCP servers, schedules, audit entries, memory.
- Use alternating surface only if it improves readability; never use zebra stripes plus card borders together.
- Selected row uses `SurfaceSelected`; status uses semantic chip plus text.
- Keep filter bars compact and persistent for data-heavy pages.

### 7.6 Dialogs and confirmations

- Use native WinUI dialog patterns.
- Title names the consequence: “Stop desktop session?” not “Are you sure?”
- Body identifies target, effects, and whether work can be resumed.
- Primary destructive action is Danger; cancel is secondary.
- Never use emoji, decorative illustrations, or motivational language in confirmations.

## 8. Per-screen visual notes

### Chat

- Page title: “Chat” or the conversation name.
- Use a compact status line: “Local model connected” or “Model unavailable.”
- The active conversation is marked with a copper left rule; no animated signal spine or glowing dot.

### Tasks and Fleet

- Default to a table/list for task management and a clean graph for dependency inspection.
- Use brown-neutral node surfaces; reserve Accent for the selected/active node.
- Avoid futuristic graph lines, animations, or decorative grid backgrounds.

### Skills and GitHub preview

- README previews resemble a normal document reader: `Surface` page, standard Markdown typography, quiet borders.
- External provenance is a compact metadata table, not a banner.
- Warnings are solid warning panels with specific text.

### MCP

- Treat configuration as operational infrastructure: form labels, code-like values in Cascadia Mono, review diffs, and plain status.
- Approved status must never appear more visually prominent than a warning about unreviewed changes.

### Desktop Vision

- Make the capture state impossible to miss using a solid status bar: “Screen capture active — [Target window]”.
- The emergency Stop button is always visible, solid Danger, and text-labeled.
- Screenshots/evidence are shown as records with timestamps and protection/redaction status; no decorative image gallery treatment.

### Settings

- Use a left category list and right settings form.
- Theme setting appears under General at the top, with System default / Light / Dark radio choices.
- Each dangerous setting has a one-sentence explanation and a safe default.

## 9. Accessibility requirements

1. Minimum contrast: 4.5:1 for normal text; 3:1 for large text and non-text UI boundaries.
2. Keyboard focus uses a visible solid `BorderStrong` outline. Do not rely on glow or animation.
3. Every icon-only control has an accessible name and tooltip.
4. Status information uses text plus icon plus color.
5. Respect Windows reduced-motion preference. All nonessential animation is disabled by default.
6. Respect Windows high-contrast mode over custom theme preferences.
7. The light and dark themes must be manually reviewed at 100%, 125%, 150%, and 200% scaling.

## 10. Implementation rules for WinUI 3

- Define all colors through semantic XAML resource keys. Screens use semantic resources, never hard-coded page-specific colors.
- Define Light, Dark, and HighContrast resource dictionaries.
- Do not use `LinearGradientBrush`, `RadialGradientBrush`, acrylic/blur as a primary surface, or animated background brushes.
- Use WinUI system typography resources where available; use Segoe UI Variable for normal text and Cascadia Mono only for code-like content.
- Use Fluent System Icons/WinUI symbols, not emoji text characters.
- Add visual regression screenshots for the Chat, Tasks, Skills, MCP, Desktop Vision, and Settings screens in both themes.

## 11. Designer and implementation acceptance checklist

- [ ] No gradients anywhere in the application.
- [ ] No emoji used as UI elements.
- [ ] No decorative `/` command labels or generated-app terminology.
- [ ] Brown-based light and dark themes use the defined semantic token sets.
- [ ] Standard readable Windows typography is used throughout.
- [ ] Both themes cover all screens, dialogs, menus, error states, and companion UI.
- [ ] Active, selected, warning, and error states remain understandable without color alone.
- [ ] Desktop Vision’s active capture and emergency stop are prominent and plain-language.
- [ ] Screens have been reviewed for normal Windows scale and high-contrast mode.
