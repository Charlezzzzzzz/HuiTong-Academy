# GitHub 参考项目清单

## 2026-10-31 界面与卷轴转场复核

本轮重新检索了纸张世界、卷轴式 WebGL 叙事和水墨转场项目。实际只借鉴交互节奏和性能架构，不复制源码：

- [architech97/bao-scroll-story](https://github.com/architech97/bao-scroll-story)：参考纸张世界中的卷轴式镜头转场；许可证需在固定提交处复核。
- [lhlGitHub/hand-drawn-storybook-animation-skill](https://github.com/lhlGitHub/hand-drawn-storybook-animation-skill)：参考中国水墨故事动画的分镜和留白；许可证需在固定提交处复核。
- [shin4/inkpond](https://github.com/shin4/inkpond)：参考 Canvas 2D 墨晕转场、静态层预计算和性能降级；仓库说明标注 MIT。
- [airbate/shuimo-liuyun](https://github.com/airbate/shuimo-liuyun)：继续参考纸纹、墨色扩散和传统颜料表现；仓库 README 标注 MIT，但上游来源仍需单独核查。

会通的卷轴入口采用本项目自己的 DOM/CSS 结构：单次展开、单次收卷、可降级为静态纸面，不引入上述项目的运行时代码。

检索时间：2026-10-28。共 4 条检索线成功返回（27 个仓库）；「鲁班锁交互」与「中式网页美学」两条检索线因上游内容检查错误未返回，若需要可另行补检。
以下仓库仅作技术参考，许可证以各仓库为准；清单中标注了实际看到的许可证。

## 水墨 3D / 墨化渲染（ink3d）

**工程要点**
- The ink look is a screen-space pass, not a per-object material: render the hall normally, blur a copy at a 2-texel radius, raise it to about 1.25, multiply by paper. webgl-landscape does an entire painting in roughly 30 GLSL lines, which lets us keep ordinary MeshStandardMaterial lighting and add only one full-screen quad.
- Blur alone reads as fog. Gate diffusion by a wetness map and make it anisotropic along paper fibres (8 taps, along-fibre weight about 5x across-fibre, 30-40 iterations, then freeze). The hall is static, so bake diffusion into a texture at load and animate only the lock/gate reveal, giving zero per-frame cost.
- For 3D meshes the ink edge is a rim term plus distance-graded brush stages (勾/皴/染). In a top-down hall the camera distance is nearly constant, so replace distance with world-depth bands and a haze mix toward paper colour: far pillars and figures should lose contrast, not just blur.
- Billboarded ink figures need anti-halo math, not just alphaTest. Reconstruct pigment from the sprite RGB and multiply alpha by a chroma-based fringe term plus a ground-fade, otherwise every figure shows a 1px coloured outline against the paper. Use premultiplied alpha and a soft radial contact shadow under each seated figure.
- Paper is the global unifier: one 2048px procedural sheet (mottle, long fibres, blotches, edge ageing) multiplied over both the WebGL canvas and the DOM overlay makes 3D, ink lines and Chinese text read as one sheet. Reuse the same texture in CSS so the name labels do not look pasted on.
- All of this fits the no-build constraint: the diffusion and paper passes are hand-written ShaderMaterial/RenderTarget code with no npm deps, and textures are generated once on a Canvas at startup. The only heavy optional item is the fluid sim, which should be a one-shot 512px dye burst at the gate opening.

### 23ag1/ink-wash-painting-skill　★ 2
- 地址：https://github.com/23ag1/ink-wash-painting-skill
- 许可证：none declared (no LICENSE file; treat as all rights reserved)
- 相关性：WebGL2 procedural 水墨 kit: paper, wash, ink and a wetness-gated diffusion pass written as reusable GLSL modules plus a Canvas brush library. Densest source of ink-material code found, though it targets 2D paintings rather than Three.js.
- 可借鉴：Port kit/passes/diffuse.frag (simplified MoXi: 8-neighbour transport gated by a wetness map, anisotropic along an fbm-rotated fibre field, uRate ~0.11, uCross ~0.2, 30-40 ping-pong steps) to a pair of Three.js WebGLRenderTargets. Lift paper.glsl's paperMottle / paperFibres (pow(1-|2*noise-1|,18) long fibres) / paperBlotch / paperAge, wash.glsl's edgeDarken + washHalo (晕) and ink.glsl's inkBleed as GLSL snippets inside onBeforeCompile or one full-screen post pass. brush/hairy.js gives the bristle model (per-bristle ink load, 飞白 dry streaks, pressed entry, 回锋 exit) as a spec for procedurally drawn figures.

### jammyfu/xiangsheng-genealogy　★ 1
- 地址：https://github.com/jammyfu/xiangsheng-genealogy
- 许可证：MIT
- 相关性：React Three Fiber ink-wash 3D atlas: layered painted scenery on a xuan-paper sheet, ink sprites, cinnabar accents and a spatial camera. Closest working analogue to our hall's look and structure.
- 可借鉴：src/components/SceneryLayers.tsx patches MeshBasicMaterial via onBeforeCompile, replacing `#include <map_fragment>`: recovers pigment from RGB, computes `fringe = 1.0-smoothstep(0.38,0.7,chroma)` to kill anti-aliased colour halos, derives alpha from `coverage`, mixes toward paper colour (0.86,0.83,0.74) by a per-layer `haze` uniform, and fades each layer's foot with `smoothstep(footUv-0.01, footUv+footSoftness, vMapUv.y)`. That is exactly the treatment for ink figures billboarded on the six cushions. Also shows depthWrite:false / depthTest:false / alphaTest:0.035 sprite settings and a tiny radial-gradient ShaderMaterial for soft contact shadows.

### sacshadow/3D_ChineseInkPaintingStyleShader　★ 479
- 地址：https://github.com/sacshadow/3D_ChineseInkPaintingStyleShader
- 许可证：MIT
- 相关性：Unity implementation of a 3D Chinese-ink renderer; the only sizeable 3D (not 2D) reference found. Shaders are organized by the traditional painting steps 勾 (outline), 皴擦 (texture strokes) and 染 (wash), with distance-driven brush treatment.
- 可借鉴：Take the pipeline structure, not the code (CG/HLSL, README has only a preview image). Concrete ideas readable in CIPR_0_Gou_step_0.shader and CIPR_2_Ran_And_Other_Diffuse.shader: rim light as the ink edge (`rimLight = pow(1-saturate(dot(V,N)), _RimRate)`); outline width modulated by a 飞白 noise texture (`_OutlineWidth0/1`, `_OutlineNoiseCtrl`); and per-distance control of brush stages (`_DistanceCtrl {MaxDistance, outlineDrop, rimClose, rimFar}`) plus screen-height bands (`_AreaBegin/_AreaEnd`). In a top-down hall, swap camera distance for world-depth bands to vary ink density near/far.

### DCtheTall/webgl-landscape　★ 6
- 地址：https://github.com/DCtheTall/webgl-landscape
- 许可证：none declared (no LICENSE file)
- 相关性：Tiny Sumi-e WebGL renderer implementing a published ink-painting model: fractal-simplex mountains, brush-texture reflection, tonal LUT and a paper-multiply post pass. Very readable TypeScript + glslify source.
- 可借鉴：src/shaders/paper/fragment.glsl is the entire 'make it ink' pass in about 30 lines: 3x3 Gaussian (weights .0625/.125/.25) sampled at 2-texel offsets, then pow(rgb, 1.25) to deepen the wash, multiplied by a paper texture. Apply it directly to our hall's scene render target. landscape/fragment.glsl also samples a 1D tones.jpg LUT by luminance (material-agnostic tonal compression) and uses the reflection vector as UV into a brush texture, a cheap way to get brush marks onto curved surfaces like the lock or roof.

### TanShilongMario/InkPainting　★ 43
- 地址：https://github.com/TanShilongMario/InkPainting
- 许可证：MIT
- 相关性：Pure front-end 水墨 painting tool (Canvas 2D, no build) with an explicit, tunable ink/paper physical model. Best used as a parameter dictionary and texture baker rather than as rendering code.
- 可借鉴：app.js defines 8 ink levels (焦墨 to 烟墨) each with alpha/dry/bleed/spread, and four paper presets (玉版宣, 仿古宣, 茶笺, 月白笺) with grain count, fibre count and length, mottle, vignette and bleed/flow/absorb multipliers. pigmentForInk() desaturates and blends toward the paper tint as wash increases. Bake the paper specs once into 1024-2048px CanvasTextures (reusable as the CSS background behind DOM labels) and drive ink-figure opacity from the same 8-level table.

### WishMelz/AquaInkGL　★ 392
- 地址：https://github.com/WishMelz/AquaInkGL
- 许可证：none declared (no LICENSE file; upstream PavelDoGreat/WebGL-Fluid-Simulation is MIT)
- 相关性：WebGL fluid-simulation background explicitly built as a 水墨 diffusion effect; a fork of the stable-fluids demo with ink-coloured dye. Good for one hero moment, too heavy for the whole hall.
- 可借鉴：The ping-pong pass graph: splat (exp(-dot(p,p)/radius)), advection with manual bilerp, divergence, curl and vorticity confinement, plus resolution tiers (DYE_RESOLUTION 512 mobile / 1024 desktop) and dissipation tuning. Use it once when the Lu Ban lock opens: a burst of ink diffusing behind the gate, frozen after about 2 seconds. Reimplement from the MIT upstream rather than copying this repo's files, since this fork carries no license.

### LingDong-/shan-shui-inf　★ 6.4k
- 地址：https://github.com/LingDong-/shan-shui-inf
- 许可证：MIT
- 相关性：Procedural Shan Shui landscape generated entirely in JS as SVG, infinitely scrolling. 2D only, but the best open library of brush-mark geometry: mountains, trees, water, boats, buildings from noise and math.
- 可借鉴：index.html's `stroke(ptlist, args)` builds a variable-width ribbon: width `wid*fun(i/n)` modulated by `(1-noi)+noi*Noise.noise(i*0.5,n0)`, with averaged-angle miter joins. That is a ready algorithm for wobbling ink lines (figure contours, room edges, engraved lines on the lock). `poly`, `blob`, `shatter`, `bark`, `water`, `mountplanner` and `vegetate` supply a motif vocabulary you can port to Canvas2D and use as billboard textures or wall murals behind the gate.

**注意事项**
- Licensing is mixed: AquaInkGL, webgl-landscape and ink-wash-painting-skill ship no LICENSE file, so treat them as all rights reserved and reimplement the ideas rather than copying files. MIT: sacshadow, InkPainting, xiangsheng-genealogy, shan-shui-inf.
- There is no production-grade Three.js ink-wash library on GitHub. Every candidate is either 2D WebGL2/Canvas, Unity HLSL, or app-specific React code, so budget port time rather than expecting a drop-in module.
- ileivoivm/inkField (167 stars) is the best-looking digital ink system but deliberately closed source; the README states the engine script.js is not open source. Dead end for code reuse.
- shan-shui-inf is a single 126 KB index.html of 2D SVG, with no 3D or shaders; it is a motif and line-geometry reference only, not a rendering technique.
- GitHub search API rate limit was hit mid-scout, so coverage is not exhaustive. Star counts were read on 2026-10-28 from the search API or the repo page; shan-shui-inf shows 6.4k rather than an exact integer.
- Adjacent but out of scope: shuimo-design/shuimo-ui (397 stars, MIT) is a 水墨-style Vue UI kit that could style the code keypad and DOM overlay but has no 3D ink rendering; paper-design/shaders (Apache-2.0) provides procedural grain/noise that could feed a paper texture but has no ink or wash modules (not deeply verified).

## 相机、房间与过场（camera）

**工程要点**
- Use two camera rigs, not one. A dedicated OrthographicCamera looking straight down (position y=34, up=(0,0,-1) to fix screen-north, rotation disabled) is the clean way to get the 6-cushion plan view; OrbitControls has a gimbal singularity when polar angle hits 0, which is why both reference projects either cap minPolarAngle (~0.1-0.3) or switch to a separate ortho camera. Then use a PerspectiveCamera for dollhouse and seated modes, and never morph between projection types mid-flight.
- Tween in polar coordinates for the overview -> seat move: interpolate (look-at target, camera direction, distance) rather than raw position (ha-3d's stepAnim), plus quaternion slerp for the final orientation (home-3d). A straight lerp from a 20 m overhead pose to a 1.1 m seated pose can pass through roof beams, lanterns or figures; direction+radius interpolation keeps the path on a controllable arc.
- Timing that reads as 'cinematic' in both codebases: 750 ms - 1.15 s with easeInOutQuad. Drive it from wall-clock delta with dt clamped to 0.05, disable controls while flying, and re-enable them with OrbitControls.target already synced to the goal - otherwise damping fights the tween on handoff.
- Seated POV numbers: three.js games_fps puts the eye at 1.0 m (capsule top), well below a standing 1.62 m; for cross-legged sitting on a 蒲团 use eye height ~1.0-1.1 m, pitch clamp around +/-75 deg, and a ~1.3 cm sine bob only while moving. Keep near plane ~0.05 so the cushion and the figure in front do not clip.
- FOV is part of the visual language: home-3d uses 68 deg for walk, 42 deg for dollhouse, 21 deg for the long-lens section view. In the reference the FOV is snapped at mode start, which is a visible pop - tween fov alongside position and call updateProjectionMatrix() every frame for our transition.
- Pre-warm shader compilation at load: attach clipping planes to wall/ceiling materials immediately with a no-op constant, create all materials (including the ink-line figure shaders) up front, then only change constants at runtime. Combined with on-demand rendering (render only when the camera or state changes), a static seated scene costs almost nothing per frame.

### rzx007/home-3d　★ 0
- 地址：https://github.com/rzx007/home-3d
- 许可证：None (no LICENSE file in repo)
- 相关性：A no-build-step ES-module three.js apartment demo with exactly the four views we need: dollhouse cutaway, orthographic top-down, 1.35 m section cut, and pointer-lock first-person walk. src/views.js is a compact, readable reference for switching between them.
- 可借鉴：src/views.js: flyTo() snapshots flyFrom/flyFromQ/flyFromTarget and stepFly() does position.lerpVectors + quaternion slerp with easeInOut over FLY_DUR = 1.15 s of wall-clock time (dt clamped to 0.05). Top view is a separate OrthographicCamera parked at y=34 with up=(0,0,-1) so north stays up, rotation disabled, pan/zoom only. Clipping planes are attached to wall materials at init with constant=100 ('no cut') so shaders compile once and mode switches do not hitch. Walk mode: EYE = 1.62, 0.26 m collision radius, 1.3 cm head bob only while moving, pitch clamped to +/-1.35 rad. Read for architecture only - no license, so do not copy code.

### yomotsu/camera-controls　★ 2.4k
- 地址：https://github.com/yomotsu/camera-controls
- 许可证：MIT
- 相关性：Mature plain-three.js camera controller with built-in smooth transitions and promise-returning moves. It can replace most hand-rolled tween code for the gate-open -> top-down -> seated sequence.
- 可借鉴：setLookAt(x, y, z, tx, ty, tz, true) animates the camera to a viewpoint; smoothTime defaults to 0.25 s; every transition returns a Promise, so moves can be sequenced with await (README shows await cameraControls.dollyTo(3, true)). fitToBox() frames the whole hall for the overhead shot, and it supports both perspective/orthographic cameras and a first-person/pointer-lock mode, so one controller can cover overview and seated look-around. ES module, no build step.

### mrdoob/three.js　★ 117.1k
- 地址：https://github.com/mrdoob/three.js
- 许可证：MIT
- 相关性：Canonical source for the two primitives we need: pointer-lock first-person look and capsule/Octree collision. Confirmed in examples/files.json that games_fps, misc_controls_pointerlock and webgl_camera exist.
- 可借鉴：examples/games_fps.html: camera.position.copy(playerCollider.end) - the camera rides the capsule's top endpoint (initial end.y = 1.0, bottom y = 0, radius 0.35), giving a 1.0-unit eye height; collision via worldOctree.capsuleIntersect(), 5 physics substeps per frame, frame dt capped at 0.05. Copy the 'eye at capsule end' pattern and just lower the endpoint to ~1.05 m for seated. examples/misc_controls_pointerlock.html: minimal Euler-order 'YXZ' mouse-look with pitch clamp, usable if we skip a controller library.

### joris-db/ha-3d-floorplan　★ 21
- 地址：https://github.com/joris-db/ha-3d-floorplan
- 许可证：MIT
- 相关性：Single-file three.js dollhouse of a house with one camera preset per room plus a whole-house view - the closest open implementation of 'pick a spot, camera glides there' at room scale.
- 可借鉴：assets/template.html (verified source): goView()/stepAnim() tween OrbitControls.target, the camera-to-target direction and the distance - not raw position - over 750 ms with easeInOutQuad. That polar interpolation produces a natural arc and avoids flying through walls. Cut-away logic lowers any wall between camera and visible room by scaling the wall group's Y to 17% (lerped 0.2 per frame) and hides wall-head children below h=0.9. Also: on-demand rendering (draw only when controls fire 'change'), adaptive resolution, and min/maxPolarAngle clamps so the camera cannot dip under the floor.

### tweenjs/tween.js　★ 10.1k
- 地址：https://github.com/tweenjs/tween.js
- 许可证：MIT (LICENSE file verified)
- 相关性：Dependency-light MIT tween engine with no CSS/colour handling and no render loop of its own - fits a no-build ES-module page better than GSAP when we need sequenced camera moves.
- 可借鉴：Tween a proxy object {t:0} and drive camera position/quaternion in onUpdate, using Easing.Quadratic.InOut for the same ease both demos hand-roll; use .chain()/.delay() to sequence gate unlock -> camera descend -> seated settle; call Tween.update(performance.now()) in the RAF loop for wall-clock timing. It also gives elastic/back easings for a subtle 'settle' on the cushion.

**注意事项**
- rzx007/home-3d is the best technical match but has NO LICENSE file (root listing: .gitignore, README.md, index.html, package.json, styles.css, plus src/ and vendor/). Its techniques are readable, but code cannot be reused verbatim; 0 stars and a single author, so treat it as an unvetted reference implementation.
- yui277/ArchViz-Lite (113 stars) came up as an architectural-visualization candidate but is CC BY-NC-SA 4.0 with proprietary UI/CSS and a commercial-use prohibition - not usable for our prototype's code.
- GSAP is not open source (standard no-charge license, not OSI); if license hygiene matters, use MIT tween.js or camera-controls' built-in transitions instead. pmndrs/drei's CameraControls/Bounds are React Three Fiber components - the patterns transfer, the code does not, since our stack is plain Three.js ES modules.
- SeanWong17/building-sunlight-simulator (488 stars, MIT) is the same vanilla/vendored-three/no-backend stack and does 2D-plan-to-3D with a bilingual Chinese UI, but its README documents no camera transitions or orthographic top view - a near-miss, not a technique source.
- Search quality was poor: WebSearch returned mostly CSDN/SEO blog spam and Douyin 'GitHub trending' lists, and unauthenticated GitHub repo search hit the 10 requests/minute limit after about six queries. 'Dollhouse' on GitHub mostly returns unrelated projects (The Sims Online remake, IoT nodes, baby-item managers).
- No repository found that implements a seated assembly-hall POV or cushion-based camera placement specifically; that behavior has to be composed from the FPS eye-height pattern (three.js games_fps) and the room-to-view transitions (home-3d, ha-3d-floorplan).

## 笔法、墨迹与转场（inkbrush）

**工程要点**
- Dry brush is cheaper as a bristle bundle than as a texture: offset ~40-60 sub-strokes across the brush width, give each its own ink budget, deplete faster at the edges (edgeDry = 0.6 + 0.8*|offset|), and drop segments once ink runs out — the holes are the kasure. Add a speed-gated noise skip for 飞白. enso-maker does this in ~200 lines of Canvas/SVG, so it is the first thing to port for strokes on the gate and for the ink-drawn figures.
- Separate silhouette from body: use perfect-freehand to get one clean pressure-varying outline, fill it flat, then composite paper noise inside with 'source-atop' and a second, darker edge line. This avoids per-pixel ink simulation while still reading as brush rather than as a vector line, and it keeps stroke count low for the 6-figure reveal.
- Ink edges come from displacement, not blur. feTurbulence(fractalNoise, baseFrequency 0.9, 2 octaves) + feDisplacementMap(scale 3.2) roughens a stroke into a bleeding edge, and anisotropic turbulence (baseFrequency '0.035 0.6') makes paper fibers. Caveat: Canvas2D ctx.filter='url(#f)' support is uneven, so render the ink layer to an offscreen canvas and apply the filter at the element level (CSS filter), or bake the displacement into textures once at load.
- For a full-screen ink wipe in a Canvas 2D overlay, animate a mask, not a shader: keep a full-res mask canvas, stamp a jagged band of overlapping feathered radial-gradient blobs advancing along the wipe direction with per-blob delays, then draw the incoming scene with globalCompositeOperation='destination-in'. inkpond's '墨晕' scene change is the same idea and is the proof it reads correctly at 60 fps.
- Budget the ink layer explicitly. inkpond's numbers are a good default: ~2 ms of script per frame against an 8 ms budget, cell/particle size tiers (16 px @60 fps, 22 px @30 fps, still-frame fallback), demote when the 60-frame p95 exceeds 8 ms, cap DPR around 1.5-2, and keep the ink atlas under 4096 px. For us: pre-bake paper and cushion textures, animate only the seated transition, and freeze the ink background while the camera is moving.
- Treat color as pigment on paper, not as RGB. Ink layering with Beer–Lambert (paper × exp(−A)) plus multiply blending keeps six differently colored cushions looking like dyed cloth/ink rather than saturated UI swatches, and stops the ink figures from turning muddy when they overlap each other.

### evoluteur/enso-maker　★ 3
- 地址：https://github.com/evoluteur/enso-maker
- 许可证：MIT
- 相关性：Zero-dependency, single-page sumi-e brush generator: an ensō painted with 46 bristles, dry-brush streaks, rice-paper texture and a red seal, in plain HTML/CSS/JS with no build step. This is the closest published implementation of the dry-brush (kasure) look we need.
- 可借鉴：The stroke is a bundle of 46 bristles offset across the brush width (js/enso.js); each bristle carries its own ink load and depletion is scaled by edgeDry = 0.6 + 0.8*|offset| so edges dry first, and a bristle skips a segment once remaining ink falls below ~0.18 + 0.25*noise — those gaps are the dry-brush streaks. High-speed skip: if p.speed > 0.8 and noise < 0.2*dry the bristle lifts (飞白). Bleed edge is an SVG filter: feTurbulence type=fractalNoise baseFrequency 0.9, 2 octaves, then feDisplacementMap scale 3.2; paper fibers use anisotropic turbulence baseFrequency '0.035 0.6'; the seal is stamped with 2.5-scale displacement and a ~4° hand-drawn rotation. Portable to Canvas 2D almost line for line.

### acamposuribe/p5.brush　★ 1.2k
- 地址：https://github.com/acamposuribe/p5.brush
- 许可证：MIT
- 相关性：Mature painterly brush engine (pencils, charcoal, markers, watercolor fills, hatching, vector fields) with a standalone WebGL2 build that needs nothing but a browser; the best reference for realistic ink/watercolor body rather than a flat line.
- 可借鉴：Read it for the watercolor fill algorithm (bleeding, pigment rings, granulation, texture) and the hatch_brush massing pattern — both map onto our ink-wash shading. 'brush.addField()' vector fields bend strokes along a flow, directly reusable for drifting ink smoke around the hall. Ships as ES module dist/brush.js with no build step, but the standalone build is WebGL2-only, so use it as an algorithm reference or an offscreen ink canvas rather than mixing it into the p5/Three scene. License MIT.

### shin4/inkpond　★ 0
- 地址：https://github.com/shin4/inkpond
- 许可证：MIT (bundled font subsets SIL OFL 1.1)
- 相关性：Canvas 2D ink-wash background library: Chinese glyphs composed into mountains/ponds, click-to-drop ink that spreads and slowly fades, and scene changes that cross over '以墨晕的方式' — i.e. a real Canvas 2D ink-blot and ink-dissolve transition, zero runtime dependencies.
- 可借鉴：Its performance architecture is the most valuable part: each glyph rasterized once into a texture atlas, static compositions precomputed, slow layers (mist) refreshed every 4th frame, ~2 ms/frame script cost against an 8 ms budget, quality tiers (16 px cells @60 fps / 22 px cells @30 fps / still-frame), demotion when the p95 over 60 frames exceeds 8 ms, DPR-capped atlas kept under the 4096 px mobile texture limit, pause on hidden tab. Also its ink-drop lifecycle (spread then fade) and the data-inkpond-avoid whitespace system that keeps content legible over the ink — useful for keeping the six cushions readable. MIT.

### jiang4wqy/ink-slash　★ 1
- 地址：https://github.com/jiang4wqy/ink-slash
- 许可证：MIT
- 相关性：Chinese sumi-e game rendered entirely with Canvas 2D and zero image assets: rice-paper texture, tapered brush cuts, dry-brush splatter (飞白迸溅), vermilion combo seals. Same rendering stack as ours, so the drawing code transfers directly.
- 可借鉴：Procedural recipes (TypeScript under src/) for paper grain, a tapered 收锋 stroke, and splatter built as a main blot plus satellite droplets rather than particles; also its 'swept segment' hit-testing between frames, which is the same trick we need to make a drag across the Lu Ban lock feel responsive at 30 fps. MIT; ~150 KB build, no framework.

### steveruizok/perfect-freehand　★ 5,776
- 地址：https://github.com/steveruizok/perfect-freehand
- 许可证：MIT
- 相关性：The de-facto library for turning pointer samples into a filled, pressure-varying stroke outline; exactly what a brush stroke silhouette and the lock-drag interaction need.
- 可借鉴：getStroke(points, {size, thinning, smoothing, streamline, simulatePressure}) returns a polygon you can fill with any renderer. Use it for the calligraphic silhouette (high thinning = slow deliberate strokes with a tapered tail), then mask a paper-noise texture inside the shape with globalCompositeOperation='source-atop' to give the stroke ink body. ESM, no dependencies, works from a CDN without a build step.

### spite/THREE.MeshLine　★ 2.3k
- 地址：https://github.com/spite/THREE.MeshLine
- 许可证：MIT
- 相关性：Renders lines as billboarded triangle strips with width that varies along the line, a texture along the line, partial visibility and advance(); updated for current three.js (r155+, ES modules only). The practical way to get ink contours on 3D geometry and figures.
- 可借鉴：Feed a brush-stroke alpha texture as material.map and vary width along the line so contours thicken and thin like a brush; 'visibility' draws a stroke progressively (figure strokes appearing as the user sits down), advance() moves a trail cheaply. The README itself points to three's Line2/LineMaterial addons if you don't need the texture or variable width.

### airbate/shuimo-liuyun　★ 4
- 地址：https://github.com/airbate/shuimo-liuyun
- 许可证：MIT for the localization (upstream rights unstated)
- 相关性：Single-file WebGL ink-on-wet-paper toy: a Stable Fluids solver plus five traditional Chinese pigments, with a procedural rice-paper texture — the best reference for how a splash actually diffuses and bleeds.
- 可借鉴：Beer–Lambert compositing (paper × exp(−A)) for believable pigment layering across sumi / indigo / vermilion / bamboo / gamboge — the same math gives us six cushion colors that read as pigments rather than flat RGB; half-float ping-pong targets with advection → vorticity → divergence → pressure projection for ink drift; the paper texture is hash grain + fibers + vignette and can be baked and reused in Canvas 2D. Note the license caveat below.

### gl-transitions/gl-transitions　★ 2.2k
- 地址：https://github.com/gl-transitions/gl-transitions
- 许可证：MIT (two transitions BSD, declared per file)
- 相关性：A spec plus 100+ GLSL full-screen transition functions. None is named 'ink', but the contract and the noise-threshold wipe pattern are exactly what an ink-wipe shader needs if the gate/hall is rendered to a render target.
- 可借鉴：Implement vec4 transition(vec2 uv) with u_progress 0..1, ratio, getFromColor/getToColor and return vec4(0.0) where nothing is drawn; build the ink front as a smoothstep on fbm noise so the edge breaks into tendrils, and expose 'wetness' via the // @range(min,max,step) comment convention the loader already parses. Only worth it if we composite a WebGL scene; for a 2D overlay the mask approach below is simpler.

**注意事项**
- The ink-wipe/transition track is genuinely thin. GitHub searches for 'ink wipe', 'ink transition', 'ink dissolve' returned only 0-star unlicensed sketches (e.g. blowupnewyork/splat, a p5 ink-splatter sketch with no license); there is no maintained ink-wipe library. gl-transitions is the only solid source, and it has no ink-named transition — we will write the wipe ourselves (mask in Canvas 2D, or an fbm-threshold shader if the scene is a render target).
- shuimo-liuyun's MIT covers only the English localization; the README says the fluid solver and visual design come from the original site, with no upstream license stated. Read it for the pigment math, do not copy the solver wholesale.
- p5.brush requires p5.js 2.x and a WebGL2 canvas (standalone build is WebGL2-only). Pulling it in would fight our Python-stdlib + Three.js + no-build stack; use it as an algorithm reference (watercolor fill, granulation, hatching, flow fields) instead of a dependency.
- enso-maker (3★), ink-slash (1★) and inkpond (0★) are single-author projects with tiny audiences. They are readable reference code, not battle-tested dependencies — vendor small snippets with attribution rather than adding them to the page.
- DCtheTall/webgl-landscape (sumi-e WebGL shader, 6★, implements a published sumi-e rendering paper) has no license file at all: reference only, no code copying. The GitHub search API was unauthenticated and rate-limited (60 req/hr, 10/min for search) and WebSearch results were noisy, so this list is a sample, not an exhaustive survey; several promising 'ink splash' repos turned out to be 0-star, unlicensed p5 sketches.

## 多智能体会场可视化（agentroom）

**工程要点**
- Split text from bodies: every mature example puts dialogue in DOM/CSS2D and bodies in WebGL. hermes-virtual-office drives speech with CSS2D balloons pinned to 3D heads; ai-town and Smallville use fixed-size canvas sprites for the same job. For Chinese ink captions, CSS2D wins (no font atlas, crisp glyphs at any distance), but CSS2D does not depth-test - so hide labels whose anchor is behind the table or another figure, and set pointer-events:none so scrolls never block seat clicks.
- Preallocate one speech object per seat and only show/hide + reposition it. Smallville creates a single 130x58 speech-bubble image per persona at depth 3 and moves it every frame; ai-town uses one Text node per character. For us: one billboarded scroll plane per cushion, clamped to ~2-3 lines, with an unroll animation (scale.y 0 to 1, or a clipping rectangle) instead of a pop-in, and a tiny "..." ink stroke while the role is composing.
- Drive the whole scene from one speaker-state machine. hermes orders states meeting > A2A call > desk > review > idle, and that single state decides position, animation and balloon visibility. Ours should be gate -> overhead -> seated(listening/speaking) -> closing, with exactly one activeSeat: its scroll opens and its figure darkens to full ink while the other cushions' figures stay at 20-30% opacity. This prevents the classic desync where a balloon, a highlight and a camera move disagree about who is talking.
- Use a round protocol, not free-for-all chat: chair -> per-round statements -> moderator synthesis -> next question. legend-talk's moderator groups claims by idea, names an unexamined angle and poses the next round's question; this gives 会通 its 主讲/问难/总括 rhythm, bounds token cost per round, and gives the visual scene natural beats to animate. Snapshot the chair's focus card with each message so regenerate/retry does not drift.
- Transcript UX details that actually matter in a seated first-person view: autoscroll only if the reader is within ~50px of the bottom, a typing row for the composing role, join/leave notices time-sorted into the same stream, and a distinct style for the user's own lines (`bubble-mine`). Dock it in the lower third with 2-3 line bubbles - a full-height chat app breaks the low seated camera framing.
- Budget the 3D behind the gate. whatsmyagentdoing lazy-loads its 3D assets only when the 3D mode is picked, and hermes keeps idle agents from ever calling a model. Build the hall, cushions and figures only after the Lu Ban lock resolves, keep ink figures as flat billboards/stroke planes rather than skinned meshes, and never run per-frame raycasts against the whole hall - one raycast against 6 cushion proxies is enough for sit/hover.

### a16z-infra/ai-town　★ 10.7k
- 地址：https://github.com/a16z-infra/ai-town
- 许可证：MIT
- 相关性：Deployable Generative-Agents-style town: PixiJS characters in a 2D world plus a React DOM chat overlay for the conversation you are watching. Best reference for the agent-bubble + transcript split.
- 可借鉴：src/components/Messages.tsx is a portable chat-panel contract: per-author `.bubble` / `.bubble-mine` classes, join/leave notices merged into the message list and sorted by timestamp (`nodes.sort((a,b)=>a.time-b.time)`), a typing row, and an autoscroll guard (`scrollHeight - scrollTop - 50 <= clientHeight`) so the log only follows when the reader is already at the bottom. Character.tsx anchors speaking/thinking indicators as Pixi Text at fixed offsets (x=18,y=-10 for the bubble glyph; y=-24 for an emoji), stops the AnimatedSprite when not moving, and draws a translucent rounded-rect highlight for the selected character - directly usable as a 'who holds the floor' marker on a cushion.

### joonspk-research/generative_agents　★ 22.3k
- 地址：https://github.com/joonspk-research/generative_agents
- 许可证：Apache-2.0
- 相关性：Stanford Smallville; the canonical browser simulation of agents on a tile map with per-agent speech bubbles and a Django front end (Phaser 3 in the demo template).
- 可借鉴：environment/frontend_server/templates/demo/main_script.html: every persona gets ONE `speech_bubble` image preallocated at a fixed 130x58 display size, depth 3, repositioned each frame relative to the sprite body; a separate monospace Phaser text object renders `"XX: " + utterance`, and finished exchanges are appended into DOM nodes `#chat__<persona>` as `speaker: text<br>`. The reusable pattern is preallocate-one-bubble-per-seat and show/hide + reposition, never create/destroy a bubble per utterance; plus `camera.startFollow(player)` for a follow-cam.

### JuniorXcoder/hermes-virtual-office　★ 140
- 地址：https://github.com/JuniorXcoder/hermes-virtual-office
- 许可证：MIT
- 相关性：A three.js 3D office where AI employees sit at assigned desks and hold real multi-turn meetings - the closest verified example of agents physically seated in a 3D space with turn-based speech.
- 可借鉴：Render dialogue as CSS2D speech balloons anchored to each avatar's head and synchronized to the active speaker - crisp Chinese text, no font atlas, no canvas texture; this is the single most directly reusable idea for ink-scroll captions. Also: a priority state machine `meeting > A2A > desk > review > idle` that drives both avatar placement and animation (idle agents never call a model), desks carrying monitor + status light + role badge (our 'cushion + role plaque'), meetings that pick a room by division, walls that fade when they obstruct the speaker, and minutes auto-structured as Decisions / Action Items / Identified Risks.

### Charonyuu/whatsmyagentdoing　★ 270
- 地址：https://github.com/Charonyuu/whatsmyagentdoing
- 许可证：MIT
- 相关性：Live office view of many concurrent coding agents, shipped in two modes: a zero-dependency hand-drawn 2D canvas and a three.js isometric office with Kenney models.
- 可借鉴：A status-to-body-language mapping worth copying verbatim: thinking = thought bubble, tool call = typing with code scrolling on the desk monitor, waiting-for-input = stand and wave, done = wander to the pantry/meeting room, plus hover-to-reveal details and a List view grouped into 'Needs you / Working / Finished' with live timers. It also lazy-loads the 3D assets only when the 3D mode is selected - the same trick keeps our hall off the critical path until the Lu Ban lock is solved.

### rockbenben/legend-talk　★ 57
- 地址：https://github.com/rockbenben/legend-talk
- 许可证：MIT
- 相关性：A Chinese-language AI roundtable of 161 historical thinkers - the closest interaction model to 会通: a panel of named roles debating in rounds with an AI moderator between rounds.
- 可借鉴：The round protocol itself: 'each round, every voice argues from its own framework'; the user is chair and chooses how many rounds run before a pause; after each round a separate moderator step groups claims by idea, identifies an unexamined angle, and poses the next round's question. Also a floating participant bar (avatars of selected thinkers, + to add, click to remove, 2-10 seats), an editable focus card that stacks on prior focus and is snapshotted per message so regenerating does not drift, and streaming that can be stopped while keeping partial text. React 19 + antd 6 + Zustand stack - borrow the protocol, not the code.

### erickong/agent-roundtable　★ 9
- 地址：https://github.com/erickong/agent-roundtable
- 许可证：MIT
- 相关性：Tiny multi-expert roundtable served by FastAPI/WebSocket with a static index.html - a WeChat-style group chat UI, i.e. the closest thing to our no-build constraint.
- 可借鉴：Proof that a turn-taking group-chat view needs no framework: one static HTML page, speaker name + bubble per turn over a raw WebSocket, 3-6 experts in structured rounds, then a moderator report. Good skeleton to steal for a vanilla ES-module transcript panel; treat it as a reference implementation only (very low star count, likely lightly maintained).

### XiaoLuoLYG/GOD　★ 1.2k
- 地址：https://github.com/XiaoLuoLYG/GOD
- 许可证：Apache-2.0
- 相关性：'Real-time control room for agent societies': a pixel town map, resident roster with profiles, replay timeline, and a live console for asking or injecting instructions into the running society.
- 可借鉴：The step-based replay model - every simulation step is addressable, with pause / scrub / fast-forward / auto-play over both live and recorded runs - and targeted natural-language injection ('ask one resident, a group, or the whole town, mid-run', read by agents on their next turn). Maps cleanly onto a chair interjecting during a 会通 and onto replaying the debate afterward. React 18 + Vite 6 + FastAPI, so take the state model rather than the UI code.

**注意事项**
- No verified repo renders a first-person seated roundtable around a low table in three.js. All 3D examples found are top-down or isometric offices; the seated camera rig, cushion geometry and "look across the hall" framing are ours to build.
- dandacompany/deskrpg (193 stars) is the best 3D-meeting reference found (three.js GLB office, meeting area, camera follows the speaker, obstructing walls fade, floor control + hand raising), but its license is NOT permissive/SPDX: the page shows NOASSERTION and a custom 'Infrastructure Provider Permission' that forbids managed-service operation. Study the behavior, do not copy code.
- GitHub's unauthenticated search API started returning 403 rate-limit errors after roughly six queries from this IP, so coverage is not exhaustive; star counts were read off repo pages on 2026-10-28 and will drift.
- Chinese-language web search returned almost entirely generic Three.js tutorials and CSDN posts; no Chinese 3D roundtable/会通 project surfaced. Anything Chinese-specific (ink scroll captions, 蒲团 seating) will have to be original.
- Most 3D candidates are Next.js/React (hermes, deskrpg) or React 18 + Vite (GOD). Our prototype is no-build vanilla ES modules with a Python stdlib server - borrow the state machines and anchoring patterns, not the dependencies.
- microsoft/autogen (61.6k, MIT) contains AutoGen Studio, but it is a Gatsby/React workflow and team builder, not a spatial roundtable; it was checked and deliberately excluded. Same for ChatDev 2.0's Vue 'Web Console' (workflow canvas + logs, no seated agents).
- erickong/agent-roundtable has only 9 stars and is likely unmaintained; use it as a reading reference for the raw-WebSocket group-chat skeleton, not as a dependency.
