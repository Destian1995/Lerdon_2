# Unified responsive windows

All Popup entry points use the existing shared navy/gold theme and now also pass through `responsive_ui.WindowFlow`, including custom city, recruitment and battle windows. The static inventory lists 69 factories in 20 files; this describes routing coverage, not manual execution of every game branch.

## Layout changes

- Measure text at its actual font and available width. Expand rows and vertical groups instead of squeezing neighboring controls together.
- Keep action heights at least 48dp; stack button rows when captions need more width. Small arrow controls remain in a horizontal row.
- Scroll overflowing content, including long descriptions, internal lists and recruitment cards. Preserve widget instances and game callbacks.
- Clamp legacy dialogs to the viewport and enforce useful minimum sizes for interactive dialogs. Recalculate after SDL finishes updating window dimensions on rotation.
- Replace troop selection's five-column table with portrait cards and correct per-row callback capture. Preserve individual selection, class 1–3 bulk selection and dispatch.
- Replace campaign results' absolutely positioned table with faction summaries. Events and ordinary messages now use vertical layouts. Diplomatic messages use a framed, scrollable card.
- Stack artifact shop panels on narrow screens; place equipment in a grid below the portrait. This layout no longer writes pixel coordinates to the game database.
- Preserve image-backed buttons when applying the common skin, including images assigned after opening.
- Make economy/politics bottom navigation horizontally scrollable instead of narrowing all five actions.
- Add the shared frame and overflow handling to map loading.

## Validation

Regression tests run actual Kivy widget layouts and callbacks. The mobile matrix includes 320×568, 360×640, 640×360, and 1280×720 at density 2, plus font scales up to 1.5. Tests cover overflow, action separation, rotation in both directions, dynamic content, troop selection, real events/messages, diplomacy, equipment geometry, image-backed buttons, recruitment navigation, and bottom navigation.

The final repository run passed all 103 tests. Python changes passed `git diff --check`.

Previews:

- [Troops, landscape](responsive-troops-phone.png)
- [Troops, portrait](responsive-troops-portrait.png)
- [Campaign results, larger font](responsive-results-large-font.png)
- [Event, larger font](responsive-event-large-font.png)
- [Diplomatic message, larger font](responsive-diplomacy-large-font.png)
- [Recruitment](unified-recruitment-phone.png)

These checks use desktop SDL/Kivy with Android-like density and font settings. A physical Android build, device-specific system bars, and the on-screen keyboard have not been validated in this pass. A guarantee for every Android device cannot be inferred from desktop rendering.
