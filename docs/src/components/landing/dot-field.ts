// Hero dot field
//
// A uniform dot grid (no vignette) with the Effecton "E" mark spelled out in
// slightly brighter dots joined by faint links. A wave travels down the glyph
// on a loop, and the pointer lifts whatever is near it.
//
// Only the plain dots are pre-rendered; the glyph is redrawn each frame, so it
// is kept off the static layer. See README.md for the tuning notes.

import { MARK_H, MARK_PATH, MARK_W } from './mark'

type Pt = { x: number; y: number; ph: number }
type Link = { a: Pt; b: Pt; mx: number; my: number; ph: number }

const GAP = 16 // grid pitch, matches the CSS fallback
const DOT = 1 // dot radius, css px

const A_BASE = 0.09 // plain dot at rest, matches the reference field

// The glyph breathes rather than sitting at a fixed brightness. The midpoint
// is set so the trough still clears the plain dots — at a lower midpoint the
// E used to dissolve into the field for part of every cycle.
const G_MID = 0.21
const G_AMP = 0.085 // glyph dot swings 0.125 – 0.295
const L_MID = 0.075
const L_AMP = 0.035 // link swings 0.040 – 0.110
const WAVE_K = 0.018 // rad per px along the travel axis: ~one wave tall
const WAVE_SPEED = 0.0016 // rad per ms: ~3.9s per cycle

// Under the pointer. Elements are lifted toward these, so the glyph reveals
// itself without the wave and the glow compounding into a hotspot.
const P_DOT = 0.32
const P_GLYPH = 0.46
const P_LINK = 0.24
const RADIUS = 150 // pointer influence, css px
const GROW = 0.8 // dots also swell a little near the pointer
const STEP = 0.02 // alpha quantisation, so a frame is a few fills
const TAU = Math.PI * 2

/**
 * Starts the field on `canvas`, which must fill `host`. Returns a function that
 * stops the animation and removes every listener and observer it installed.
 */
export function mountDotField(host: HTMLElement, canvas: HTMLCanvasElement): () => void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return () => {}

  const canHover = window.matchMedia('(hover: hover)').matches
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  let w = 0
  let h = 0
  let dpr = 1
  let plainPts: Pt[] = []
  let glyphPts: Pt[] = []
  let links: Link[] = []
  let base: HTMLCanvasElement | null = null // plain dots only
  let raf = 0
  let onScreen = true

  const target = { x: 0, y: 0 }
  const eased = { x: 0, y: 0 }
  let inside = false

  /* ---- Which grid cells fall inside the mark ---- */

  function glyphMask(cols: number, rows: number): (ix: number, iy: number) => boolean {
    const m = document.createElement('canvas')
    m.width = cols
    m.height = rows
    const mx = m.getContext('2d')
    if (!mx) return () => false

    // One mask pixel per grid cell. The E stands tall enough that its top and
    // bottom bars land in the empty bands above the badge and below the CTAs,
    // rather than hiding entirely behind the headline block — but it is capped
    // by width too, so a narrow viewport doesn't clip it into loose bars.
    let gh = rows * 0.86
    let gw = gh * (MARK_W / MARK_H)
    const maxW = cols * 0.62
    if (gw > maxW) {
      gw = maxW
      gh = gw * (MARK_H / MARK_W)
    }

    mx.translate((cols - gw) / 2, (rows - gh) / 2)
    mx.scale(gw / MARK_W, gh / MARK_H)
    mx.fillStyle = '#fff'
    mx.fill(new Path2D(MARK_PATH))

    const data = mx.getImageData(0, 0, cols, rows).data
    return (ix, iy) => data[(iy * cols + ix) * 4 + 3]! > 100
  }

  /* ---- Build ---- */

  function build() {
    // Measure the canvas, not the host: the host has a 1px border, so its
    // border-box is ~2px wider than the canvas's own box. Sizing the backing
    // store from the host offsets and stretches the whole field.
    const rect = canvas.getBoundingClientRect()
    w = rect.width
    h = rect.height
    if (w <= 0 || h <= 0) return

    dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.round(w * dpr)
    canvas.height = Math.round(h * dpr)
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)

    const cols = Math.floor(w / GAP)
    const rows = Math.floor(h / GAP)
    // Centre the grid so the margins match on both sides.
    const ox = (w - (cols - 1) * GAP) / 2
    const oy = (h - (rows - 1) * GAP) / 2

    const inGlyph = glyphMask(cols, rows)
    const grid: (Pt | null)[][] = []
    plainPts = []
    glyphPts = []

    for (let iy = 0; iy < rows; iy++) {
      grid[iy] = []
      for (let ix = 0; ix < cols; ix++) {
        const x = ox + ix * GAP
        const y = oy + iy * GAP
        const g = inGlyph(ix, iy)
        // Phase leans vertical so the E's bars light in sequence.
        const p: Pt = { x, y, ph: (y * 0.85 + x * 0.35) * WAVE_K }
        grid[iy]![ix] = g ? p : null
        ;(g ? glyphPts : plainPts).push(p)
      }
    }

    // Join orthogonally adjacent glyph dots; that is what makes it read as a
    // letter rather than a slightly brighter smudge.
    links = []
    const link = (a: Pt, b: Pt): Link => {
      const mx = (a.x + b.x) / 2
      const my = (a.y + b.y) / 2
      return { a, b, mx, my, ph: (my * 0.85 + mx * 0.35) * WAVE_K }
    }
    for (let iy = 0; iy < rows; iy++) {
      for (let ix = 0; ix < cols; ix++) {
        const a = grid[iy]![ix]
        if (!a) continue
        const right = ix + 1 < cols ? grid[iy]![ix + 1] : null
        const down = iy + 1 < rows ? grid[iy + 1]![ix] : null
        if (right) links.push(link(a, right))
        if (down) links.push(link(a, down))
      }
    }

    base = renderStatic()
    frame(performance.now())
  }

  function renderStatic(): HTMLCanvasElement | null {
    const c = document.createElement('canvas')
    c.width = canvas.width
    c.height = canvas.height
    const g = c.getContext('2d')
    if (!g) return null
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.fillStyle = `rgba(255,255,255,${A_BASE})`
    g.beginPath()
    plainPts.forEach((p) => {
      g.moveTo(p.x + DOT, p.y)
      g.arc(p.x, p.y, DOT, 0, TAU)
    })
    g.fill()
    return c
  }

  /* ---- Frame ---- */

  // Falloff in [0,1]; 0 outside the pointer's reach.
  function pull(x: number, y: number): number {
    if (!inside) return 0
    const d = Math.hypot(x - eased.x, y - eased.y)
    if (d >= RADIUS) return 0
    const t = 1 - d / RADIUS
    return t * t
  }

  function fillDots(groups: Map<number, Pt[]>) {
    groups.forEach((group, key) => {
      const a = Math.floor(key / 16) * STEP
      const r = DOT * (1 + GROW * ((key % 16) / 6))
      ctx!.fillStyle = `rgba(255,255,255,${a.toFixed(3)})`
      ctx!.beginPath()
      group.forEach((p) => {
        ctx!.moveTo(p.x + r, p.y)
        ctx!.arc(p.x, p.y, r, 0, TAU)
      })
      ctx!.fill()
    })
  }

  function frame(now: number) {
    const phase = reduced ? 0 : now * WAVE_SPEED

    ctx!.clearRect(0, 0, w, h)
    if (base) {
      // Blit device-pixel to device-pixel. Scaling the base into a CSS-pixel
      // rect resamples it whenever devicePixelRatio is not a whole number,
      // which softens every dot and drifts its peak alpha.
      ctx!.save()
      ctx!.setTransform(1, 0, 0, 1, 0, 0)
      ctx!.drawImage(base, 0, 0)
      ctx!.restore()
    }

    // Glyph links, under the dots.
    const linkGroups = new Map<number, Link[]>()
    links.forEach((l) => {
      const rest = reduced ? L_MID : L_MID + L_AMP * Math.sin(phase - l.ph)
      const k = pull(l.mx, l.my)
      const a = rest + (P_LINK - rest) * k
      if (a <= 0.004) return
      const q = Math.round(a / STEP)
      let g = linkGroups.get(q)
      if (!g) linkGroups.set(q, (g = []))
      g.push(l)
    })
    ctx!.lineWidth = 1
    linkGroups.forEach((group, q) => {
      ctx!.strokeStyle = `rgba(255,255,255,${(q * STEP).toFixed(3)})`
      ctx!.beginPath()
      group.forEach((l) => {
        ctx!.moveTo(l.a.x, l.a.y)
        ctx!.lineTo(l.b.x, l.b.y)
      })
      ctx!.stroke()
    })

    // Glyph dots. Key on quantised alpha *and* radius so both stay batched.
    const glyphGroups = new Map<number, Pt[]>()
    glyphPts.forEach((p) => {
      const rest = reduced ? G_MID : G_MID + G_AMP * Math.sin(phase - p.ph)
      const k = pull(p.x, p.y)
      const a = rest + (P_GLYPH - rest) * k
      if (a <= 0.004) return
      const key = Math.round(a / STEP) * 16 + Math.round(k * 6)
      let g = glyphGroups.get(key)
      if (!g) glyphGroups.set(key, (g = []))
      g.push(p)
    })
    fillDots(glyphGroups)

    // Plain dots only need topping up where the pointer is.
    if (inside) {
      const plainGroups = new Map<number, Pt[]>()
      plainPts.forEach((p) => {
        const k = pull(p.x, p.y)
        if (k <= 0) return
        const add = (P_DOT - A_BASE) * k
        if (add <= 0.004) return
        const key = Math.round(add / STEP) * 16 + Math.round(k * 6)
        let g = plainGroups.get(key)
        if (!g) plainGroups.set(key, (g = []))
        g.push(p)
      })
      fillDots(plainGroups)
    }
  }

  /* ---- Loop ---- */

  const tick = (now: number) => {
    eased.x += (target.x - eased.x) * 0.18
    eased.y += (target.y - eased.y) * 0.18
    frame(now)
    raf = onScreen ? requestAnimationFrame(tick) : 0
  }

  const run = () => {
    if (!raf && onScreen && !reduced) raf = requestAnimationFrame(tick)
  }
  const halt = () => {
    if (raf) {
      cancelAnimationFrame(raf)
      raf = 0
    }
  }

  host.classList.add('has-dots')
  build()

  const onPointerMove = (e: PointerEvent) => {
    const r = canvas.getBoundingClientRect()
    target.x = e.clientX - r.left
    target.y = e.clientY - r.top
    if (!inside) {
      eased.x = target.x
      eased.y = target.y
      inside = true
    }
  }
  const onPointerLeave = () => {
    inside = false
  }
  if (canHover && !reduced) {
    host.addEventListener('pointermove', onPointerMove)
    host.addEventListener('pointerleave', onPointerLeave)
  }

  // The wave runs forever, so stop paying for it once the hero scrolls away.
  const visibility = new IntersectionObserver(
    (entries) => {
      onScreen = entries[0]?.isIntersecting ?? true
      if (onScreen) run()
      else halt()
    },
    { rootMargin: '80px' },
  )
  visibility.observe(host)

  run()

  let resizeTimer: ReturnType<typeof setTimeout> | undefined
  const resize = new ResizeObserver(() => {
    clearTimeout(resizeTimer)
    resizeTimer = setTimeout(build, 120)
  })
  resize.observe(canvas)

  return () => {
    halt()
    clearTimeout(resizeTimer)
    resize.disconnect()
    visibility.disconnect()
    host.removeEventListener('pointermove', onPointerMove)
    host.removeEventListener('pointerleave', onPointerLeave)
    host.classList.remove('has-dots')
  }
}
