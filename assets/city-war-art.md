# Захват, дым и разрушение городов

## Правила

- Мирное присоединение: цвет фракции, золотые искры и плавные кольца.
- Боевой захват: оранжевая вспышка, разлетающиеся частицы и цвет победителя.
- Бой без смены владельца также отмечается отдельным эффектом.
- Анимация захвата ждёт закрытия окна битвы/отчёта, чтобы игрок увидел её на карте.
- После обычного боя дым виден в ход сражения и ещё два хода.
- При силе **каждой** участвующей армии от **20 000 000** город становится руинами,
  даже если защитник удержал его. Здания в нём уничтожаются.
- Сила фиксируется до потерь и временных боевых модификаторов:
  `(атака × коэффициент класса + защита + живучесть) × количество`.
  Это формула силы из ИИ; учитываются участвующие стеки, включая союзников.
- Руины сохраняются в БД и продолжают слегка дымиться до восстановления.
- Отстройка 25 зданий владельца запускает восстановление на следующем ходу.
  Новый крупный бой сбрасывает восстановление. Мирная смена владельца руины не лечит.
- Для обычных фракций используется разрушенный город; для городов нежити —
  разрушенная готическая крепость. Фракция по-прежнему указана в подписи и территории.
- При открытии сохранённого состояния старые вспышки не воспроизводятся заново.
  Дым и текущая иконка восстанавливаются из данных.

## Арт

Использован встроенный `image_gen` через навык imagegen, режим редактирования.
Оригиналы `files/buildings/default.png` и `castle_death.png` сохранены.
Итоговые RGBA PNG уменьшены до 256×256 с Lanczos, альфа сохранена;
дым не нарисован в PNG — он анимируется отдельно.

| Иконка | Исходник | Итог |
|---|---|---|
| Обычные руины | `files/buildings/default.png` | `files/buildings/ruined/town.png` |
| Крепость нежити | `files/buildings/castle_death.png` | `files/buildings/ruined/undead.png` |

### Prompt: town

Use case: precise-object-edit. Edit target: supplied fantasy town icon. Create its WAR-RUINED state for a strategy map, same camera, same footprint, transparent RGBA background. Preserve the town's red tile roofs, warm beige stone and timber identity, but show unmistakable heavy battle destruction: clock bell tower snapped in half, collapsed roofs exposing rafters, breached arch, charred houses, rubble spilling into the courtyard. Retain 35 percent of recognizable standing buildings, majority destroyed. Dramatic hand painted polished fantasy strategy game sprite, readable at 77 pixels. Compact isolated silhouette, ground rubble confined to the original footprint, no rectangular base, no text, no UI frame, no people. NO smoke clouds, NO fire painted into the image because smoke/fire will be animated in engine. Soft daylight from upper left. Produce one transparent cutout icon centered with 6 percent transparent margin, no background.

### Prompt: undead

Use case: precise-object-edit. Edit target: supplied gothic undead castle sprite. Create its WAR-RUINED state, same camera, same footprint, transparent RGBA background. Preserve cold blue-black gothic stone, cyan window accents and iconic spires, but unmistakably devastated: central spire broken halfway, roof wings caved in, huge breached walls, black rubble piles and shattered cyan stained glass. Retain only 35 percent recognizable standing castle, majority collapsed. Polished hand painted fantasy strategy map sprite readable at 77 pixels. Ground rubble contained in footprint, isolated compact silhouette, no rectangular base, no text, no UI frame, no people. NO smoke clouds or flames painted into image because engine animates smoke. Same upper-left light. One transparent cutout icon centered with 6 percent transparent margin, no background.

## Проверка

`tests/test_city_war.py`: порог обеих сторон, реальный бой в изолированной БД,
смена владельца, повторное разрушение, отстройка, сохранение, повторная отрисовка,
затухание дыма, масштабирование и ограничение количества частиц.

`tests/render_city_war_preview.py` создаёт `assets/city-war-preview.png`
из настоящих игровых текстур и графических инструкций, не открывая сохранение игрока.
