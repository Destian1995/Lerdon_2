# Unified front end, 6.7.0

Main menu, campaign setup, tutorial faction selection and author screen now use the same navy/gold components as gameplay windows. Lore and rating use the same theme and responsive flow; campaign controls retain the existing faction, ideology, ally and start actions. Both economy and politics navigation factories create shared strategy buttons.

Button feedback uses a finite 80ms press / 160ms release animation. Pages enter over 220ms, modal windows over 180ms. Motion does not change control positions or sizes. The new menu has no idle particle timers. The visible menu version is now 6.7.0.

Two reported regressions were corrected: transparent hit regions over development card labels remain transparent, and the AI chat's on_dismiss handler removes its AdvisorView owner and disposes keyboard handlers. Close is idempotent.

This release intentionally resets old Android campaign data once, keyed by `RELEASE_DATA_ID`, and clears the artifact icon cache. The packaged database is a cleaned snapshot that preserves game reference data. Subsequent launches preserve the new campaign.

Previews: [menu](frontend-menu-phone.png), [campaign](frontend-campaign-phone.png), [development labels](development-restored.png).
