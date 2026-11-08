# NEXORA 1.2 — Warm Utility WinUI 3 Design Document

## 1. Understanding Summary
- **Target Application:** NEXORA Native Desktop Control Plane (WinUI 3 / .NET 8 / Windows App SDK).
- **Design Philosophy:** "Warm Utility" — quiet, durable, practical desktop visual language based on paper, walnut, clay, copper, and ink. Replaces all previous cyberpunk / blue-navy / neon styling.
- **Key Constraints:**
  - **Zero gradients anywhere** (strictly `SolidColorBrush` in WinUI 3 XAML; no `LinearGradientBrush`, `RadialGradientBrush`, or background acrylic).
  - **Zero emoji**; strictly Windows Fluent / Segoe MDL2 iconography.
  - **Zero generic AI microcopy** (e.g. "How can I help you?"); factual, verb-first labels.
  - **Standard Windows Typography:** `Segoe UI Variable` (fallback `Segoe UI`) for body and UI; `Cascadia Mono` (fallback `Consolas`) for IDs, models, hotkeys, and paths.
  - **First-class Dark & Light themes** with full parity and high-contrast compliance.
  - **Signature copper activity rule:** 3px solid copper marker (`#C9905D` Dark, `#855A36` Light) beside active tasks, selected navigation items, and page headings.
- **Non-Goals:**
  - No continuous animations or glowing accents.
  - No domain model or backend API changes (design-only scope).

---

## 2. Decision Log

| # | Topic | What Was Decided | Alternatives Considered | Rationale |
|---|---|---|---|---|
| **1** | Architecture Approach | **Semantic Theme Resource Dictionary (`ThemeResources.xaml`)** using native `ResourceDictionary.ThemeDictionaries` for `Dark`, `Light`, and `HighContrast`. | Option 2: Full control template overrides (`ControlStyles.xaml`).<br>Option 3: In-line refactoring in `MainWindow.xaml`. | Option 1 is the cleanest standard WinUI 3 architecture. It decouples tokens from view logic, enables instant zero-restart theme switching, preserves Windows High Contrast mode, and requires minimal ongoing maintenance. |
| **2** | Theme Switching | Runtime switching via `RootGrid.RequestedTheme = ElementTheme.Light / Dark / Default` driven by local user configuration. | Application restart upon theme change. | Instant dynamic resolution of `{ThemeResource}` references provides a modern, seamless user experience without losing active task logs or conversation state. |
| **3** | Shell Background | Solid canvas background (`CanvasBrush`), removing `<MicaBackdrop />`. | Retaining Mica / Acrylic backdrops. | Mica allows desktop wallpaper tinting (often dark navy or bright blues) to bleed through, violating the solid paper/walnut Warm Utility aesthetic. |
| **4** | Iconography | Windows Segoe MDL2 Assets and Fluent System glyphs only; zero emoji unicode characters in navigation, buttons, badges, or headers. | Emoji icons or third-party web icon fonts. | Guarantees authentic Windows desktop utility feel and avoids juvenile or platform-dependent emoji rendering. |
| **5** | Status & Accessibility | Three-way indicator for every state: textual label + Segoe MDL2 glyph + semantic status brush. Native high contrast mode strictly mapped to Windows system brushes. | Color-only status indicators or custom high contrast overrides. | Ensures WCAG AAA compliance and accessibility for color-blind users and high-contrast system settings. |

---

## 3. Theme Token Specification

### 3.1 Dark Theme Tokens (`ThemeDictionaries["Dark"]` & `["Default"]`)
| Token Key | Hex Code | Intended Use |
|---|---|---|
| `CanvasBrush` | `#201814` | Window canvas / root background |
| `SurfaceBrush` | `#2A201B` | Primary content panels, cards, dialogs |
| `SurfaceMutedBrush` | `#332720` | Navigation rail, top header, secondary panels |
| `SurfaceSelectedBrush` | `#493629` | Selected navigation item, active row |
| `BorderBrush` | `#584337` | 1px control borders, panel separators |
| `BorderStrongBrush` | `#836451` | Focused border, active frame boundary |
| `TextPrimaryBrush` | `#F3EBDD` | Primary headings, message text, labels |
| `TextSecondaryBrush` | `#C8B8A5` | Metadata, subtitles, timestamps |
| `TextDisabledBrush` | `#8D7C6D` | Disabled controls, inactive status |
| `AccentCopperBrush` | `#C9905D` | Signature copper activity rule, primary action fill |
| `AccentHoverBrush` | `#DEA872` | Pressed / hovered accent button fill |
| `AccentTextBrush` | `#2A1B11` | Text on copper button |
| `StatusSuccessBrush` | `#7EBA8A` | Healthy, completed status |
| `StatusWarningBrush` | `#E4B45F` | Waiting approval, caution |
| `StatusDangerBrush` | `#F0897F` | Failed task, emergency stop fill |
| `StatusInfoBrush` | `#89B7D4` | Information badge, system trace |

### 3.2 Light Theme Tokens (`ThemeDictionaries["Light"]`)
| Token Key | Hex Code | Intended Use |
|---|---|---|
| `CanvasBrush` | `#F4F0E8` | Window canvas / root background |
| `SurfaceBrush` | `#FFFDF8` | Primary content panels, cards, dialogs |
| `SurfaceMutedBrush` | `#E9E1D4` | Navigation rail, top header, secondary panels |
| `SurfaceSelectedBrush` | `#E1D2BF` | Selected navigation item, active row |
| `BorderBrush` | `#CDBEAB` | 1px control borders, panel separators |
| `BorderStrongBrush` | `#9E8368` | Focused border, active frame boundary |
| `TextPrimaryBrush` | `#2C2119` | Primary headings, message text, labels |
| `TextSecondaryBrush` | `#695747` | Metadata, subtitles, timestamps |
| `TextDisabledBrush` | `#9A8B7D` | Disabled controls, inactive status |
| `AccentCopperBrush` | `#855A36` | Signature copper activity rule, primary action fill |
| `AccentHoverBrush` | `#6D482B` | Pressed / hovered accent button fill |
| `AccentTextBrush` | `#FFFFFF` | Text on copper button |
| `StatusSuccessBrush` | `#3E6A4D` | Healthy, completed status |
| `StatusWarningBrush` | `#9A651B` | Waiting approval, caution |
| `StatusDangerBrush` | `#A33E35` | Failed task, emergency stop fill |
| `StatusInfoBrush` | `#456177` | Information badge, system trace |

### 3.3 High-Contrast Theme Tokens (`ThemeDictionaries["HighContrast"]`)
Maps semantic keys directly to Windows system high-contrast theme brushes:
- `CanvasBrush` $\rightarrow$ `SystemColorWindowBrush`
- `SurfaceBrush` $\rightarrow$ `SystemColorWindowBrush`
- `SurfaceMutedBrush` $\rightarrow$ `SystemColorButtonFaceBrush`
- `SurfaceSelectedBrush` $\rightarrow$ `SystemColorHighlightBrush`
- `BorderBrush` $\rightarrow$ `SystemColorWindowTextBrush`
- `TextPrimaryBrush` $\rightarrow$ `SystemColorWindowTextBrush`
- `TextSecondaryBrush` $\rightarrow$ `SystemColorGrayTextBrush`
- `AccentCopperBrush` $\rightarrow$ `SystemColorHighlightBrush`
- `AccentTextBrush` $\rightarrow$ `SystemColorHighlightTextBrush`

### 3.4 Shared Geometry & Font Tokens
- `FontFamilyUi`: `"Segoe UI Variable, Segoe UI"`
- `FontFamilyCode`: `"Cascadia Mono, Consolas"`
- `ControlCornerRadius`: `4`
- `PanelCornerRadius`: `6`
- `ContainerCornerRadius`: `8`

---

## 4. Visual Artifact Reference
- **Dark Theme Screen:** `Plans/nexora-warm-utility-dark.html` & `Plans/nexora-warm-utility-dark.png`
- **Light Theme Screen:** `Plans/nexora-warm-utility-light.html` & `Plans/nexora-warm-utility-light.png`
- **Stitch Project:** `9088176958453806266` (NEXORA 1.2 — Warm Utility Control Plane)
