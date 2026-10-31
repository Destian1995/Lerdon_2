# Battle UI review

The live replay, after-action report and battle career panel now share the navy/gold strategy window style. Existing faction and hero portraits are reused.

## Live replay

- Two army panels show fighter counts, smooth strength bars with trailing loss bands, floating casualties, impact flashes, portrait shake and pooled sparks.
- Pause, ×1/×2 speed and immediate report controls are available. The result banner reflects the player's side, including a defeat when an attack fails.
- Critical hits and hero arrivals come from simulation events. There are no randomly invented critical hits. Long battles are condensed to at most 16 frames, with actual round ranges and accumulated event counts preserved.
- One 30 Hz clock drives the presentation. Graphics instructions are reused; effects use their own random generator. The clock stops after the result settles and is cancelled on dismissal. The report callback runs once.

## Statistics

- Separate army summaries show initial/remaining fighters, permanent casualties, recovery and newly raised fighters. Vampiric growth cannot conceal battle losses.
- Unit rows show exact counts and portrait thumbnails. Single-unit casualties and recovery are explicit.
- The report accepts real round counts and critical totals. The career panel includes wins, losses, win rate and campaign results.
- The combat formula and random draw sequence remain unchanged. Instrumentation only records existing critical-hit decisions.

## Validation

All 93 repository tests passed, including eight battle tests covering real combat random-sequence parity, critical event logging, replay condensation, casualty accounting, player-relative results, phone layout, graphics reuse and exactly-once dismissal.

Previews use the actual Kivy widgets with fixture battle data at 1000×600 and 640×360:

- [Animated replay](battle-replay.gif)
- [Phone replay](battle-replay-phone.png)
- [Phone result](battle-victory-phone.png)
- [Battle report](battle-report.png)
- [Phone report](battle-report-phone.png)

Android device performance and touch behavior have not been tested in this pass. The previously built APK does not include these changes.
