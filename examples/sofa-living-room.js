/* Example (vertical 1080x1920, a person on a sofa): a bright living room. White wall, a light linen sofa across the bottom with a beige cushion (left) and a striped
   one (right), an olive tree behind the left arm, a tall framed abstract print on the left wall, a dark wood door in
   a recess on the far right. Coordinates are the video's own pixels (1080x1920), read off work/plate_grid.jpg. */
Cartoon.room({
  width: 1080, height: 1920,
  head: [540, 900],
  // free wall, away from the person and the keywords' top band: the doodles pop in here
  spots: [[140, 200, 48], [950, 230, 52], [250, 1030, 40], [880, 1090, 42], [930, 700, 44], [320, 650, 38]],
  draw(K) {
    return K.wall()
      + K.line("M1000 -20 L1000 1210", "ink", { w: 6 })                       // the recess edge
      + K.door({ x: 1020, y: 570, w: 110, h: 660 })
      + K.frame({ x: -20, y: 345, w: 200, h: 530, art: "abstract", role: "wood" })
      + K.plant({ x: 55, y: 1250, h: 440, pot: "c", big: true })
      + K.sofa({ x: -30, y: 1185, w: 1140, h: 780, seatY: 1520, cushions: 2, cushion: "b" });
  },
});
