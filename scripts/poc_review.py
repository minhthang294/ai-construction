#!/usr/bin/env python3
"""Build a local HTML review sheet from page-extraction POC manifests."""

from __future__ import annotations

import argparse
import base64
import html
import json
from io import BytesIO
from pathlib import Path

from PIL import Image


def _thumb(path: Path, width: int = 1000) -> str:
    if not path.is_file():
        return ""
    try:
        image = Image.open(path)
        ratio = width / max(1, image.width)
        image = image.resize((width, max(1, int(image.height * ratio))))
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=78, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return ""


def _json(path: str | None) -> dict:
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text())
    except Exception:  # noqa: BLE001
        return {}


def _page(run: dict, entry: dict) -> str:
    data = _json(entry.get("result"))
    image = _thumb(Path(entry.get("image", "")))
    values = data.get("key_values") or []
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td class='quote'>{}</td></tr>".format(
            html.escape(str(item.get("name", ""))),
            html.escape(str(item.get("value", ""))),
            html.escape(str(item.get("unit") or "")),
            html.escape(str(item.get("quote", ""))),
        )
        for item in values
        if isinstance(item, dict)
    )
    warnings = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in (data.get("warnings") or [])
    )
    ocr = entry.get("ocr") or {}
    model = entry.get("model") or {}
    return f"""
    <section class="page">
      <div class="meta">
        <h2>Trang {entry.get('page')} · {html.escape(str(entry.get('status')))}</h2>
        <p><b>Loại:</b> {html.escape(str(data.get('page_type') or entry.get('page_type') or ''))}
           · <b>Model conf:</b> {html.escape(str(data.get('confidence') or entry.get('confidence') or ''))}
           · <b>KV:</b> {len(values)} · <b>Warnings:</b> {len(data.get('warnings') or [])}
           · <b>Tiles:</b> {entry.get('tile_count', 0)}</p>
        <p><b>Title:</b> {html.escape(str(data.get('title') or ''))}
           · <b>Drawing:</b> {html.escape(str(data.get('drawing_number') or ''))}
           · <b>Rev:</b> {html.escape(str(data.get('revision') or ''))}</p>
        <p><b>OCR:</b> {ocr.get('words', '?')} từ · conf {ocr.get('mean_confidence', '?')}
           · {ocr.get('seconds', '?')} s · <b>Model:</b> {model.get('seconds', '?')} s
           · tokens {json.dumps(model.get('tokens', {}), ensure_ascii=False)}</p>
      </div>
      <div class="body">
        <div class="image">{f'<img src="{image}" />' if image else '<em>no image</em>'}</div>
        <div class="data">
          <h3>Key values</h3>
          <table><thead><tr><th>Tên</th><th>Giá trị</th><th>Đơn vị</th><th>Quote</th></tr></thead>
          <tbody>{rows or '<tr><td colspan="4">Không có</td></tr>'}</tbody></table>
          <h3>Warnings</h3>
          <ul>{warnings or '<li>Không có</li>'}</ul>
        </div>
      </div>
    </section>
    """


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True, type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sections = []
    for run_dir in args.runs:
        manifest = json.loads((run_dir / "manifest.json").read_text())
        pages = manifest.get("pages") or []
        sections.append(
            f"<h1>{html.escape(run_dir.name)}</h1>"
            f"<p>{html.escape(str(manifest.get('pdf')))} · mode {html.escape(str(manifest.get('mode')))}"
            f" · model {html.escape(str(manifest.get('model')))}</p>"
            + "".join(_page(manifest, page) for page in pages)
        )
    doc = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>POC page extraction review</title>
<style>
body{{font-family:system-ui,sans-serif;margin:20px;background:#f7f7f7;color:#222}}
.page{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px;margin:18px 0}}
.meta p{{margin:4px 0;font-size:13px}}
.body{{display:grid;grid-template-columns:minmax(320px,1fr) minmax(360px,1fr);gap:16px;align-items:start}}
.image img{{max-width:100%;border:1px solid #ccc;border-radius:6px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{border:1px solid #ddd;padding:4px;vertical-align:top;text-align:left}}
th{{background:#eee}} .quote{{color:#555;max-width:360px;word-break:break-word}}
ul{{font-size:12px}} h3{{margin:12px 0 4px;font-size:13px}}
@media(max-width:900px){{.body{{grid-template-columns:1fr}}}}
</style></head><body><h1>POC DeepSeek page extraction</h1>{''.join(sections)}</body></html>"""
    args.out.write_text(doc)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
