# Mobile UI corrections after 6.7.0

Campaign setup and rating now use a viewport-sized page with a fixed header/footer and independent scrolling content. The previous text measurement callbacks disagreed about constrained versus natural text height, repeatedly expanding rows. NaturalList explicitly removes the old size callback and wraps text with an unconstrained height. Campaign choices use a compact grid on narrow panels; captions fit the available width and faction artwork remains visible behind translucent panels. Rating uses a faction filter and naturally sized history cards.

The first-class recruitment slider remains visible at all viewport heights. Compact statistics use two columns to reserve room for the slider. Recruitment, tax and market sliders share vector graphics while retaining Kivy's original value/range/touch behavior. The market exchange ratio is inside the price card.

AI chat faction selection keeps light text against the themed background. Its close action now lives in the header and runs on release. Owner removal is deferred until Popup finishes its dismissal callbacks. Android keyboard code binds the actual keyboard_height property, removes unused JNI activity references, cancels delayed scrolling and guards disposed views.

World events use one queued, clipped ticker above navigation. Text cannot draw across the entire screen, and completion/close/removal cancels timers and animations.

Validation uses actual chat and market widgets with an isolated in-memory copy of the database. Tests populate live factions, switch each chat tab, and repeat open/close three times. Additional checks cover stable text heights over extra frames, Android density/font scale, fixed footer geometry, market price grouping, slider graphic reuse and event queue disposal. Existing recruitment and tax action tests remain in the suite.

Previews: [campaign](frontend-campaign-android-fixed.png), [rating](frontend-rating-android-fixed.png), [chat selection](frontend-chat-selected-fixed.png), [chat closed](frontend-chat-closed-fixed.png), [market](frontend-market-fixed.png), [ticker](frontend-event-ticker-fixed.png), [recruitment](unified-recruitment-phone.png).

Physical Android touch/keyboard behavior has not been exercised in this desktop validation pass.

The final repository suite passed all 117 tests. Python changes passed `git diff --check`.
