/* Example (landscape 1920x1080, a person at a desk): a window top left, a monitor on the desk to the left, a ring light
   on a stand to the right, a bookshelf on the right wall, a pendant lamp, a plant at the desk's right end. */
Cartoon.room({
  width: 1920, height: 1080,
  head: [960, 380],
  spots: [[560, 130, 44], [1180, 110, 40], [1830, 760, 40], [90, 640, 42], [1320, 600, 36]],
  draw(K) {
    return K.wall()
      + K.window({ x: 60, y: 60, w: 330, h: 380, panes: 2, curtains: true })
      + K.shelf({ x: 1480, y: 110, w: 360, h: 520, rows: 3 })
      + K.lamp({ x: 1180, y: 250, h: 260, type: "pendant", shade: "c" })
      + K.ringlight({ x: 1340, y: 380, r: 115, stand: 420 })
      + K.table({ x: -20, y: 780, w: 1960, h: 320, top: 34 })
      + K.monitor({ x: 300, y: 470, w: 420, h: 250 })
      + K.mug({ x: 800, y: 780, s: 1.1 })
      + K.plant({ x: 1760, y: 782, h: 300 });
  },
});
