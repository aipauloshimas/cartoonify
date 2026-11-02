# Redrawing the room (`room.js`)

The set behind the person is their own room, redrawn. Claude writes it once per video in `P/room.js`, from the empty
room (`work/plate.png`) and its grid (`work/plate_grid.jpg`), with the prop library in `kit/cartoon.js`. The doodle
style picked on the storyboard decides the colours, the ink, the line and the wall; `room.js` only says **what is
where**. So the same `room.js` draws all 10 styles in the look picker.

## The file

```js
/* One line on the room: what is in it, where the light comes from. Coordinates are the video's own pixels. */
Cartoon.room({
  width: 1080, height: 1920,            // the video's size (cartoonify.json)
  head: [540, 900],                     // the centre of the head, most of the time (the Retro 70s arch sits behind it)
  spots: [[140, 200, 48], [950, 230, 52], [250, 1030, 40]],   // free wall where doodles pop in: [x, y, radius]
  // lights: false,                     // no string of lights across the top in the Cozy loft style
  draw(K) {
    return K.wall()
      + K.frame({ x: -20, y: 345, w: 200, h: 530, art: "abstract", role: "wood" })
      + K.plant({ x: 55, y: 1250, h: 440, big: true })
      + K.sofa({ x: -30, y: 1185, w: 1140, h: 780, seatY: 1520, cushions: 2 });
  },
});
```

`draw` returns one string; draw in painter's order: the wall first, then what hangs on it (frames, windows, doors,
shelves), then the furniture in front (the sofa or the desk last). The person is always in front of the whole set.

## How to read the room

1. Open `work/plate_grid.jpg`: the room with the person removed and a grid every 100 px (labels every 200 px) in the
   video's own pixels. Magenta = never seen (always behind the person): draw what is most likely there.
2. Look at `work/contact.jpg` too: the plate can smear things the person moves in front of.
3. List the 4 to 8 things that make the room recognisable: the big furniture, what is on the wall, the window or door,
   one or two signature objects (a plant, a lamp, a shelf of books, a ring light, a monitor). Skip small clutter.
4. Read each one's box (x, y, w, h) off the grid. Let shapes run off the frame where the real ones do (negative x, or
   past the width).
5. Pick roles by what a thing is, not by its real colour: the style paints them. Sofa or bed = `a` (its shade `a2`),
   cushions and pillows = `b`, accents = `c` / `d`, wood = `wood`, plants = `leaf` / `leaf2`, glass = `glass`, lamps
   and bulbs = `light`, screens = `screen`, metal = `metal`, paper and sheets = `paper`, dark things = `dark`.
   Use a literal `"#hex"` only when the real colour is the point (a red sofa that everyone knows); the colour styles
   keep it, the one-ink styles (Chalkboard, Notebook, Pencil) redraw it in their own ink.
6. `head` = the head's centre in most frames. `spots` = 4 to 8 free patches of wall, away from the person (the plate
   step prints where the person usually is) and not crowding the keywords; radius 35 to 55 at a 1080 short side.

Then `CF check-room P` and open `work/check/compare.jpg` (the real empty room | your drawing | your drawing over the
room). Fix what is off by more than a hand's width and run it again. Two or three passes are enough: it is a cartoon,
not a tracing.

## The kit (`K`)

All sizes are in the video's pixels. Line widths and small details scale with the video (`K.u` = short side / 1080).

| Call | Draws |
|---|---|
| `K.wall(role = "wall")` | the wall colour and the style's wall texture and extras (lights, leaves, stars, lined paper, bricks). Always first. |
| `K.floor({ y })` | a floor from `y` down |
| `K.wainscot({ y, role })` | a lower wall panel from `y` down |
| `K.sofa({ x, y, w, h, seatY, cushions = 2, cushion = "b", arms = true, role = "a", shade = "a2" })` | a sofa: back from `y`, seat from `seatY`, cushions leaning on the back |
| `K.bed({ x, y, w, h, role, sheet, pillow })` | a bed with two pillows |
| `K.chair({ x, y, w, h, role })` | an armless chair |
| `K.table({ x, y, w, h, role, top })` | a table or desk top with two legs |
| `K.cabinet({ x, y, w, h, doors, drawers, legs })` | a cabinet, dresser or sideboard |
| `K.shelf({ x, y, w, h, rows = 3, books = true })` | a bookshelf filled with books |
| `K.window({ x, y, w, h, arch, panes = 2, sun = true, curtains })` | a window with sky, sun and a cloud |
| `K.curtain({ x, y, w, h, role })` | one curtain |
| `K.door({ x, y, w, h })` | a panelled door |
| `K.frame({ x, y, w, h, art })` | a framed picture: `art` = `mountains`, `abstract`, `bolt`, `face`, `dark` |
| `K.poster({ x, y, w, h, text, tilt })` | a pinned poster, with a word on it if you like |
| `K.plant({ x, y, h, big, pot })` | a potted plant; `x, y` = the bottom centre of the pot |
| `K.lamp({ x, y, h, type, shade })` | `floor` / `desk` (x, y = the base) or `pendant` (x, y = the bottom of the shade, h = the cord) |
| `K.softbox({ x, y, w, h, stand })`, `K.ringlight({ x, y, r, stand })` | creator lights |
| `K.monitor({ x, y, w, h, stand })`, `K.tv({ x, y, w, h })` | a screen |
| `K.clock({ x, y, r })`, `K.mug({ x, y, s })`, `K.rug({ x, y, w, h })`, `K.box({ x, y, w, h, role })` | small things |
| `K.lights({ y, x0, x1, n, sag })` | a string of lights |

Anything else, draw with the primitives and wrap it in `K.prop("name", ...)` (the Sticker bomb style gives every prop
its die-cut border through it):

| Primitive | |
|---|---|
| `K.path(d, role, { w, fill, stroke })` | any SVG path, filled with the role's colour, outlined in the style's ink |
| `K.rect(x, y, w, h, role, { rx })`, `K.circle(x, y, r, role)`, `K.ellipse(x, y, rx, ry, role)` | shapes |
| `K.line(d, role = "ink", { w, dash })` | a stroke only |
| `K.text(x, y, text, size, role, { font })` | a word on the wall (a neon sign, a poster) |
| `K.hatch(x, y, w, h, gap)` | pencil shading in a box |

```js
// a guitar on a stand, drawn by hand
+ K.prop("guitar", K.path("M820 1100 q-60 0 -60 70 q0 60 50 80 q-40 40 -10 90 q40 50 100 0 q30 -50 -10 -90 q50 -20 50 -80 q0 -70 -60 -70 z", "wood")
    + K.line("M840 1110 L840 700", "ink", { w: 14 }) + K.circle(840, 1240, 22, "dark"))
```

## Examples

- `examples/sofa-living-room.js`: a person on a sofa, a framed print, a plant, a door (the test take).
- `examples/desk-studio.js`: a person at a desk, a shelf, a monitor, a ring light and a window.
