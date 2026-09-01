"""Rysowanie map jako SVG/HTML."""
import math
import re
from html import escape

TOOLTIP_ASSETS = """
<style>
.tw-tooltip{position:fixed;pointer-events:none;background:#111;color:#eee;padding:6px 10px;
  border-radius:6px;font-family:sans-serif;font-size:12px;z-index:9999;display:none;
  white-space:pre-line;border:1px solid #555;box-shadow:0 2px 10px #0009;max-width:260px;}
circle.tw-hl{stroke:#ff2d55!important;stroke-width:3!important;}
</style>
<div id="tw-tooltip" class="tw-tooltip"></div>
<script>
(function(){
  var tip = document.getElementById('tw-tooltip');
  function pidSelector(pid){ return 'circle[data-pid="' + pid + '"]'; }
  document.addEventListener('mouseover', function(e){
    var t = e.target;
    if (t && t.tagName === 'circle' && t.dataset && t.dataset.pid) {
      document.querySelectorAll(pidSelector(t.dataset.pid)).forEach(function(el){
        el.classList.add('tw-hl');
      });
    }
  });
  document.addEventListener('mouseout', function(e){
    var t = e.target;
    if (t && t.tagName === 'circle' && t.dataset && t.dataset.pid) {
      document.querySelectorAll(pidSelector(t.dataset.pid)).forEach(function(el){
        el.classList.remove('tw-hl');
      });
    }
  });
  document.addEventListener('mousemove', function(e){
    var t = e.target;
    if (t && t.tagName === 'circle' && t.dataset && t.dataset.label) {
      tip.textContent = t.dataset.label;
      tip.style.left = (e.clientX + 14) + 'px';
      tip.style.top = (e.clientY + 14) + 'px';
      tip.style.display = 'block';
    } else {
      tip.style.display = 'none';
    }
  });
})();
</script>
"""


DOWNLOAD_ASSETS = """
<style>
.tw-toolbar{margin:10px 0;display:flex;gap:8px;flex-wrap:wrap;}
.tw-toolbar button{background:#2b6cff;color:#fff;border:none;padding:6px 14px;
  border-radius:4px;cursor:pointer;font-size:13px;font-family:sans-serif;}
.tw-toolbar button:hover{background:#1e54cc;}
</style>
<script>
function twSlug(s){ return (s||'mapa').toLowerCase().replace(/[^a-z0-9]+/g,'_').slice(0,60); }
function twDownloadBlob(content, filename, mime){
  var blob = new Blob([content], {type: mime});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
}
function twDownloadSVG(svgId, filename){
  var svg = document.getElementById(svgId);
  if (!svg) return;
  var data = new XMLSerializer().serializeToString(svg);
  twDownloadBlob(data, filename, 'image/svg+xml');
}
function twDownloadPNG(svgId, filename, bg){
  var svg = document.getElementById(svgId);
  if (!svg) return;
  var w = parseInt(svg.getAttribute('width'), 10);
  var h = parseInt(svg.getAttribute('height'), 10);
  var data = new XMLSerializer().serializeToString(svg);
  var svgBlob = new Blob([data], {type: 'image/svg+xml;charset=utf-8'});
  var url = URL.createObjectURL(svgBlob);
  var img = new Image();
  img.onload = function(){
    var canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = bg || '#0e0e0e';
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);
    URL.revokeObjectURL(url);
    canvas.toBlob(function(blob){
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
    }, 'image/png');
  };
  img.src = url;
}
function twDownloadTextArea(taId, filename){
  var ta = document.getElementById(taId);
  if (!ta) return;
  twDownloadBlob(ta.value, filename, 'text/plain;charset=utf-8');
}
</script>
"""


LINE_ICONS = {"front": "\u2694\ufe0f", "mid": "\u25cf", "back": "\U0001F6E1\ufe0f"}


def render_roster_txt(roster):
    """roster: patrz render_roster. Zwraca prosty tekstowy eksport podzialu
    na czlony (do pobrania jako .txt), np. do wklejenia na forum/discord."""
    lines = []
    for group in roster:
        lines.append(f"=== {group['name']} - {len(group['members'])} graczy ===")
        leaders = group.get("leaders") or []
        if leaders:
            lines.append(f"Rada: {', '.join(leaders)}")
        for nick, points, is_council, tier in group["members"]:
            tag = " [RADA]" if is_council else ""
            tier_txt = f" ({tier})" if tier else ""
            lines.append(f"{nick} - {points} pkt{tier_txt}{tag}")
        lines.append("")
    return "\n".join(lines)


def render_roster(roster):
    """roster: lista {color, name, leaders:[nick,...], lines:{tier:count}|None,
    members:[(nick, punkty, is_council, tier|None), ...]} - zwraca HTML z lista
    nickow pogrupowana wg czlonu (liderzy rady i linia front/srodek/zaplecze
    wyroznione), do wyswietlenia obok mapy."""
    cols = []
    for group in roster:
        items = "".join(
            f'<li class="{"tw-roster-leader" if is_council else ""}">'
            f'<span class="tw-roster-nick">{"\U0001F451 " if is_council else ""}'
            f'{LINE_ICONS.get(tier, "") + " " if tier else ""}'
            f'{escape(nick)}</span> '
            f'<span class="tw-roster-pts">{points}</span></li>'
            for nick, points, is_council, tier in group["members"]
        )
        leaders = group.get("leaders") or []
        leaders_html = (
            f'<div class="tw-roster-leaders">\U0001F451 Rada: {escape(", ".join(leaders))}</div>'
            if leaders else
            '<div class="tw-roster-leaders tw-roster-noleader">\u26a0 brak lidera rady!</div>'
        )
        lines_html = ""
        if group.get("lines"):
            parts = [f'{LINE_ICONS.get(t, "")} {t}: {group["lines"].get(t, 0)}'
                    for t in ("front", "mid", "back")]
            lines_html = f'<div class="tw-roster-lines">{" &nbsp; ".join(parts)}</div>'
        cols.append(
            f'<div class="tw-roster-col">'
            f'<h4 style="border-color:{group["color"]}"><span class="tw-roster-dot" '
            f'style="background:{group["color"]}"></span>{escape(group["name"])} '
            f'({len(group["members"])})</h4>'
            f'{leaders_html}{lines_html}'
            f'<ul>{items}</ul></div>'
        )
    return (
        '<style>'
        '.tw-roster{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;text-align:left;}'
        '.tw-roster-col{background:#1a1a1a;border-radius:8px;padding:10px 14px;min-width:180px;'
        'max-height:480px;overflow-y:auto;}'
        '.tw-roster-col h4{margin:0 0 6px;padding-bottom:6px;border-bottom:2px solid;'
        'font-family:sans-serif;font-size:14px;color:#eee;}'
        '.tw-roster-dot{display:inline-block;width:10px;height:10px;border-radius:50%;'
        'margin-right:6px;}'
        '.tw-roster-leaders{font-family:sans-serif;font-size:11px;color:#ffd91a;margin-bottom:4px;}'
        '.tw-roster-noleader{color:#ff6666;}'
        '.tw-roster-lines{font-family:sans-serif;font-size:11px;color:#9cf;margin-bottom:6px;}'
        '.tw-roster-col ul{list-style:none;margin:0;padding:0;font-family:sans-serif;font-size:12px;}'
        '.tw-roster-col li{display:flex;justify-content:space-between;gap:8px;padding:2px 0;'
        'color:#ccc;border-bottom:1px solid #2a2a2a;}'
        '.tw-roster-leader{color:#ffd91a;font-weight:bold;}'
        '.tw-roster-pts{color:#888;}'
        '</style>'
        f'<div class="tw-toolbar">'
        f'<button onclick="twDownloadTextArea(\'tw-roster-txt\',\'grupy.txt\')">'
        f'\U0001F4E5 Pobierz liste graczy (.txt)</button></div>'
        f'<textarea id="tw-roster-txt" style="display:none">{escape(render_roster_txt(roster))}</textarea>'
        f'<div class="tw-roster">{"".join(cols)}</div>'
    )



def _wrap_text(text, width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def render_map(points, title, out_path, legend_items, pad=40, scale=None,
               max_width=1600, max_height=1000, background="#0b2b13",
               show_grid=True, point_radius=None, extra_html="", show_continents=True):
    """points: lista (x, y, color, stroke) lub (x, y, color, stroke, label)
    lub (x, y, color, stroke, label, player_id).
    label (moze byc wieloliniowy, "\\n"-oddzielony) pokazuje sie w tooltipie
    po najechaniu na punkt (JS, bo natywny <title> w SVG jest zawodny/wolny).
    Gdy podany jest player_id, wszystkie wioski tego samego gracza podswietlaja
    sie (czerwona obwodka) po najechaniu na dowolna z nich.
    legend_items: lista (color, label).
    point_radius: opcjonalnie wymusza stala promien kropek zamiast auto-doboru.
    show_continents: rysuje grubsze linie i etykiety K## na granicach
    kontynentow (co 100 pol, tak jak na mapie w Plemiona.pl)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    if scale is None:
        scale = min((max_width - 2 * pad) / span_x, (max_height - 2 * pad) / span_y)
        scale = max(scale, 0.3)

    legend_w = 320 if legend_items else 0
    map_width = int(span_x * scale) + 2 * pad
    height = int(span_y * scale) + 2 * pad
    width = map_width + legend_w

    def tx(x):
        return pad + (x - min_x) * scale

    def ty(y):
        return pad + (y - min_y) * scale

    svg = [
        f'<svg id="tw-map-svg" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#0e0e0e"/>',
        f'<rect x="0" y="0" width="{map_width}" height="{height}" fill="{background}"/>',
    ]

    if show_grid:
        grid_step = max(round(span_x / 20 / 10) * 10, 10)
        gx = math.floor(min_x / grid_step) * grid_step
        while gx <= max_x + grid_step:
            svg.append(f'<line x1="{tx(gx):.1f}" y1="0" x2="{tx(gx):.1f}" y2="{height}" '
                       f'stroke="#134a1f" stroke-width="1"/>')
            gx += grid_step
        gy = math.floor(min_y / grid_step) * grid_step
        while gy <= max_y + grid_step:
            svg.append(f'<line x1="0" y1="{ty(gy):.1f}" x2="{map_width}" y2="{ty(gy):.1f}" '
                       f'stroke="#134a1f" stroke-width="1"/>')
            gy += grid_step

    if show_continents:
        cont_step = 100
        cx0 = math.floor(min_x / cont_step) * cont_step
        while cx0 <= max_x + cont_step:
            svg.append(f'<line x1="{tx(cx0):.1f}" y1="0" x2="{tx(cx0):.1f}" y2="{height}" '
                       f'stroke="#e0a030" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.8"/>')
            cx0 += cont_step
        cy0 = math.floor(min_y / cont_step) * cont_step
        while cy0 <= max_y + cont_step:
            svg.append(f'<line x1="0" y1="{ty(cy0):.1f}" x2="{map_width}" y2="{ty(cy0):.1f}" '
                       f'stroke="#e0a030" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.8"/>')
            cy0 += cont_step

        cy = math.floor(min_y / cont_step) * cont_step
        while cy < max_y + cont_step:
            cx = math.floor(min_x / cont_step) * cont_step
            while cx < max_x + cont_step:
                cont_num = (int(cy) // 100) * 10 + (int(cx) // 100)
                # etykieta w widocznym rogu przeciecia kontynentu z przycietym widokiem
                lx = tx(max(cx, min_x)) + 4
                ly = ty(max(cy, min_y)) + 14
                if -20 < lx < map_width and -20 < ly < height:
                    svg.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#e0a030" '
                               f'font-size="12" font-family="sans-serif" font-weight="bold" '
                               f'opacity="0.85">K{cont_num:02d}</text>')
                cx += cont_step
            cy += cont_step

    if point_radius is not None:
        r = point_radius
    else:
        r = 6 if len(points) < 400 else (2.5 if len(points) < 3000 else 1.6)

    for point in points:
        x, y, color, stroke = point[0], point[1], point[2], point[3]
        label = point[4] if len(point) > 4 else None
        player_id = point[5] if len(point) > 5 else None
        cx, cy = tx(x), ty(y)
        # bez <title> - natywny tooltip przegladarki nakladalby sie na tw-tooltip z JS
        data_attrs = f' data-label="{escape(label)}"' if label else ""
        if player_id is not None:
            data_attrs += f' data-pid="{player_id}"'
        svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" '
                   f'stroke="{stroke}" stroke-width="{0.6 if r < 3 else 1}"{data_attrs}/>')

    if legend_items:
        legend_x = map_width + 20
        title_lines = _wrap_text(title, 34)
        legend_y = 24 + 16 * len(title_lines)
        row_h = 20 if len(legend_items) > 25 else 24
        box_h = min(height - 20, legend_y + row_h * (len(legend_items) + 1))
        svg.append(f'<rect x="{legend_x - 10}" y="4" width="{legend_w - 20}" '
                   f'height="{box_h}" fill="#1a1a1a" stroke="#ffffff22"/>')
        for li, line in enumerate(title_lines):
            svg.append(f'<text x="{legend_x}" y="{22 + 16 * li}" fill="#fff" font-size="13" '
                       f'font-family="sans-serif" font-weight="bold">{escape(line)}</text>')
        for i, (color, label) in enumerate(legend_items):
            cy = legend_y + row_h * (i + 1)
            if cy > 4 + box_h - 10:
                svg.append(f'<text x="{legend_x}" y="{cy}" fill="#999" font-size="11" '
                           f'font-family="sans-serif">... (+{len(legend_items) - i} wiecej)</text>')
                break
            svg.append(f'<circle cx="{legend_x + 6}" cy="{cy - 4}" r="6" fill="{color}" '
                       f'stroke="#000" stroke-width="1"/>')
            svg.append(f'<text x="{legend_x + 20}" y="{cy}" fill="#eee" font-size="12" '
                       f'font-family="sans-serif">{escape(label)}</text>')

    svg.append("</svg>")
    svg_str = "\n".join(svg)

    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:60] or "mapa"
    toolbar = (
        f'<div class="tw-toolbar">'
        f'<button onclick="twDownloadPNG(\'tw-map-svg\',\'{slug}.png\',\'{background}\')">'
        f'\U0001F4E5 Pobierz PNG</button>'
        f'<button onclick="twDownloadSVG(\'tw-map-svg\',\'{slug}.svg\')">'
        f'\U0001F4E5 Pobierz SVG</button></div>'
    )

    if out_path is None:
        return svg_str + toolbar + extra_html + TOOLTIP_ASSETS + DOWNLOAD_ASSETS
    if out_path.endswith(".svg"):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg_str)
    else:
        html = (f'<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">'
                f'<title>{escape(title)}</title>'
                f'<style>body{{background:#111;color:#eee;font-family:sans-serif;'
                f'text-align:center}}</style></head><body><h2>{escape(title)}</h2>'
                f'{svg_str}{toolbar}{extra_html}{TOOLTIP_ASSETS}{DOWNLOAD_ASSETS}</body></html>')
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
    return out_path
