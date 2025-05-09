#!/usr/bin/env python3
import sys
import json
import asyncio
import io
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from PIL import Image
from playwright.async_api import async_playwright

def _js_contrast_function():
    return r"""
() => {
  const toRgb = s => {
    const m = s.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    return m ? [ +m[1], +m[2], +m[3] ] : null;
  };
  const lum = c => {
    const v = c/255;
    return v <= 0.03928
      ? v/12.92
      : Math.pow((v + 0.055)/1.055, 2.4);
  };
  const contrastRatio = (f, b) => {
    const L1 = 0.2126*lum(f[0]) + 0.7152*lum(f[1]) + 0.0722*lum(f[2]);
    const L2 = 0.2126*lum(b[0]) + 0.7152*lum(b[1]) + 0.0722*lum(b[2]);
    return (Math.max(L1,L2) + 0.05)/(Math.min(L1,L2) + 0.05);
  };

  const tags = ['p','span','a','h1','h2','h3','h4','h5','h6','li','label','button'];
  return Array.from(document.querySelectorAll(tags.join(','))).map(el => {
    const cs = window.getComputedStyle(el);
    const fg = toRgb(cs.color);
    if (!fg) return null;
    let bg = toRgb(cs.backgroundColor);
    let p = el.parentElement;
    while((!bg || bg.every(c=>c===0)) && p){
      bg = toRgb(window.getComputedStyle(p).backgroundColor);
      p = p.parentElement;
    }
    if (!bg) bg = [255,255,255];
    return {
      role: el.tagName.toLowerCase(),
      fg, bg,
      contrast: contrastRatio(fg,bg)
    };
  }).filter(x => x);
}
"""

async def analyze(url: str, output_path: Path):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width':1920,'height':1080})

        # ── 1) navigate & wait ───────────────────────────────
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(500)

        # ── 2) screenshot → WebP ─────────────────────────────
        png_bytes = await page.screenshot(full_page=True)
        webp_path = output_path.with_suffix('.webp')
        img = Image.open(io.BytesIO(png_bytes))
        img.save(webp_path, 'WEBP')

        # ── 3) inject axe-core ───────────────────────────────
        await page.add_script_tag(
            url='https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js'
        )

        # ── 4) grab HTML + parse with BS4 for semantic ──────
        html = await page.content()
        html_path = output_path.with_suffix('.html')
        html_path.write_text(html, encoding='utf-8')

        soup = BeautifulSoup(html, 'html.parser')

        # semantic: lang + headings
        lang = (soup.html or {}).get('lang', '')
        headings = []
        for lvl in range(1,7):
            for h in soup.find_all(f'h{lvl}'):
                headings.append([lvl, h.get_text(strip=True)])

        # semantic: images + svgs / missing_alt
        images = []
        missing_alt = []

        # 1) all <img> tags
        for idx, img_tag in enumerate(soup.find_all('img')):
            alt = img_tag.get('alt', '').strip()
            node_id = f"img-{idx}"
            images.append({'nodeId': node_id, 'alt': alt})
            if not alt:
                missing_alt.append(node_id)

        # 2) all inline <svg> tags
        for idx, svg_tag in enumerate(soup.find_all('svg')):
            node_id = f"svg-{idx}"
            # svg elements never have alt attributes
            images.append({'nodeId': node_id, 'alt': ''})
            missing_alt.append(node_id)

        # semantic: links / missing_name (unchanged)
        links = []
        missing_name = []
        for idx, a in enumerate(soup.find_all('a')):
            txt = a.get_text(strip=True)
            node_id = str(idx)
            links.append({'nodeId': node_id, 'text': txt})
            if not txt:
                missing_name.append(node_id)

        semantic = {
            'lang': lang,
            'headings': headings,
            'images': images,
            'missing_alt': missing_alt,
            'links': links,
            'missing_name': missing_name
        }

        # ── 5) contrast via injected JS ──────────────────────
        contrast = await page.evaluate(_js_contrast_function())

        # ── 6) image_captioning via getBoundingClientRect() ──
        #     now includes <img> and inline <svg> elements
        image_captioning = await page.evaluate("""
          () => {
            const imgCaps = Array.from(document.images).map((el,i) => {
              const r = el.getBoundingClientRect();
              return {
                nodeId: `img-${i}`,
                alt: el.getAttribute('alt') || '',
                bbox: { x: r.x, y: r.y, width: r.width, height: r.height }
              };
            });
            const svgCaps = Array.from(document.querySelectorAll('svg')).map((el,i) => {
              const r = el.getBoundingClientRect();
              return {
                nodeId: `svg-${i}`,
                alt: '',
                bbox: { x: r.x, y: r.y, width: r.width, height: r.height }
              };
            });
            return imgCaps.concat(svgCaps);
          }
        """)

        # ── 7) axe report, drop passes/incomplete/inapplicable ─
        await page.wait_for_timeout(5000)

        axe_raw = await page.evaluate("""
          async () => {
            const r = await axe.run(document);
            delete r.passes;
            delete r.incomplete;
            delete r.inapplicable;
            return r;
          }
        """)

        await browser.close()

        # ── 8) assemble + write JSON ─────────────────────────
        out = {
            'page_id': url,
            'viewports': [{
                'viewport': '1920-1080',
                'semantic': semantic,
                'contrast': contrast,
                'image_captioning': image_captioning,
                'axe': axe_raw,
                'html_path': str(html_path),
                'screenshot': str(webp_path)
            }]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"✅ JSON  → {output_path}")
    print(f"✅ HTML  → {html_path}")
    print(f"✅ WebP  → {webp_path}")

    def count_violations_nodes(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'violations' and isinstance(value, list):
                    return sum(len(item.get('nodes', [])) for item in value if isinstance(item, dict))
                else:
                    count = count_violations_nodes(value)
                    if count is not None:
                        return count
        elif isinstance(node, list):
            for value in node:
                count = count_violations_nodes(value)
                if count is not None:
                    return count
        return None

    violations_node_count = count_violations_nodes(out)
    print(f"Total number of nodes having violations: {violations_node_count}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage:\n  python analyze_page.py <page-url> <out.json-or-out-dir/>")
        sys.exit(1)

    page_url = sys.argv[1]
    out_arg  = sys.argv[2]
    out_path = Path(out_arg)

    # if it's a directory (or ends with '/'), auto‐name
    if out_arg.endswith('/') or out_path.is_dir():
        out_path.mkdir(parents=True, exist_ok=True)
        u    = urlparse(page_url)
        host = u.netloc.replace(':','-')
        slug = u.path.strip('/').replace('/','-')
        fname = host + (f'-{slug}' if slug else '') + '.json'
        output_file = out_path / fname
    else:
        output_file = out_path
        output_file.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(analyze(page_url, output_file))
