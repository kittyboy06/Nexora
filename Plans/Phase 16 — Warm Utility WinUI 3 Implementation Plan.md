# Phase 16 — Warm Utility WinUI 3 Implementation Plan

## Objective
Implement the "Warm Utility" design system in the NEXORA WinUI 3 desktop application according to `Plans/NEXORA 1.2 — Visual Design Update Specification.md` and `Plans/NEXORA 1.2 — Warm Utility WinUI 3 Design Document.md`.

---

## Proposed Changes

### 1. Theme Resources (`desktop/Nexora.Desktop/Styles/ThemeResources.xaml`)
- Create `desktop/Nexora.Desktop/Styles/ThemeResources.xaml` containing:
  - `ResourceDictionary.ThemeDictionaries`:
    - `"Dark"` (and `"Default"`): Walnut/brown palette (`#201814` canvas, `#2A201B` surface, `#332720` surface muted, `#493629` surface selected, `#584337` border, `#836451` border strong, `#C9905D` copper accent, `#7EBA8A` success, `#E4B45F` warning, `#F0897F` danger, `#89B7D4` info).
    - `"Light"`: Paper/clay palette (`#F4F0E8` canvas, `#FFFDF8` surface, `#E9E1D4` surface muted, `#E1D2BF` surface selected, `#CDBEAB` border, `#9E8368` border strong, `#855A36` copper accent, `#3E6A4D` success, `#9A651B` warning, `#A33E35` danger, `#456177` info).
    - `"HighContrast"`: High-contrast system color brushes (`SystemColorWindowBrush`, `SystemColorHighlightBrush`, etc.).
  - Standard font and geometric tokens (`FontFamilyUi`, `FontFamilyCode`, `ControlCornerRadius`, `PanelCornerRadius`, `ContainerCornerRadius`).
- Register `ThemeResources.xaml` in `desktop/Nexora.Desktop/App.xaml`.

### 2. Converter & Model Enhancements
- Update `StatusToBrushConverter.cs` to resolve semantic theme brushes from `Application.Current.Resources`.
- Update `StatusToGlyphConverter.cs` to ensure Segoe MDL2 glyphs for all task and system states.
- Introduce `AppThemeMode` enum (`SystemDefault`, `Light`, `Dark`) and integrate runtime switching via `RootGrid.RequestedTheme`.

### 3. Shell & Header Overhaul (`MainWindow.xaml`)
- Remove `<MicaBackdrop />` and apply solid `{ThemeResource CanvasBrush}` to the root.
- Re-style top header with solid `{ThemeResource SurfaceMutedBrush}`, copper accent badge (`AccentCopperBrush`), and Segoe MDL2 glyphs.
- Add 3px solid copper bottom activity rule (`AccentCopperBrush`) to the active navigation tab.
- Eliminate all emojis and generic AI phrases.

### 4. Workspace View Updates
- **Chat View:** Factual placeholders ("Write a message"), solid message surfaces, 3px copper rule on active session, Cascadia Mono for model identifiers.
- **Tasks & Fleet:** Solid table rows, Cascadia Mono task IDs, copper active marker on running task.
- **Desktop Vision:** Solid status bar for active capture, prominent solid Danger Emergency Stop button.
- **Skills & MCP:** Cascadia Mono for config keys and file paths, quiet document reader styling.
- **Settings:** General settings category with System Default / Light / Dark theme selector.

---

## Verification Plan

### Automated Tests
- Run `dotnet build desktop/Nexora.Desktop/Nexora.Desktop.csproj -c Release -p:Platform=x64` to verify XAML compilation and resource resolution.
- Run `dotnet test desktop/Nexora.Desktop.Tests/Nexora.Desktop.Tests.csproj` to verify all unit tests pass.

### Manual Verification
- Launch application in Dark and Light themes.
- Verify zero gradient brushes and zero emojis across all navigation and views.
- Test theme selector in Settings for instant runtime application.
- Build release package with `deploy.bat --skip-backend`.
