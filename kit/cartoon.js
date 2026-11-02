/* Cartoonify drawing kit. One file for the browser (storyboard stills, the look picker) and Node (the edit build).

   A ROOM is the person's real room, redrawn by Claude in rooms/<name>.js with the prop library below:
     Cartoon.room({ width: 1080, height: 1920, head: [540, 760], spots: [[x, y, r], ...], draw(K) { return K.wall() + K.sofa({...}) + ... } })
   A DOODLE STYLE (D1..D10) decides how that room is drawn: palette per role, ink, line width, line filter, wall
   texture and the signature doodles that pop into the free spots. A TYPE STYLE (T1..T10) draws the keywords.

     Cartoon.set(room, styleId)            -> <svg> of the whole set (wall, props, doodles), at the room's own size
     Cartoon.typeHTML(typeId, lines, size)  -> HTML block of the keyword lines
     Cartoon.glyph(styleId, i, x, y, r)     -> one doodle of the style (the pop-ins beside the keywords)

   Roles (fill colours a style maps): wall, floor, a (main furniture), a2 (its shade), b (second piece), c (accent),
   d (accent 2), wood, glass, leaf, leaf2, light, metal, paper, dark, screen. A literal "#hex" is kept as is, except in
   one-ink styles (chalk, pen, pencil), which redraw it with their own colours. */
(function (root) {
  "use strict";
  const N = (v) => +(+v).toFixed(1);

  /* ---------- doodle styles ---------- */
  const STYLES = [
    { id: "D1", name: "Creator studio", kind: "crayon", blurb: "Peach wall in crayon, a camera, a play button and an ON AIR sign in the free spots.",
      ink: "#2B2B5E", w: 9, pal: { wall: "#F7D3BD", wall2: "#FBE2D2", floor: "#E8B79C", a: "#4C7BD9", a2: "#3962B8", b: "#FFC93C", c: "#FF5A5A", d: "#9FD3FF", wood: "#C98A5A", glass: "#BFE3F7", leaf: "#3BA55C", leaf2: "#2A7D45", light: "#FFE07A", metal: "#9AA3B5", paper: "#FFF8F0", dark: "#3A3F7A", screen: "#3A3F7A" },
      deco: ["onair", "star4", "play", "sparkle", "camera", "heart"], accent: ["#FFC93C", "#FF5A5A", "#4C7BD9"] },
    { id: "D2", name: "Chalkboard", kind: "chalk", dark: true, blurb: "The room in white chalk on a green board, with light bulbs, arrows, stars and swirls.",
      ink: "#F4F1E8", w: 8, pal: { wall: "#2E4A3D", wall2: "#3D5E4E", floor: "#284035", a: "#3D5E4E", a2: "#34523F", b: "#46695A", c: "#4A6B5A", d: "#3F6151", wood: "#3B5A4B", glass: "#355546", leaf: "#3F6151", leaf2: "#36584A", light: "#5A7A63", metal: "#3B5A4B", paper: "#46695A", dark: "#263D33", screen: "#263D33" },
      chalkInk: { c: "#FFE46B", d: "#9BE0FF", leaf: "#A8E6A1", light: "#FFE46B", glass: "#9BE0FF" },
      deco: ["bulb", "arrow", "star5o", "swirl", "zigzag"], accent: ["#FFE46B", "#9BE0FF", "#FF9EBB"] },
    { id: "D3", name: "Notebook margin", kind: "pen", blurb: "Lined paper and blue ballpoint, like a page doodled in class: rocket, spiral, cube, hearts.",
      ink: "#2346B0", w: 6, pal: { wall: "#FCFBF4", floor: "#FCFBF4", a: "#FFFFFF", a2: "#F1F4FC", b: "#FFFFFF", c: "#FFFFFF", d: "#FFFFFF", wood: "#FFFFFF", glass: "#EEF3FF", leaf: "#FFFFFF", leaf2: "#FFFFFF", light: "#FFFFFF", metal: "#FFFFFF", paper: "#FFFFFF", dark: "#E3E9F8", screen: "#E3E9F8" },
      deco: ["rocket", "swirl", "cube", "heart", "star5o"], accent: ["#2346B0", "#E8442E"] },
    { id: "D4", name: "Neon signs", kind: "neon", dark: true, blurb: "Dark brick wall, the room traced in glowing neon, with hearts, bolts and sparkles.",
      ink: "#B57CFF", w: 7, pal: { wall: "#1A1230", floor: "#140E26", a: "#2A1F48", a2: "#22193B", b: "#2A1F48", c: "#2A1F48", d: "#2A1F48", wood: "#251A40", glass: "#1F1838", leaf: "#1F2A3A", leaf2: "#1F2A3A", light: "#2A2438", metal: "#251A40", paper: "#251A40", dark: "#140E26", screen: "#140E26" },
      neon: { a: "#B57CFF", a2: "#B57CFF", b: "#52E8FF", c: "#FF4FA3", d: "#FFE14F", wood: "#FF9F43", glass: "#52E8FF", leaf: "#7CFF8A", leaf2: "#7CFF8A", light: "#FFE14F", metal: "#52E8FF", paper: "#FF4FA3", dark: "#B57CFF", screen: "#52E8FF", floor: "#B57CFF" },
      deco: ["heart", "bolt", "play", "star4"], accent: ["#FF4FA3", "#52E8FF", "#FFE14F"] },
    { id: "D5", name: "Cozy loft", kind: "marker", blurb: "Cream wall, warm marker colours and string lights across the top. Still reads as a real room.",
      ink: "#2F2219", w: 8, pal: { wall: "#F2E3C4", wall2: "#F8ECD3", floor: "#D9B98C", a: "#C4553B", a2: "#A8432D", b: "#F2B731", c: "#E8442E", d: "#3D7DD8", wood: "#B9773F", glass: "#BFE3F7", leaf: "#3BA55C", leaf2: "#2A7D45", light: "#FFD23F", metal: "#8C8C99", paper: "#FFF6E6", dark: "#4A3426", screen: "#3B4A6B" },
      lights: true, deco: ["star4", "heart", "arrow", "rays", "star4"], accent: ["#FFD23F", "#E8442E", "#E06AA0"] },
    { id: "D6", name: "Night sky", kind: "crayon", dark: true, blurb: "Midnight wall in crayon: ringed planet, crescent moon, a little rocket and stars.",
      ink: "#0E1433", w: 8, pal: { wall: "#22306B", wall2: "#2E3F86", floor: "#1B2657", a: "#7B5CD6", a2: "#6347BB", b: "#FFD23F", c: "#FF8A5B", d: "#7FD3FF", wood: "#5B4A9E", glass: "#3B5BB0", leaf: "#3BA55C", leaf2: "#2A7D45", light: "#FFE98A", metal: "#8D9BD6", paper: "#E9E6FF", dark: "#141C45", screen: "#141C45" },
      dots: true, deco: ["planet", "moon", "rocket", "star5", "star5"], accent: ["#FFE98A", "#FF8A5B", "#7FD3FF"] },
    { id: "D7", name: "Greenhouse", kind: "marker", blurb: "Warm cream wall framed by giant leaves at the edges, with butterflies in the free spots.",
      ink: "#1F3A2A", w: 8, pal: { wall: "#FFF1D2", wall2: "#FFF7E4", floor: "#E9CFA0", a: "#E07A4F", a2: "#C7653C", b: "#FFE07A", c: "#3BA55C", d: "#FFB347", wood: "#B97A4A", glass: "#CDEBF5", leaf: "#3BA55C", leaf2: "#2E8B57", light: "#FFE07A", metal: "#9DB0A3", paper: "#FFFBF0", dark: "#2E4A3A", screen: "#2E4A3A" },
      leaves: true, deco: ["butterfly", "leaf", "butterfly", "sparkle"], accent: ["#3BA55C", "#FFB347", "#E07A4F"] },
    { id: "D8", name: "Retro 70s", kind: "marker", blurb: "A rainbow arch behind your head, daisies and wavy lines. Warm and loud.",
      ink: "#3B2416", w: 8, pal: { wall: "#F6E4C3", wall2: "#FBEFD9", floor: "#D9A066", a: "#B5562C", a2: "#984522", b: "#F7D774", c: "#E8572A", d: "#4FA3A5", wood: "#A8642E", glass: "#BFE3DA", leaf: "#6E9E3A", leaf2: "#55802B", light: "#F7D774", metal: "#B8A27E", paper: "#FFF6E6", dark: "#5A3420", screen: "#4FA3A5" },
      arch: ["#E8572A", "#F2A93B", "#F7D774", "#4FA3A5"], deco: ["daisy", "wave", "daisy", "sun"], accent: ["#E8572A", "#F2A93B", "#4FA3A5"] },
    { id: "D9", name: "Pencil sketchbook", kind: "pencil", blurb: "Cream paper, graphite only: the room sketched with a doubled line and hatching.",
      ink: "#4A4A4A", w: 5, pal: { wall: "#F3EEE2", floor: "#ECE5D5", a: "#EAE3D3", a2: "#E2DACA", b: "#F0EADC", c: "#E6DFCF", d: "#EDE7DA", wood: "#E4DCCB", glass: "#F7F4EC", leaf: "#E6E1D2", leaf2: "#DFD9C9", light: "#F7F4EC", metal: "#E4DED2", paper: "#F7F4EC", dark: "#D6CFBF", screen: "#D6CFBF" },
      deco: ["star5o", "swirl", "heart", "sparkle"], accent: ["#4A4A4A"] },
    { id: "D10", name: "Sticker bomb", kind: "sticker", blurb: "Yellow wall, every piece of the room a die-cut sticker, plus star, flame, WOW and cursor stickers.",
      ink: "#1D1D1F", w: 6, pal: { wall: "#FFD84D", floor: "#F2C12E", a: "#5B6CFF", a2: "#4655E0", b: "#FF8FC2", c: "#FF5A5A", d: "#3DD6A3", wood: "#FF9F43", glass: "#9AD0FF", leaf: "#3BA55C", leaf2: "#2A7D45", light: "#FFFFFF", metal: "#B6BCD0", paper: "#FFFFFF", dark: "#2B2E4A", screen: "#2B2E4A" },
      deco: ["star5", "flame", "wow", "cursor", "heart", "play"], accent: ["#FF5A5A", "#5B6CFF", "#FF4FA3"] },
  ];

  /* ---------- the kit (K) handed to a room's draw(K) ---------- */
  function kit(room, st) {
    const W = room.width, H = room.height, u = Math.min(W, H) / 1080;
    const mono = st.kind === "chalk" || st.kind === "pen" || st.kind === "pencil";
    const col = (r) => {
      if (r === "none") return "none";
      if (typeof r === "string" && r[0] === "#") return mono ? st.pal.a : r;
      return st.pal[r] || st.pal.a;
    };
    const strokeFor = (r) => (st.neon && st.neon[r]) || (st.chalkInk && st.chalkInk[r]) || (r && r[0] === "#" && st.neon ? st.neon.a : st.ink);
    const sw = (k = 1) => N(st.w * u * k);
    const attrs = (fill, stroke, w, extra = "") => `fill="${fill}" stroke="${stroke}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" ${extra}`;
    const K = { W, H, u, st, col, ink: st.ink, sw };
    // primitives: role decides fill, the style decides the ink
    K.path = (d, role = "a", o = {}) => {
      const fill = o.fill || (role === "none" ? "none" : col(role));
      const stroke = o.stroke || strokeFor(role);
      const op = st.kind === "neon" && fill !== "none" ? ' fill-opacity=".85"' : (st.kind === "chalk" && fill !== "none" ? ' fill-opacity=".9"' : "");
      let s = `<path d="${d}" ${attrs(fill, stroke, o.w != null ? N(o.w * u) : sw(), op)}/>`;
      if (st.kind === "pencil" && !o.single) s += `<path d="${d}" fill="none" stroke="${st.ink}" stroke-width="${sw(0.5)}" stroke-linecap="round" opacity=".55" transform="translate(${N(4 * u)} ${N(3 * u)})"/>`;
      return s;
    };
    K.line = (d, role = "ink", o = {}) => `<path d="${d}" ${attrs("none", role === "ink" ? st.ink : strokeFor(role) === st.ink && st.kind !== "neon" && !mono ? col(role) : strokeFor(role), o.w != null ? N(o.w * u) : sw(0.7), o.dash ? `stroke-dasharray="${o.dash}"` : "")}/>`;
    K.rect = (x, y, w, h, role = "a", o = {}) => K.path(roundRect(x, y, w, h, o.rx || 0), role, o);
    K.circle = (x, y, r, role = "a", o = {}) => K.path(`M${N(x - r)} ${N(y)} a${N(r)} ${N(r)} 0 1 0 ${N(2 * r)} 0 a${N(r)} ${N(r)} 0 1 0 ${N(-2 * r)} 0Z`, role, o);
    K.ellipse = (x, y, rx, ry, role = "a", o = {}) => K.path(`M${N(x - rx)} ${N(y)} a${N(rx)} ${N(ry)} 0 1 0 ${N(2 * rx)} 0 a${N(rx)} ${N(ry)} 0 1 0 ${N(-2 * rx)} 0Z`, role, o);
    K.text = (x, y, s, size, role = "c", o = {}) => `<text x="${N(x)}" y="${N(y)}" font-family="${o.font || "Permanent Marker"}" font-size="${N(size * u)}" text-anchor="middle" fill="${st.kind === "neon" ? strokeFor(role) : (mono ? st.ink : col(role))}">${s}</text>`;
    // a prop is one piece of furniture: the sticker style gives each its white die-cut border
    K.prop = (name, inner) => {
      if (st.kind === "sticker") {
        const white = inner.replace(/fill="(?!none)[^"]*"/g, 'fill="#fff"').replace(/stroke="[^"]*"/g, 'stroke="#fff"').replace(/stroke-width="[^"]*"/g, `stroke-width="${N(26 * u)}"`);
        inner = `<g filter="url(#cf-s)">${white}${inner}</g>`;
      }
      return `<g class="cf-prop" data-prop="${name}">${inner}</g>`;
    };
    K.hatch = (x, y, w, h, gap = 22) => {   // pencil-style shading inside a box
      let d = ""; for (let i = -h; i < w; i += gap * u) d += `M${N(x + Math.max(0, i))} ${N(y + h - Math.max(0, -i))} L${N(x + Math.min(w, i + h))} ${N(y + h - Math.min(h, i + h))} `;
      return `<path d="${d}" fill="none" stroke="${st.ink}" stroke-width="${N(2 * u)}" opacity=".35"/>`;
    };

    // ---------- props: boxes are in the room's own pixels (the video frame) ----------
    K.wall = (role = "wall") => wallLayer(K, role);
    K.floor = ({ y, role = "floor", line = true } = {}) => K.prop("floor", K.path(`M-40 ${y} L${W + 40} ${y} L${W + 40} ${H + 40} L-40 ${H + 40} Z`, role, { w: line ? st.w : 0 }) + (st.kind === "pencil" ? K.hatch(0, y, W, H - y, 30) : ""));
    K.wainscot = ({ y, role = "a2" }) => K.prop("wainscot", K.path(`M-40 ${y} L${W + 40} ${y} L${W + 40} ${H + 40} L-40 ${H + 40} Z`, role) + K.line(`M-40 ${N(y + 30 * u)} L${W + 40} ${N(y + 30 * u)}`));
    K.sofa = ({ x, y, w, h, role = "a", shade = "a2", cushions = 2, cushion = "b", arms = true, seatY }) => {
      const sy = seatY != null ? seatY : y + h * 0.42, ar = arms ? Math.min(w * 0.09, 120 * u) : 0, r = 50 * u;
      let s = K.path(`M${x} ${N(y + r)} Q${x} ${y} ${N(x + r)} ${y} L${N(x + w - r)} ${y} Q${x + w} ${y} ${x + w} ${N(y + r)} L${x + w} ${N(sy + 40 * u)} L${x} ${N(sy + 40 * u)} Z`, role);
      s += K.path(`M${x} ${N(sy)} L${x + w} ${N(sy)} L${x + w} ${y + h} L${x} ${y + h} Z`, shade);
      if (arms) s += K.path(roundRect(x - ar * 0.4, sy - 60 * u, ar, y + h - sy + 60 * u, 40 * u), role) + K.path(roundRect(x + w - ar * 0.6, sy - 60 * u, ar, y + h - sy + 60 * u, 40 * u), role);
      s += K.line(`M${N(x + ar)} ${N(sy + (y + h - sy) * 0.45)} L${N(x + w - ar)} ${N(sy + (y + h - sy) * 0.45)}`, "ink", { w: 5, dash: `${N(4 * u)} ${N(26 * u)}` });
      for (let i = 0; i < cushions; i++) {
        // cushions lean on the back and sit on the seat: their bottom rests just below the seat line
        const cw = Math.min(w * 0.26, 300 * u), cx = i % 2 === 0 ? x + ar + w * 0.03 + Math.floor(i / 2) * cw * 1.05 : x + w - ar - w * 0.03 - cw - Math.floor(i / 2) * cw * 1.05, cy = sy + 30 * u - cw * 0.9;
        s += K.path(`M${N(cx)} ${N(cy + 30 * u)} Q${N(cx - 6 * u)} ${N(cy)} ${N(cx + 40 * u)} ${N(cy - 4 * u)} L${N(cx + cw - 30 * u)} ${N(cy + 8 * u)} Q${N(cx + cw + 4 * u)} ${N(cy + 14 * u)} ${N(cx + cw)} ${N(cy + 50 * u)} L${N(cx + cw - 12 * u)} ${N(cy + cw * 0.85)} Q${N(cx + cw - 20 * u)} ${N(cy + cw * 0.95)} ${N(cx + cw - 56 * u)} ${N(cy + cw * 0.92)} L${N(cx + 30 * u)} ${N(cy + cw * 0.86)} Q${N(cx - 4 * u)} ${N(cy + cw * 0.8)} ${N(cx)} ${N(cy + cw * 0.6)} Z`, cushion);
      }
      return K.prop("sofa", s);
    };
    K.shelf = ({ x, y, w, h, rows = 3, role = "wood", books = true, items = [] }) => {
      let s = K.rect(x, y, w, h, role, { rx: 6 * u }), rh = h / rows;
      const bc = ["c", "b", "d", "leaf", "a", "light"];
      for (let r = 0; r < rows; r++) {
        const by = y + (r + 1) * rh;
        if (r < rows - 1) s += K.line(`M${x} ${N(by)} L${x + w} ${N(by)}`, "ink", { w: st.w });
        if (!books) continue;
        let bx = x + 12 * u, i = r * 2;
        while (bx < x + w - 40 * u && (r + i) % 7 !== 6) {
          const bw = (24 + ((i * 13) % 22)) * u, bh = rh * (0.62 + ((i * 7) % 4) * 0.07);
          if (bx + bw > x + w - 10 * u) break;
          s += K.rect(bx, by - bh - 4 * u, bw, bh, bc[i % bc.length], { w: 5, rx: 3 * u });
          bx += bw + 5 * u; i++;
        }
      }
      items.forEach((it) => { s += it; });
      return K.prop("shelf", s);
    };
    K.cabinet = ({ x, y, w, h, role = "wood", doors = 2, drawers = 0, legs = 0 }) => {
      let s = K.rect(x, y, w, h, role, { rx: 6 * u });
      const dh = drawers ? h * 0.22 : 0;
      for (let i = 0; i < drawers; i++) s += K.rect(x + 12 * u + i * (w - 24 * u) / drawers, y + 12 * u, (w - 24 * u) / drawers - 10 * u, dh - 18 * u, role, { w: 5, rx: 4 * u }) + K.circle(x + 12 * u + (i + 0.5) * (w - 24 * u) / drawers - 5 * u, y + dh / 2, 6 * u, "metal", { w: 3 });
      for (let i = 0; i < doors; i++) { const dx = x + 12 * u + i * (w - 24 * u) / doors; s += K.rect(dx, y + dh + 12 * u, (w - 24 * u) / doors - 10 * u, h - dh - 24 * u, role, { w: 5, rx: 4 * u }) + K.circle(dx + (i % 2 ? 22 * u : (w - 24 * u) / doors - 32 * u), y + dh + (h - dh) / 2, 7 * u, "metal", { w: 3 }); }
      for (let i = 0; i < legs; i++) s += K.line(`M${N(x + 20 * u + i * (w - 40 * u) / Math.max(1, legs - 1))} ${y + h} l0 ${N(40 * u)}`, "ink", { w: st.w });
      return K.prop("cabinet", s);
    };
    K.table = ({ x, y, w, h, role = "wood", top = 26 }) => K.prop("table", K.rect(x, y, w, top * u, role, { rx: 6 * u }) + K.path(`M${N(x + 30 * u)} ${N(y + top * u)} L${N(x + 40 * u)} ${y + h} M${N(x + w - 30 * u)} ${N(y + top * u)} L${N(x + w - 40 * u)} ${y + h}`, "none"));
    K.chair = ({ x, y, w, h, role = "a" }) => K.prop("chair", K.rect(x + w * 0.1, y, w * 0.8, h * 0.55, role, { rx: 30 * u }) + K.rect(x, y + h * 0.5, w, h * 0.16, role, { rx: 16 * u }) + K.path(`M${N(x + w * 0.2)} ${N(y + h * 0.66)} L${N(x + w * 0.15)} ${y + h} M${N(x + w * 0.8)} ${N(y + h * 0.66)} L${N(x + w * 0.85)} ${y + h}`, "none"));
    K.bed = ({ x, y, w, h, role = "a", sheet = "paper", pillow = "b" }) => K.prop("bed", K.rect(x, y, w, h * 0.35, "wood", { rx: 20 * u }) + K.rect(x, y + h * 0.3, w, h * 0.7, sheet, { rx: 24 * u }) + K.rect(x + w * 0.06, y + h * 0.12, w * 0.36, h * 0.28, pillow, { rx: 30 * u }) + K.rect(x + w * 0.58, y + h * 0.12, w * 0.36, h * 0.28, pillow, { rx: 30 * u }) + K.rect(x, y + h * 0.55, w, h * 0.45, role, { rx: 18 * u }));
    K.window = ({ x, y, w, h, arch = false, panes = 2, sun = true, curtains = false, frame = "c" }) => {
      let s = arch ? K.path(`M${x} ${y + h} L${x} ${N(y + w / 2)} A${N(w / 2)} ${N(w / 2)} 0 0 1 ${x + w} ${N(y + w / 2)} L${x + w} ${y + h} Z`, "glass") : K.rect(x, y, w, h, "glass", { rx: 8 * u });
      if (sun) s += K.circle(x + w * 0.7, y + h * 0.25, Math.min(w, h) * 0.12, "light");
      s += K.path(`M${N(x + w * 0.12)} ${N(y + h * 0.62)} q${N(w * .05)} ${N(-h * .1)} ${N(w * .18)} ${N(-h * .07)} q${N(w * .08)} ${N(-h * .09)} ${N(w * .2)} ${N(-h * .03)} q${N(w * .12)} 0 ${N(w * .12)} ${N(h * .08)} q${N(w * .06)} ${N(h * .06)} ${N(-w * .04)} ${N(h * .1)} l${N(-w * .4)} 0 q${N(-w * .1)} ${N(-h * .03)} ${N(-w * .06)} ${N(-h * .08)}z`, "paper", { w: st.w * 0.7 });
      for (let i = 1; i < panes; i++) s += K.line(`M${N(x + (w * i) / panes)} ${N(y + (arch ? 0 : 4 * u))} L${N(x + (w * i) / panes)} ${y + h}`, frame, { w: st.w * 1.3 });
      s += K.line(`M${x} ${N(y + h * 0.55)} L${x + w} ${N(y + h * 0.55)}`, frame, { w: st.w * 1.3 });
      s += K.rect(x - 16 * u, y + h - 6 * u, w + 32 * u, 26 * u, frame, { rx: 8 * u });
      if (curtains) s += K.curtain({ x: x - w * 0.18, y: y - 30 * u, w: w * 0.3, h: h + 60 * u }) + K.curtain({ x: x + w * 0.88, y: y - 30 * u, w: w * 0.3, h: h + 60 * u });
      return K.prop("window", s);
    };
    K.curtain = ({ x, y, w, h, role = "c" }) => K.prop("curtain", K.path(`M${x} ${y} L${x + w} ${y} Q${N(x + w * 0.6)} ${N(y + h * 0.5)} ${N(x + w * 0.85)} ${y + h} L${N(x + w * 0.1)} ${y + h} Q${N(x + w * 0.35)} ${N(y + h * 0.5)} ${x} ${y} Z`, role) + K.line(`M${N(x + w * 0.35)} ${N(y + 20 * u)} Q${N(x + w * 0.45)} ${N(y + h * 0.5)} ${N(x + w * 0.35)} ${N(y + h - 20 * u)}`, "ink", { w: 4 }));
    K.door = ({ x, y, w, h, role = "wood" }) => K.prop("door", K.rect(x, y, w, h, role, { rx: 6 * u }) + K.rect(x + w * 0.14, y + h * 0.08, w * 0.72, h * 0.36, role, { w: 5, rx: 6 * u }) + K.rect(x + w * 0.14, y + h * 0.52, w * 0.72, h * 0.4, role, { w: 5, rx: 6 * u }) + K.circle(x + w * 0.84, y + h * 0.5, 12 * u, "metal", { w: 4 }));
    K.frame = ({ x, y, w, h, art = "mountains", role = "c" }) => {
      let s = K.rect(x - 14 * u, y - 14 * u, w + 28 * u, h + 28 * u, role, { rx: 4 * u }) + K.rect(x, y, w, h, art === "dark" ? "dark" : "glass");
      if (art === "mountains") s += K.path(`M${N(x + 8 * u)} ${N(y + h - 6 * u)} L${N(x + w * 0.32)} ${N(y + h * 0.35)} L${N(x + w * 0.55)} ${N(y + h * 0.7)} L${N(x + w * 0.72)} ${N(y + h * 0.45)} L${N(x + w - 8 * u)} ${N(y + h - 6 * u)} Z`, "leaf", { w: st.w * 0.7 }) + K.circle(x + w * 0.8, y + h * 0.25, Math.min(w, h) * 0.1, "light", { w: st.w * 0.5 });
      else if (art === "bolt" || art === "dark") s += K.path(`M${N(x + w * .56)} ${N(y + h * .12)} L${N(x + w * .3)} ${N(y + h * .55)} L${N(x + w * .5)} ${N(y + h * .55)} L${N(x + w * .38)} ${N(y + h * .88)} L${N(x + w * .72)} ${N(y + h * .4)} L${N(x + w * .52)} ${N(y + h * .4)} Z`, "light", { w: st.w * .5 });
      else if (art === "abstract") s += K.circle(x + w * 0.35, y + h * 0.4, Math.min(w, h) * 0.22, "b", { w: st.w * 0.6 }) + K.rect(x + w * 0.45, y + h * 0.45, w * 0.4, h * 0.4, "d", { w: st.w * 0.6 });
      else if (art === "face") s += K.circle(x + w / 2, y + h * 0.45, Math.min(w, h) * 0.28, "b", { w: st.w * .6 }) + K.line(`M${N(x + w * .4)} ${N(y + h * .52)} q${N(w * .1)} ${N(h * .08)} ${N(w * .2)} 0`, "ink", { w: 5 });
      return K.prop("frame", s);
    };
    K.poster = ({ x, y, w, h, text = "", role = "paper", tilt = -3 }) => K.prop("poster", `<g transform="rotate(${tilt} ${N(x + w / 2)} ${N(y + h / 2)})">${K.rect(x, y, w, h, role, { rx: 4 * u })}${text ? K.text(x + w / 2, y + h * 0.58, text, Math.min(w / (0.62 * text.length), h * 0.5) / u, "c") : ""}${K.circle(x + w / 2, y + 12 * u, 8 * u, "c", { w: 3 })}</g>`);
    K.plant = ({ x, y, h = 300, pot = "c", big = false }) => {   // x, y = the pot's bottom centre
      const p = h * 0.3, s = h / 300;
      let leaves = K.path(`M${x} ${N(y - p)} q${N(-10 * s)} ${N(-150 * s)} ${N(-80 * s)} ${N(-230 * s)} q${N(100 * s)} ${N(40 * s)} ${N(95 * s)} ${N(210 * s)}`, "leaf")
        + K.path(`M${N(x + 10 * s)} ${N(y - p)} q${N(20 * s)} ${N(-190 * s)} ${N(110 * s)} ${N(-250 * s)} q${N(-40 * s)} ${N(120 * s)} ${N(-85 * s)} ${N(250 * s)}`, "leaf2")
        + K.path(`M${N(x - 5 * s)} ${N(y - p)} q${N(-60 * s)} ${N(-80 * s)} ${N(-140 * s)} ${N(-90 * s)} q${N(70 * s)} ${N(60 * s)} ${N(115 * s)} ${N(100 * s)}`, "leaf2");
      if (big) leaves += K.path(`M${N(x + 8 * s)} ${N(y - p)} q${N(50 * s)} ${N(-70 * s)} ${N(125 * s)} ${N(-70 * s)} q${N(-50 * s)} ${N(50 * s)} ${N(-105 * s)} ${N(85 * s)}`, "leaf");
      return K.prop("plant", leaves + K.path(`M${N(x - 65 * s)} ${N(y - p)} L${N(x + 65 * s)} ${N(y - p)} L${N(x + 50 * s)} ${y} L${N(x - 50 * s)} ${y} Z`, pot) + K.line(`M${N(x - 60 * s)} ${N(y - p + 30 * s)} L${N(x + 60 * s)} ${N(y - p + 30 * s)}`, "ink", { w: 5 }));
    };
    K.lamp = ({ x, y, h = 300, type = "floor", shade = "c" }) => {   // floor/desk: x,y = base centre; pendant: x,y = shade bottom centre, h = cord
      if (type === "pendant") return K.prop("lamp", K.line(`M${x} ${N(y - h)} L${x} ${N(y - 70 * u)}`, "ink", { w: st.w * 0.8 }) + K.path(`M${N(x - 60 * u)} ${y} Q${N(x - 60 * u)} ${N(y - 70 * u)} ${x} ${N(y - 70 * u)} Q${N(x + 60 * u)} ${N(y - 70 * u)} ${N(x + 60 * u)} ${y} Z`, shade) + K.circle(x, y + 10 * u, 18 * u, "light"));
      const sh = Math.min(140 * u, h * 0.35);
      return K.prop("lamp", K.line(`M${x} ${y} L${x} ${N(y - h + sh)}`, "ink", { w: st.w })
        + K.path(`M${N(x - sh * 0.45)} ${N(y - h)} L${N(x + sh * 0.45)} ${N(y - h)} L${N(x + sh * 0.7)} ${N(y - h + sh)} L${N(x - sh * 0.7)} ${N(y - h + sh)} Z`, shade)
        + K.ellipse(x, y, sh * 0.5, 14 * u, "dark", { w: st.w * 0.7 }));
    };
    K.softbox = ({ x, y, w, h, stand = 0 }) => K.prop("softbox", K.rect(x, y, w, h, "dark", { rx: 10 * u }) + K.rect(x + 16 * u, y + 16 * u, w - 32 * u, h - 32 * u, "paper", { rx: 6 * u }) + (stand ? K.path(`M${N(x + w / 2)} ${y + h} L${N(x + w / 2)} ${N(y + h + stand)} M${N(x + w / 2)} ${N(y + h + stand * 0.8)} l${N(-w * 0.3)} ${N(stand * 0.2)} M${N(x + w / 2)} ${N(y + h + stand * 0.8)} l${N(w * 0.3)} ${N(stand * 0.2)}`, "none") : ""));
    K.ringlight = ({ x, y, r = 110, stand = 0 }) => K.prop("ringlight", K.circle(x, y, r, "none", { w: st.w * 4, stroke: col("light") }) + K.circle(x, y, r * 1.16, "none") + K.circle(x, y, r * 0.84, "none") + (stand ? K.path(`M${x} ${N(y + r * 1.16)} L${x} ${N(y + stand)} M${x} ${N(y + stand * 0.85)} l${N(-r * 0.6)} ${N(stand * 0.15)} M${x} ${N(y + stand * 0.85)} l${N(r * 0.6)} ${N(stand * 0.15)}`, "none") : ""));
    K.monitor = ({ x, y, w, h, role = "dark", screen = "screen", stand = true }) => K.prop("monitor", K.rect(x, y, w, h, role, { rx: 12 * u }) + K.rect(x + 14 * u, y + 14 * u, w - 28 * u, h - 28 * u, screen, { rx: 6 * u, w: 4 }) + K.line(`M${N(x + w * .15)} ${N(y + h * .3)} l${N(w * .4)} 0 M${N(x + w * .15)} ${N(y + h * .45)} l${N(w * .55)} 0 M${N(x + w * .15)} ${N(y + h * .6)} l${N(w * .3)} 0`, "light", { w: 6 }) + (stand ? K.path(`M${N(x + w / 2 - 20 * u)} ${y + h} L${N(x + w / 2 - 30 * u)} ${N(y + h + 60 * u)} L${N(x + w / 2 + 30 * u)} ${N(y + h + 60 * u)} L${N(x + w / 2 + 20 * u)} ${y + h} Z`, role) : ""));
    K.tv = (o) => K.monitor(Object.assign({ stand: false }, o));
    K.clock = ({ x, y, r = 60 }) => K.prop("clock", K.circle(x, y, r, "paper") + K.line(`M${x} ${y} l0 ${N(-r * 0.6)} M${x} ${y} l${N(r * 0.45)} ${N(r * 0.2)}`, "ink", { w: 6 }) + K.circle(x, y, 5 * u, "dark", { w: 2 }));
    K.mug = ({ x, y, s = 1, role = "c" }) => K.prop("mug", K.rect(x - 30 * u * s, y - 70 * u * s, 60 * u * s, 70 * u * s, role, { rx: 8 * u }) + K.path(`M${N(x + 30 * u * s)} ${N(y - 55 * u * s)} q${N(28 * u * s)} 0 ${N(28 * u * s)} ${N(20 * u * s)} q0 ${N(20 * u * s)} ${N(-28 * u * s)} ${N(20 * u * s)}`, "none"));
    K.rug = ({ x, y, w, h, role = "d" }) => K.prop("rug", K.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, role) + K.ellipse(x + w / 2, y + h / 2, w * 0.36, h * 0.3, "none", { w: 5 }));
    K.lights = ({ y = 70, x0 = 0, x1 = W, n = 9, sag = 30 } = {}) => {   // a string of lights along the top
      let d = `M${x0} ${y}`, bulbs = "";
      const cs = ["light", "c", "d"];
      for (let i = 0; i < n; i++) { const bx = x0 + (i + 0.5) * (x1 - x0) / n, by = y + sag * u * (0.6 + 0.4 * Math.sin(i * 1.1)); d += ` L${N(bx)} ${N(by)}`; bulbs += K.circle(bx, by + 18 * u, 13 * u, cs[i % 3], { w: 4 }); }
      return K.prop("lights", K.line(d + ` L${x1} ${y}`, "ink", { w: 5 }) + bulbs);
    };
    K.box = ({ x, y, w, h, role = "b", rx = 8 }) => K.prop("box", K.rect(x, y, w, h, role, { rx: rx * u }));
    return K;
  }

  function roundRect(x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    if (!r) return `M${N(x)} ${N(y)} L${N(x + w)} ${N(y)} L${N(x + w)} ${N(y + h)} L${N(x)} ${N(y + h)} Z`;
    return `M${N(x + r)} ${N(y)} L${N(x + w - r)} ${N(y)} Q${N(x + w)} ${N(y)} ${N(x + w)} ${N(y + r)} L${N(x + w)} ${N(y + h - r)} Q${N(x + w)} ${N(y + h)} ${N(x + w - r)} ${N(y + h)} L${N(x + r)} ${N(y + h)} Q${N(x)} ${N(y + h)} ${N(x)} ${N(y + h - r)} L${N(x)} ${N(y + r)} Q${N(x)} ${N(y)} ${N(x + r)} ${N(y)} Z`;
  }

  /* the wall: colour, texture and the style's room-wide extras (lights, leaves, arch, stars) */
  function wallLayer(K, role) {
    const { W, H, u, st } = K, p = st.pal;
    let s = `<rect x="-40" y="-40" width="${W + 80}" height="${H + 80}" fill="${p[role] || p.wall}"/>`;
    if (p.wall2) s += `<rect x="-40" y="-40" width="${W + 80}" height="${H + 80}" fill="${p.wall2}" opacity=".55" filter="url(#cf-g)"/>`;
    if (st.kind === "pen") { let l = ""; for (let y = 80 * u; y < H; y += 64 * u) l += `M0 ${N(y)} L${W} ${N(y)} `; s += `<path d="${l}" stroke="#A9C4F0" stroke-width="${N(3 * u)}"/><path d="M${N(110 * u)} 0 L${N(110 * u)} ${H}" stroke="#F09A9A" stroke-width="${N(4 * u)}"/>`; }
    if (st.kind === "neon") { let b = ""; for (let y = 40 * u, r = 0; y < H; y += 70 * u, r++) for (let x = (r % 2) * -70 * u; x < W; x += 140 * u) b += `<rect x="${N(x)}" y="${N(y)}" width="${N(136 * u)}" height="${N(66 * u)}" fill="none" stroke="#2C1F45" stroke-width="${N(3 * u)}"/>`; s += b; }
    if (st.dots) { const pts = [[.08, .06], [.28, .03], [.65, .05], [.89, .11], [.06, .29], [.94, .31], [.39, .56], [.59, .57], [.18, .4], [.8, .45]]; pts.forEach(([a, b]) => { s += `<circle cx="${N(a * W)}" cy="${N(b * H)}" r="${N(5 * u)}" fill="#FFF6C8"/>`; }); }
    return `<g id="cf-wall-base">${s}</g>`;
  }
  function wallExtras(room, K) {
    const { W, H, u, st } = K;
    let s = "";
    if (st.arch && room.head) {   // a rainbow arch behind the head
      const [hx, hy] = room.head;
      st.arch.forEach((c, i) => { const r = (520 - i * 75) * u; s += `<path d="M${N(hx - r)} ${N(hy + 380 * u)} A${N(r)} ${N(r)} 0 0 1 ${N(hx + r)} ${N(hy + 380 * u)} Z" fill="${c}" stroke="${st.ink}" stroke-width="${N(7 * u)}"/>`; });
    }
    if (st.leaves) {
      const leaf = (x, y, s_, r, c) => `<g transform="translate(${N(x)} ${N(y)}) rotate(${r}) scale(${N(s_ * u)})"><path d="M0 0 C-120 -60 -140 -260 0 -340 C140 -260 120 -60 0 0Z" fill="${c}" stroke="${st.ink}" stroke-width="${N(st.w / s_)}" stroke-linejoin="round"/><path d="M0 0 L0 -320 M0 -80 L-70 -140 M0 -150 L-80 -220 M0 -80 L70 -140 M0 -150 L80 -220" fill="none" stroke="${st.ink}" stroke-width="${N(5 / s_)}" stroke-linecap="round"/></g>`;
      s += leaf(0, H * 0.42, 1.1, 55, "#2E8B57") + leaf(-20, H * 0.62, 1.25, 30, "#3BA55C") + leaf(W, H * 0.42, 1.1, -55, "#3BA55C") + leaf(W + 20, H * 0.62, 1.25, -30, "#2E8B57") + leaf(W * 0.12, -10, 0.9, 160, "#3BA55C") + leaf(W * 0.88, -10, 0.9, -160, "#2E8B57");
    }
    if (st.lights && room.lights !== false) s += K.lights({ y: 60 * u, x0: 0, x1: W, n: Math.max(5, Math.round(W / (120 * u))) });
    return s;
  }

  /* ---------- doodle glyphs (x, y = centre, r = radius) ---------- */
  function glyphSVG(st, name, x, y, r, i, u) {
    const ink = st.ink, w = N(Math.max(4, st.w * 0.75) * u), acc = st.accent[i % st.accent.length];
    const neon = st.kind === "neon", mono = st.kind === "pen" || st.kind === "pencil";
    const F = (c) => (neon || mono ? "none" : c), S = (c) => (neon ? c : (st.kind === "chalk" ? (c === "none" ? ink : c) : ink));
    const P = (d, f, s) => `<path d="${d}" fill="${f}" stroke="${s}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
    const n = (v) => N(v);
    const star = (pts, inner) => { let d = ""; for (let k = 0; k < pts * 2; k++) { const a = -Math.PI / 2 + k * Math.PI / pts, rr = k % 2 ? r * inner : r; d += (k ? "L" : "M") + n(x + rr * Math.cos(a)) + " " + n(y + rr * Math.sin(a)); } return d + "Z"; };
    const G = {
      star4: () => P(`M${x} ${n(y - r)} Q${n(x + r * .15)} ${n(y - r * .15)} ${n(x + r)} ${y} Q${n(x + r * .15)} ${n(y + r * .15)} ${x} ${n(y + r)} Q${n(x - r * .15)} ${n(y + r * .15)} ${n(x - r)} ${y} Q${n(x - r * .15)} ${n(y - r * .15)} ${x} ${n(y - r)}Z`, F(acc), S(acc)),
      star5: () => P(star(5, .45), F(acc), S(acc)),
      star5o: () => P(star(5, .45), "none", S(acc)),
      sparkle: () => P(`M${x} ${n(y - r)} L${x} ${n(y + r)} M${n(x - r)} ${y} L${n(x + r)} ${y} M${n(x - r * .6)} ${n(y - r * .6)} L${n(x + r * .6)} ${n(y + r * .6)} M${n(x + r * .6)} ${n(y - r * .6)} L${n(x - r * .6)} ${n(y + r * .6)}`, "none", neon || st.kind === "chalk" ? acc : acc),
      heart: () => P(`M${x} ${n(y + r * .9)} C${n(x - r * 1.4)} ${y} ${n(x - r * .9)} ${n(y - r)} ${x} ${n(y - r * .35)} C${n(x + r * .9)} ${n(y - r)} ${n(x + r * 1.4)} ${y} ${x} ${n(y + r * .9)}Z`, F(acc), S(acc)),
      bolt: () => P(`M${n(x + r * .2)} ${n(y - r)} L${n(x - r * .5)} ${n(y + r * .1)} L${x} ${n(y + r * .1)} L${n(x - r * .25)} ${n(y + r)} L${n(x + r * .55)} ${n(y - r * .15)} L${n(x + r * .05)} ${n(y - r * .15)} Z`, F(acc), S(acc)),
      swirl: () => P(`M${x} ${y} q${n(r * .3)} ${n(-r * .4)} ${n(r * .6)} 0 q${n(r * .2)} ${n(r * .5)} ${n(-r * .4)} ${n(r * .6)} q${n(-r * .8)} 0 ${n(-r * .7)} ${n(-r * .8)} q${n(r * .2)} ${n(-r * .9)} ${n(r * 1.2)} ${n(-r * .7)}`, "none", neon || st.kind === "chalk" ? acc : ink),
      zigzag: () => P(`M${n(x - r)} ${y} l${n(r * .4)} ${n(-r * .4)} l${n(r * .4)} ${n(r * .4)} l${n(r * .4)} ${n(-r * .4)} l${n(r * .4)} ${n(r * .4)}`, "none", acc),
      wave: () => P(`M${n(x - r * 1.2)} ${y} q${n(r * .3)} ${n(-r * .4)} ${n(r * .6)} 0 t${n(r * .6)} 0 t${n(r * .6)} 0 t${n(r * .6)} 0`, "none", acc),
      arrow: () => P(`M${n(x - r)} ${n(y + r * .3)} q${n(-r * .1)} ${n(-r * 1.1)} ${n(r * .8)} ${n(-r * 1)} q${n(r * .9)} ${n(r * .1)} ${n(r * 1)} ${n(r * .9)}`, "none", neon || mono ? acc : acc) + P(`M${n(x + r * .55)} ${n(y - r * .05)} l${n(r * .25)} ${n(r * .3)} l${n(r * .25)} ${n(-r * .45)}`, "none", neon || mono ? acc : acc),
      rays: () => P(`M${n(x - r * .7)} ${n(y + r * .2)} l${n(-r * .4)} ${n(-r * .4)} M${x} ${n(y - r * .1)} l0 ${n(-r * .6)} M${n(x + r * .7)} ${n(y + r * .2)} l${n(r * .4)} ${n(-r * .4)}`, "none", acc),
      bulb: () => P(`M${n(x - r * .45)} ${n(y + r * .3)} q${n(-r * .4)} ${n(-r * .5)} ${n(-r * .05)} ${n(-r * 1.0)} q${n(r * .5)} ${n(-r * .3)} ${n(r * .95)} 0 q${n(r * .35)} ${n(r * .5)} ${n(-r * .05)} ${n(r * 1.0)} Z M${n(x - r * .35)} ${n(y + r * .55)} l${n(r * .7)} 0 M${n(x - r * .25)} ${n(y + r * .78)} l${n(r * .5)} 0`, "none", ink) + P(`M${x} ${n(y - r * 1.15)} l0 ${n(-r * .3)} M${n(x - r * .85)} ${n(y - r * .75)} l${n(-r * .25)} ${n(-r * .2)} M${n(x + r * .85)} ${n(y - r * .75)} l${n(r * .25)} ${n(-r * .2)}`, "none", acc),
      rocket: () => P(`M${x} ${n(y - r)} q${n(r * .45)} ${n(r * .5)} ${n(r * .4)} ${n(r * 1.3)} l${n(-r * .8)} 0 q${n(-r * .05)} ${n(-r * .8)} ${n(r * .4)} ${n(-r * 1.3)}z`, F("#fff"), S(ink)) + P(`M${n(x - r * .4)} ${n(y + r * .2)} l${n(-r * .3)} ${n(r * .4)} l${n(r * .3)} 0 M${n(x + r * .4)} ${n(y + r * .2)} l${n(r * .3)} ${n(r * .4)} l${n(-r * .3)} 0`, "none", S(ink)) + P(`M${n(x - r * .2)} ${n(y + r * .45)} q${n(r * .2)} ${n(r * .6)} ${n(r * .4)} 0`, F(acc), S(acc)),
      cube: () => P(`M${n(x - r)} ${n(y - r * .4)} l${r} ${n(-r * .45)} l${r} ${n(r * .45)} l0 ${n(r * 1.1)} l${-r} ${n(r * .45)} l${-r} ${n(-r * .45)}z M${n(x - r)} ${n(y - r * .4)} l${r} ${n(r * .45)} l${r} ${n(-r * .45)} M${x} ${n(y + r * .05)} l0 ${n(r * 1.1)}`, "none", S(ink)),
      play: () => P(`M${n(x - r)} ${n(y - r * .7)} h${n(2 * r)} v${n(1.4 * r)} h${n(-2 * r)}z`, F(acc), S(acc)) + P(`M${n(x - r * .3)} ${n(y - r * .35)} l${n(r * .65)} ${n(r * .35)} l${n(-r * .65)} ${n(r * .35)}z`, F("#fff"), S(neon ? acc : ink)),
      planet: () => P(`M${n(x - r * .7)} ${y} a${n(r * .7)} ${n(r * .7)} 0 1 0 ${n(r * 1.4)} 0 a${n(r * .7)} ${n(r * .7)} 0 1 0 ${n(-r * 1.4)} 0z`, F(acc), S(acc)) + P(`M${n(x - r * 1.3)} ${n(y + r * .25)} Q${x} ${n(y - r * .6)} ${n(x + r * 1.3)} ${n(y - r * .1)}`, "none", "#FFD23F"),
      moon: () => P(`M${n(x - r * .2)} ${n(y - r)} a${r} ${r} 0 1 0 ${n(r * .9)} ${n(r * 1.7)} a${n(r * .75)} ${n(r * .75)} 0 1 1 ${n(-r * .9)} ${n(-r * 1.7)}z`, F("#FFE98A"), S("#FFE98A")),
      daisy: () => { let s = ""; for (let k = 0; k < 8; k++) s += `<ellipse cx="${x}" cy="${n(y - r * .6)}" rx="${n(r * .24)}" ry="${n(r * .45)}" fill="${F("#fff")}" stroke="${S(ink)}" stroke-width="${n(w * .7)}" transform="rotate(${k * 45} ${x} ${y})"/>`; return s + P(`M${n(x - r * .3)} ${y} a${n(r * .3)} ${n(r * .3)} 0 1 0 ${n(r * .6)} 0 a${n(r * .3)} ${n(r * .3)} 0 1 0 ${n(-r * .6)} 0z`, F("#F2A93B"), S(ink)); },
      sun: () => P(`M${n(x - r * .45)} ${y} a${n(r * .45)} ${n(r * .45)} 0 1 0 ${n(r * .9)} 0 a${n(r * .45)} ${n(r * .45)} 0 1 0 ${n(-r * .9)} 0z`, F("#F7D774"), S(ink)) + P(Array.from({ length: 8 }, (_, k) => { const a = k * Math.PI / 4; return `M${n(x + Math.cos(a) * r * .65)} ${n(y + Math.sin(a) * r * .65)} L${n(x + Math.cos(a) * r)} ${n(y + Math.sin(a) * r)}`; }).join(" "), "none", acc),
      leaf: () => P(`M${x} ${n(y + r)} C${n(x - r * .9)} ${n(y + r * .3)} ${n(x - r * .8)} ${n(y - r * .7)} ${x} ${n(y - r)} C${n(x + r * .8)} ${n(y - r * .7)} ${n(x + r * .9)} ${n(y + r * .3)} ${x} ${n(y + r)}Z M${x} ${n(y + r)} L${x} ${n(y - r * .7)}`, F("#3BA55C"), S(ink)),
      butterfly: () => P(`M${x} ${y} q${n(-r * .8)} ${n(-r * .8)} ${n(-r)} 0 q${n(r * .2)} ${n(r * .7)} ${r} 0 q${n(r * .8)} ${n(-r * .8)} ${r} 0 q${n(-r * .2)} ${n(r * .7)} ${-r} 0`, F(acc), S(ink)) + P(`M${x} ${n(y - r * .2)} l${n(-r * .2)} ${n(-r * .4)} M${x} ${n(y - r * .2)} l${n(r * .2)} ${n(-r * .4)}`, "none", S(ink)),
      camera: () => P(`M${n(x - r)} ${n(y - r * .5)} h${n(2 * r)} v${n(1.2 * r)} h${n(-2 * r)}z`, F("#3A3F7A"), S(ink)) + P(`M${n(x - r * .35)} ${n(y + r * .1)} a${n(r * .35)} ${n(r * .35)} 0 1 0 ${n(r * .7)} 0 a${n(r * .35)} ${n(r * .35)} 0 1 0 ${n(-r * .7)} 0z`, F("#9FD3FF"), S(ink)) + P(`M${n(x - r * .6)} ${n(y - r * .5)} l${n(r * .2)} ${n(-r * .3)} h${n(r * .5)} l${n(r * .2)} ${n(r * .3)}`, "none", S(ink)),
      onair: () => `<g>${P(`M${n(x - r * 1.5)} ${n(y - r * .5)} h${n(3 * r)} v${r} h${n(-3 * r)}z`, F("#FF5A5A"), S(ink))}<text x="${x}" y="${n(y + r * .3)}" font-family="Permanent Marker" font-size="${n(r * .78)}" text-anchor="middle" fill="${neon ? "#FF5A5A" : "#fff"}">ON AIR</text></g>`,
      flame: () => P(`M${x} ${n(y + r)} q${n(-r * .9)} ${n(-r * .4)} ${n(-r * .3)} ${n(-r * 1.4)} q${n(r * .1)} ${n(r * .4)} ${n(r * .35)} ${n(r * .5)} q0 ${n(-r * .5)} ${n(r * .35)} ${n(-r * .7)} q${n(r * .6)} ${n(r * .9)} ${n(r * .2)} ${n(r * 1.6)}z`, F("#FF7A2F"), S(ink)),
      wow: () => `<g>${P(`M${n(x - r * 1.3)} ${n(y - r * .6)} h${n(2.6 * r)} v${n(1.1 * r)} h${n(-1.4 * r)} l${n(-r * .4)} ${n(r * .4)} v${n(-r * .4)} h${n(-r * .8)}z`, F("#fff"), S(ink))}<text x="${x}" y="${n(y + r * .2)}" font-family="Luckiest Guy" font-size="${n(r * .9)}" text-anchor="middle" fill="${neon ? acc : "#3D7DD8"}">WOW</text></g>`,
      cursor: () => P(`M${n(x - r * .4)} ${n(y - r)} l0 ${n(r * 1.6)} l${n(r * .4)} ${n(-r * .35)} l${n(r * .3)} ${n(r * .65)} l${n(r * .28)} ${n(-r * .13)} l${n(-r * .3)} ${n(-r * .62)} l${n(r * .55)} ${n(-r * .05)} z`, F("#fff"), S(ink)),
    };
    // the wide signs are drawn smaller, so every doodle stays within about 1.35 r of its centre
    if (name === "onair" || name === "wow") { const r0 = r; r = r * (name === "onair" ? 0.84 : 0.95); const g0 = G[name](); r = r0; return st.kind === "sticker" ? stick(g0) : g0; }
    let g = (G[name] || G.star4)();
    return st.kind === "sticker" ? stick(g) : g;
    function stick(g) { return `<g filter="url(#cf-s)">${g.replace(/fill="(?!none)[^"]*"/g, 'fill="#fff"').replace(/stroke="[^"]*"/g, 'stroke="#fff"').replace(/stroke-width="[^"]*"/g, `stroke-width="${N(24 * u)}"`)}${g}</g>`; }
  }

  function defs(st, u) {
    const pen = st.kind === "pen" || st.kind === "pencil";
    const chalk = st.kind === "chalk";
    return `<defs>
<filter id="cf-w" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="${N(0.02 / u * 1000) / 1000}" numOctaves="2" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="${N((pen ? 6 : 10) * u)}" xChannelSelector="R" yChannelSelector="G" result="d"/>${chalk ? `<feTurbulence type="fractalNoise" baseFrequency="1.1 0.6" numOctaves="2" seed="8" result="g"/><feColorMatrix in="g" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.4 1.9" result="ga"/><feComposite in="d" in2="ga" operator="in"/>` : ""}</filter>
<filter id="cf-g" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="${chalk ? "1.1 0.6" : "0.9 0.25"}" numOctaves="2" seed="8" result="g"/><feColorMatrix in="g" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.4 ${chalk ? 1.6 : 1.9}" result="ga"/><feComposite in="SourceGraphic" in2="ga" operator="in"/></filter>
<filter id="cf-n" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="${N(9 * u)}" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="cf-s" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="${N(6 * u)}" dy="${N(8 * u)}" stdDeviation="${N(2 * u)}" flood-opacity=".25"/></filter>
</defs>`;
  }

  const styleById = (id) => STYLES.find((s) => s.id === id) || Cartoon.CUSTOM.find((s) => s.id === id) || STYLES[4];

  /* the whole set as one SVG. opt.doodles: false leaves out the pop-in doodles; opt.only: "doodles" gives them alone,
     each in its own .cf-doodle group with its own line filter (a small filter area each, cheap to boil live) */
  function set(room, styleId, opt = {}) {
    const st = typeof styleId === "object" ? styleId : styleById(styleId);
    const K = kit(room, st), W = room.width, H = room.height, u = K.u;
    const glow = st.kind === "neon";
    const lines = (inner) => (glow ? `<g filter="url(#cf-n)"><g filter="url(#cf-w)">${inner}</g></g>` : `<g filter="url(#cf-w)">${inner}</g>`);
    const doodle = ([x, y, r], i) => glyphSVG(st, st.deco[i % st.deco.length], x, y, r > 0 ? r : 40, i, u);
    if (opt.only === "doodles") {
      const each = (room.spots || []).map((s, i) => `<g class="cf-doodle" id="cf-d${i}" data-x="${s[0]}" data-y="${s[1]}">${lines(doodle(s, i))}</g>`).join("");
      return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" data-style="${st.id}">${defs(st, u)}<g id="cf-doodles">${each}</g></svg>`;
    }
    let body = room.draw(K);
    const extras = wallExtras(room, K);
    const spots = (room.spots || []).map((s, i) => `<g class="cf-doodle" id="cf-d${i}" data-x="${s[0]}" data-y="${s[1]}">${doodle(s, i)}</g>`).join("");
    // the wall base stays still; every drawn line (props, extras, doodles) boils through #cf-w
    const wallBase = body.match(/<g id="cf-wall-base">[\s\S]*?<\/g>/);
    const base = wallBase ? wallBase[0] : "";
    if (base) body = body.replace(base, "");
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" data-style="${st.id}">${defs(st, u)}${base}${lines(extras + body)}<g id="cf-doodles">${opt.doodles === false ? "" : lines(spots)}</g></svg>`;
  }

  /* one doodle of a style, for the keyword pop-ins (returned with its own filters so it can sit in any svg) */
  function glyph(styleId, i, x, y, r, u = 1) {
    const st = styleById(styleId);
    return glyphSVG(st, st.deco[i % st.deco.length], x, y, r, i, u);
  }

  /* ---------- 10 type styles: lines = ["FOR THE LOVE", "OF GOD!"], size = px of the first line ---------- */
  const up = (t) => t.toUpperCase();
  const TYPES = [
    { id: "T1", name: "Condensed poster", font: "Anton", cw: 0.45, blurb: "Tall bold letters, navy and red, a little tilt. Clean and loud.",
      line: (t, i, s) => `<div style="font:${s}px/0.95 Anton;color:${["#1E2A6B", "#E8442E"][i % 2]};transform:rotate(${i % 2 ? 1 : -2}deg);text-shadow:${N(s / 40)}px ${N(s / 36)}px 0 rgba(0,0,0,.18)">${up(t)}</div>` },
    { id: "T2", name: "Marker hand-lettering", font: "Permanent Marker", cw: 0.62, blurb: "Written with a thick marker, with a scribbled underline. Feels drawn on the wall.",
      line: (t, i, s) => `<div style="font:${s}px/1.05 'Permanent Marker';color:${["#111", "#E8442E"][i % 2]};transform:rotate(${i % 2 ? 2 : -4}deg)">${up(t)}</div>`,
      after: (s) => `<svg width="${N(s * 3.2)}" height="${N(s * 0.28)}" viewBox="0 0 720 60" style="display:block;margin:-${N(s * 0.04)}px auto 0"><path d="M20 30 Q200 5 360 30 T700 28" stroke="#111" stroke-width="14" fill="none" stroke-linecap="round"/></svg>` },
    { id: "T3", name: "Bubble 3D", font: "Luckiest Guy", cw: 0.6, blurb: "Fat rounded letters, yellow and pink with a dark outline and a deep 3D drop.",
      line: (t, i, s) => `<div style="font:${s}px/1 'Luckiest Guy';color:${["#FFD23F", "#FF6FB5", "#7FD3FF"][i % 3]};-webkit-text-stroke:${Math.round(s / 19)}px #1D1D1F;paint-order:stroke fill;text-shadow:0 ${Math.round(s / 16)}px 0 #1D1D1F;transform:rotate(${i % 2 ? 2 : -3}deg)">${up(t)}</div>` },
    { id: "T4", name: "Comic burst", font: "Bangers", cw: 0.48, blurb: "Comic-book lettering on a jagged yellow burst. Punchy and fun.",
      wrap: (inner) => `<div style="position:relative;display:inline-block;padding:0.35em 0.7em"><svg viewBox="0 0 980 560" preserveAspectRatio="none" style="position:absolute;left:-6%;top:-14%;width:112%;height:128%;z-index:-1;overflow:visible"><path d="M490 10 L560 110 L700 40 L690 160 L860 130 L770 240 L950 290 L770 340 L870 460 L690 420 L690 540 L560 450 L490 550 L420 450 L290 540 L290 420 L110 460 L210 340 L30 290 L210 240 L120 130 L290 160 L280 40 L420 110Z" fill="#FFE14F" stroke="#1D1D1F" stroke-width="10" stroke-linejoin="round"/></svg>${inner}</div>`,
      line: (t, i, s) => `<div style="font:${s}px/0.98 Bangers;letter-spacing:${N(s / 40)}px;color:${["#E8442E", "#1E2A6B"][i % 2]};-webkit-text-stroke:${Math.round(s / 30)}px #1D1D1F;paint-order:stroke fill;text-shadow:${N(s / 30)}px ${N(s / 26)}px 0 #1D1D1F;transform:rotate(${i % 2 ? 2 : -3}deg)">${up(t)}</div>` },
    { id: "T5", name: "Die-cut sticker", font: "Titan One", cw: 0.66, blurb: "Coloured letters with a thick white sticker border and a soft shadow.",
      line: (t, i, s) => `<div style="font:${s}px/1.04 'Titan One';color:${["#FF5A5A", "#3D7DD8", "#2E9E6A"][i % 3]};-webkit-text-stroke:${Math.round(s / 8)}px #fff;paint-order:stroke fill;filter:drop-shadow(${N(s / 35)}px ${N(s / 21)}px 0 rgba(0,0,0,.22));transform:rotate(${i % 2 ? 3 : -3}deg)">${up(t)}</div>` },
    { id: "T6", name: "Chalk", font: "Cabin Sketch", cw: 0.6, blurb: "Hand-drawn chalk letters, white and yellow, with a dusty edge.",
      line: (t, i, s) => `<div style="font:700 ${s}px/1.02 'Cabin Sketch';color:${["#F7F4EA", "#FFE46B"][i % 2]};text-shadow:0 0 3px #fff,${N(s / 55)}px ${N(s / 46)}px 0 rgba(0,0,0,.45),0 0 ${N(s / 12)}px rgba(0,0,0,.35)">${up(t)}</div>` },
    { id: "T7", name: "Neon script", font: "Yellowtail", cw: 0.48, blurb: "Glowing pink and cyan script, like a bar sign.", keepCase: true,
      line: (t, i, s) => { const g = ["#FF4FA3", "#52E8FF"][i % 2]; return `<div style="font:${s}px/1.08 Yellowtail;color:${["#FFE3F3", "#E0FBFF"][i % 2]};text-shadow:0 0 ${N(s / 23)}px ${g},0 0 ${N(s / 9)}px ${g},0 0 ${N(s / 4)}px ${g};transform:rotate(${i % 2 ? -3 : -5}deg)">${t}</div>`; } },
    { id: "T8", name: "Cut-out collage", font: "Anton", cw: 0.75, blurb: "Every letter cut from a different paper, like a ransom note.",
      line: (t, o, s) => { const F = ["Anton", "'Abril Fatface'", "'Titan One'", "'Rubik Mono One'", "Bangers"], BG = ["#fff", "#FFD23F", "#1D1D1F", "#FF7EB3", "#9AD0FF", "#E8442E"], FG = ["#1D1D1F", "#1D1D1F", "#fff", "#1D1D1F", "#1D1D1F", "#fff"];
        const k = o * 3; return `<div style="line-height:1.1">${[...up(t)].map((c, i) => { if (c === " ") return `<span style="display:inline-block;width:${N(s * 0.3)}px"></span>`; const j = (i + k) % 6; return `<span style="display:inline-block;font:${N(s * (0.86 + ((i * 37 + k) % 40) / 200))}px/1 ${F[(i + k) % 5]};background:${BG[j]};color:${FG[j]};padding:${N(s * .03)}px ${N(s * .06)}px;margin:${N(s * .02)}px;transform:rotate(${((i * 7 + k) % 11) - 5}deg);box-shadow:${N(s / 40)}px ${N(s / 28)}px 0 rgba(0,0,0,.22)">${c}</span>`; }).join("")}</div>`; } },
    { id: "T9", name: "70s groovy", font: "Shrikhand", cw: 0.7, blurb: "Swashy retro letters in orange with stacked mustard and brown shadows.",
      line: (t, i, s) => `<div style="font:${s}px/1.05 Shrikhand;color:${["#E8572A", "#4FA3A5"][i % 2]};text-shadow:${N(s / 36)}px ${N(s / 36)}px 0 #F2A93B,${N(s / 18)}px ${N(s / 18)}px 0 #7A3E1D;transform:rotate(${i % 2 ? 1 : -4}deg)">${up(t)}</div>` },
    { id: "T10", name: "Label tape", font: "Special Elite", cw: 0.68, blurb: "Typewriter letters on strips of white tape, stuck on at an angle.",
      line: (t, i, s) => `<div><div style="display:inline-block;margin:${i ? N(s * 0.12) : 0}px 0 0;background:#FBFAF5;padding:${N(s * .05)}px ${N(s * .24)}px 0;font:${s}px/1.05 'Special Elite';color:#1D1D1F;letter-spacing:${N(s / 19)}px;transform:rotate(${i % 2 ? 3 : -4}deg);box-shadow:0 ${N(s / 24)}px ${N(s / 12)}px rgba(0,0,0,.22);clip-path:polygon(0 4%,3% 0,97% 3%,100% 0,99% 96%,100% 100%,2% 98%,0 100%)">${up(t)}</div></div>` },
  ];
  const typeById = (id) => TYPES.find((t) => t.id === id) || Cartoon.CUSTOM_TYPES.find((t) => t.id === id) || TYPES[2];

  /* The safe zone: where giant type and its doodles must stay. Vertical video uses the Instagram Reels zone (key content
     in x 60-960 and y 220-1500 of 1080x1920, scaled to the frame); type starts at y 230. Other shapes keep 5% margins. */
  function safeZone(W, H) {
    if (H > W) return { x0: Math.round(W * 60 / 1080), y0: Math.round(H * 220 / 1920), x1: Math.round(W * 960 / 1080), y1: Math.round(H * 1500 / 1920), typeTop: Math.round(H * 230 / 1920) };
    return { x0: Math.round(W * 0.05), y0: Math.round(H * 0.05), x1: Math.round(W * 0.95), y1: Math.round(H * 0.95), typeTop: Math.round(H * 0.06) };
  }

  /* Browser only, fonts loaded: the real size of a keyword block in px, measured in its own font with every rotated
     line, letter and burst counted, plus the outline stroke (about size / 9.5) that the layout boxes do not include. */
  function measure(typeId, lines, size, opt = {}) {
    const host = document.createElement("div");
    host.style.cssText = "position:absolute;left:0;top:0;visibility:hidden;white-space:nowrap;width:max-content";
    host.innerHTML = typeHTML(typeId, lines, size, opt);
    document.body.appendChild(host);
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const el of [host.firstElementChild, ...host.querySelectorAll("*")]) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom);
    }
    host.remove();
    const pad = size / 9.5;
    return { w: x1 - x0 + pad, h: y1 - y0 + pad };
  }
  /* Browser only: the biggest size up to `start` whose measured block fits maxW x maxH. Never sized from the letter count. */
  function fitSize(typeId, lines, maxW, maxH, start) {
    let s = Math.max(8, Math.round(start));
    for (let i = 0; i < 24 && s > 8; i++) {   // stops only on a size that measured inside the box
      const m = measure(typeId, lines, s), k = Math.min(maxW / m.w, maxH / m.h);
      if (k >= 1) break;
      s = Math.max(8, Math.min(s - 1, Math.floor(s * k * 0.98)));
    }
    return s;
  }

  /* a first guess from the letter count (Node, before any browser measures it); the final size always comes from fitSize */
  function fit(typeId, lines, maxW, maxSize) {
    const t = typeById(typeId), longest = Math.max(...lines.map((l) => l.length), 1);
    return Math.round(Math.min(maxSize, maxW / (longest * t.cw)));
  }
  function typeHTML(typeId, lines, size, opt = {}) {
    const t = typeById(typeId);
    const sizes = lines.map((l, i) => Math.round(size * (opt.scales ? opt.scales[i] || 1 : 1)));
    let inner = lines.map((l, i) => t.line(l, i, sizes[i])).join("") + (t.after ? t.after(size) : "");
    if (t.wrap) inner = t.wrap(inner);
    return `<div class="cf-type" data-type="${t.id}" style="text-align:center;position:relative;z-index:0">${inner}</div>`;
  }

  /* fonts: the kit ships them in kit/fonts; base = the folder URL that holds that fonts dir */
  const FONT_FILES = { "Anton": "Anton-Regular.ttf", "Permanent Marker": "PermanentMarker-Regular.ttf", "Luckiest Guy": "LuckiestGuy-Regular.ttf", "Bangers": "Bangers-Regular.ttf",
    "Titan One": "TitanOne-Regular.ttf", "Cabin Sketch": "CabinSketch-Bold.ttf", "Yellowtail": "Yellowtail-Regular.ttf", "Abril Fatface": "AbrilFatface-Regular.ttf",
    "Rubik Mono One": "RubikMonoOne-Regular.ttf", "Shrikhand": "Shrikhand-Regular.ttf", "Special Elite": "SpecialElite-Regular.ttf" };
  function fontCSS(base = "fonts/") {
    return Object.entries(FONT_FILES).map(([f, file]) => `@font-face{font-family:"${f}";src:url("${base}${file}");${f === "Cabin Sketch" ? "font-weight:700;" : ""}font-display:block}`).join("\n");
  }

  const Cartoon = { STYLES, TYPES, CUSTOM: [], CUSTOM_TYPES: [], ROOM: null, set, glyph, typeHTML, fit, fitSize, measure, safeZone, fontCSS, FONT_FILES, styleById, typeById, roundRect,
    room(def) { Cartoon.ROOM = def; return def; },
    /* a custom doodle style: Object.assign a copy of a base style with new pal/ink/deco, then Cartoon.addStyle(...) */
    addStyle(s) { Cartoon.CUSTOM.push(s); return s; },
    addType(t) { Cartoon.CUSTOM_TYPES.push(t); return t; } };
  root.Cartoon = Cartoon;
  if (typeof module !== "undefined" && module.exports) module.exports = Cartoon;
})(typeof window !== "undefined" ? window : globalThis);
