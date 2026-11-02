# Looks: 10 doodle styles, 10 type styles, and custom ones

The user picks one doodle style and one type style in "Pick your look" at the top of the storyboard, on their own
frame. Claude recommends one pair first (`recommended` in `cartoonify.json`) and draws the beats in it.

## Doodle styles (the room)

| Id | Name | Feel | Good when |
|---|---|---|---|
| D1 | Creator studio | peach wall in crayon; camera, play button, ON AIR doodles | creators, tutorials |
| D2 | Chalkboard | white chalk on a green board; bulbs, arrows, swirls | teaching, tips; light clothes |
| D3 | Notebook margin | lined paper, blue ballpoint; rocket, cube, hearts | school, study, playful |
| D4 | Neon signs | dark brick, the room traced in neon; hearts, bolts | night, music, gaming; light clothes |
| D5 | Cozy loft | cream wall, warm marker colours, string lights | the safe default: still reads as a real room |
| D6 | Night sky | midnight wall in crayon; planet, moon, rocket, stars | dreamy, space, bedtime |
| D7 | Greenhouse | cream wall framed by giant leaves; butterflies | wellness, food, calm |
| D8 | Retro 70s | rainbow arch behind the head, daisies, waves | loud and warm; one person centred |
| D9 | Pencil sketchbook | graphite on cream paper, doubled line, hatching | artsy, understated |
| D10 | Sticker bomb | yellow wall, every prop a die-cut sticker; WOW, flame, cursor | loud, social, youthful |

Dark clothes read best on light walls (D1, D3, D5, D7, D8, D9, D10); the dark styles (D2, D4, D6) suit light clothes.
The marker outline around the person takes each style's ink.

## Type styles (the keywords)

| Id | Name | Note |
|---|---|---|
| T1 | Condensed poster | Anton, navy and red; fits long words |
| T2 | Marker hand-lettering | Permanent Marker, black and red, scribbled underline; looks drawn by the same hand |
| T3 | Bubble 3D | Luckiest Guy, yellow and pink with a deep drop; reads on any wall |
| T4 | Comic burst | Bangers on a jagged yellow burst |
| T5 | Die-cut sticker | Titan One with a thick white border |
| T6 | Chalk | Cabin Sketch, white and yellow: for dark walls (D2, D4, D6) |
| T7 | Neon script | Yellowtail glowing pink and cyan, keeps the spoken case: for dark walls |
| T8 | Cut-out collage | ransom-note letters |
| T9 | 70s groovy | Shrikhand with stacked shadows (pairs with D8) |
| T10 | Label tape | typewriter letters on tape strips |

Light type (T6, T7) on a light wall does not read: say so if the user picks it, and offer T3 or T2.

## Custom looks

When the user describes their own look in the free field, write `P/custom-look.js`. It is loaded after the kit and
before `room.js`, so a custom style shows up in the picker next to the 10 (rerun `storyboard --bump`).

```js
// P/custom-look.js
const base = Cartoon.styleById("D5");
Cartoon.addStyle(Object.assign({}, base, {
  id: "C1", name: "Pastel loft", blurb: "Soft pastel wall and furniture, thick plum ink, hearts and sparkles.",
  ink: "#4A3B5C", w: 11,
  pal: Object.assign({}, base.pal, { wall: "#FDE2E4", wall2: "#FFF0F3", a: "#BDE0FE", a2: "#A2C8F0", b: "#FFC8DD", c: "#CDB4DB" }),
  deco: ["heart", "sparkle", "star4"], accent: ["#FFAFCC", "#A2D2FF", "#CDB4DB"], lights: false,
}));
Cartoon.addType({
  id: "U1", name: "Pastel bubble", font: "Luckiest Guy", cw: 0.6, blurb: "Bubble letters in pastel pink and blue.",
  line: (t, i, s) => `<div style="font:${s}px/1 'Luckiest Guy';color:${["#FFAFCC", "#A2D2FF"][i % 2]};-webkit-text-stroke:${Math.round(s / 19)}px #4A3B5C;paint-order:stroke fill;text-shadow:0 ${Math.round(s / 16)}px 0 #4A3B5C">${t.toUpperCase()}</div>`,
}));
```

Then `CF look P --doodle C1 --type U1`, `CF outline P` (before the build) and `CF storyboard P --bump --change "New custom look: Pastel loft"`.

What a style can set:
- `kind`: `marker`, `crayon` (grainy wall), `chalk` (grainy lines), `pen` (lined paper, white fills), `neon` (dark
  fills, glowing strokes per role: `neon: { a: "#hex", ... }`), `pencil` (doubled line, hatching), `sticker` (die-cut
  border on every prop and doodle).
- `ink`, `w` (line width at a 1080 short side), `pal` (one colour per role: wall, wall2, floor, a, a2, b, c, d, wood,
  glass, leaf, leaf2, light, metal, paper, dark, screen), `dark: true` for dark walls.
- Wall extras: `lights` (string of lights), `dots` (stars), `leaves` (giant leaves at the edges), `arch: [colours]`
  (an arch behind the head).
- `deco`: the doodles that pop into the free spots and beside the keywords, from: star4, star5, star5o, sparkle,
  heart, bolt, swirl, zigzag, wave, arrow, rays, bulb, rocket, cube, play, planet, moon, daisy, sun, leaf, butterfly,
  camera, onair, flame, wow, cursor. `accent`: their colours.

A custom type's `line(text, index, size)` returns the HTML of one line; `cw` is the average letter width as a share
of the size (used to fit the longest line). Use the bundled fonts: Anton, Permanent Marker, Luckiest Guy, Bangers,
Titan One, Cabin Sketch (700), Yellowtail, Abril Fatface, Rubik Mono One, Shrikhand, Special Elite.
