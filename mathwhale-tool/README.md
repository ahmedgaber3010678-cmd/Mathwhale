# mathwhale-tool

Turns photographed textbook pages into a branded, redesigned PDF lesson,
matching the "IN MATHS / MATH WHALE" template.

## Setup (GitHub Codespaces)

1. Open this repo in a Codespace (green "Code" button -> Codespaces tab ->
   "Create codespace on main").
2. `pip install -r requirements.txt`
3. Put your two font files and the template PDF in `assets/`:
   - `assets/fonts/GHAITHSANS-BLACK.OTF`
   - `assets/fonts/INKFREE.TTF`
   - `assets/template_pdf.pdf`

## Workflow for a new lesson

1. **Upload the source photos** into `uploads/` (one file per printed page).

2. **Find and crop every diagram:**
   ```
   python scripts/crop_diagrams.py contact uploads/page1.jpg
   ```
   This saves `contact_page1.png` — open it, note the blue numbered boxes
   around each diagram/paragraph you care about.
   ```
   python scripts/crop_diagrams.py extract uploads/page1.jpg 3=p149_learn1 7=p149_example1
   ```
   Saves `assets/diagrams/p149_learn1.png` and `..._example1.png`, already
   watermark-cleaned and background-transparent.

   If a diagram gets merged with nearby text in the auto-detection, use
   `tight_crop()` from Python directly with a rough box you eyeball instead
   — see the docstring in `scripts/crop_diagrams.py`.

3. **Write the content HTML.** Copy `content/example_lesson.html` as a
   starting point — it demonstrates every reusable class (callouts, pills,
   MCQ items, essay items, fractions, two-column grids, figures). Transcribe
   the lesson text, and reference each cropped diagram by its saved path.

   Diagram sizing: don't fight it with CSS. Each `<img>` displays at its
   natural size scaled from the source photo (595.5pt page width ÷ 1656px
   source photo width ≈ 0.36 pt/px is the scale this project's photos use —
   recalculate if your photos are a different resolution). This keeps every
   diagram's *relative* size exactly as it was in the original book, which
   is what actually reads as "consistent" — forcing a uniform box height
   instead distorts wide diagrams vs. narrow ones and looks worse, not better.

4. **Render and merge:**
   ```
   python scripts/render_pdf.py content/lesson.html output/lesson.pdf
   ```

5. Check the output page by page before sending it anywhere. Diagram
   correctness in particular is worth a real look, not a skim — see the
   comments in `render_pdf.py` for two rendering bugs that are easy to
   reintroduce if the CSS or merge step changes.

## Known gotchas (already worked around in this codebase)

- **WeasyPrint flexbox bug**: a percentage-width flex child can silently
  collapse to 100% width depending on unrelated CSS rule order elsewhere in
  the stylesheet. `style.css` uses `inline-block` + `font-size:0` for every
  multi-column grid specifically to avoid this — don't switch those back to
  `display:flex`.
- **pikepdf template scaling**: always pass an explicit `rect` to
  `add_underlay()` (see `render_pdf.py`) or the template frame silently
  stretches by a fraction of a percent and logos drift out of position.
