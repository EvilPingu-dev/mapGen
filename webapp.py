#!/usr/bin/env python3
"""
webapp.py - prosty interfejs webowy (Flask) do mapgen.

Uruchomienie:
  uv run mapgen-web
  (albo: uv run flask --app webapp run --debug)

Otwiera formularz na http://127.0.0.1:5000/ do generowania:
  - mapy rodzin plemion na calym swiecie
  - podzialu wybranej rodziny/sojuszy na K zwartych czlonow

Kazda kropka na mapie ma tooltip (najechanie mysza) z nickiem gracza.
"""
from flask import Flask, render_template_string, request

from mapgen.builders import build_family_map, build_split_map
from mapgen.clustering import SPLIT_METHODS
from mapgen.data import fetch_world
from mapgen.render import render_map, render_roster

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Mapa Plemiona.pl</title>
<style>
  body { background:#111; color:#eee; font-family:sans-serif; margin:0; padding:20px; }
  h1 { margin-top:0; }
  form { background:#1a1a1a; padding:16px; border-radius:8px; margin-bottom:20px; }
  fieldset { border:1px solid #333; border-radius:6px; margin-bottom:10px; }
  legend { padding:0 6px; }
  label { display:inline-block; min-width:150px; }
  input, select { background:#222; color:#eee; border:1px solid #444; padding:5px; border-radius:4px; }
  textarea { background:#222; color:#eee; border:1px solid #444; padding:5px; border-radius:4px;
             width:100%; max-width:400px; font-family:sans-serif; }
  button { background:#2b6cff; color:#fff; border:none; padding:8px 18px; border-radius:4px;
           cursor:pointer; font-size:14px; }
  button:hover { background:#1e54cc; }
  .row { margin:8px 0; }
  .error { background:#3a1414; border:1px solid #a33; padding:10px; border-radius:6px; }
  .result { margin-top:20px; }
  .stats { background:#1a1a1a; padding:12px; border-radius:8px; margin-top:12px; }
  code { color:#9cf; }
</style>
</head>
<body>
<h1>Mapa Plemiona.pl / Tribal Wars</h1>
<form method="post">
  <div class="row">
    <label for="world">Swiat (np. pl232):</label>
    <input type="text" name="world" id="world" value="{{ world }}" required>
  </div>

  <fieldset>
    <legend>Tryb</legend>
    <label><input type="radio" name="mode" value="family" {{ 'checked' if mode=='family' else '' }}> Mapa rodzin (caly swiat)</label>
    &nbsp;&nbsp;
    <label><input type="radio" name="mode" value="split" {{ 'checked' if mode=='split' else '' }}> Podzial na czlony</label>
  </fieldset>

  <fieldset>
    <legend>Opcje trybu "split"</legend>
    <div class="row">
      <label for="family">Nazwa rodziny (fragment):</label>
      <input type="text" name="family" id="family" value="{{ family }}" placeholder="np. Galowie">
    </div>
    <div class="row">
      <label for="allies">... lub ID sojuszy (po przecinku):</label>
      <input type="text" name="allies" id="allies" value="{{ allies }}" placeholder="np. 102,108,122,132">
    </div>
    <div class="row">
      <label for="k">Liczba czlonow (K):</label>
      <input type="number" name="k" id="k" value="{{ k }}" min="2" max="12">
    </div>
    <div class="row">
      <label for="max_per_group">Limit graczy / czlon:</label>
      <input type="number" name="max_per_group" id="max_per_group" value="{{ max_per_group }}" min="1">
    </div>
    <div class="row">
      <label for="method">Algorytm podzialu:</label>
      <select name="method" id="method">
        {% for key, desc in split_methods.items() %}
        <option value="{{ key }}" {{ 'selected' if method==key else '' }}>{{ desc }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="row">
      <label for="color_mode">Kolory:</label>
      <select name="color_mode" id="color_mode">
        <option value="fixed4" {{ 'selected' if color_mode=='fixed4' else '' }}>Stale 4 (niebieski/zielony/bialy/zolty)</option>
        <option value="auto" {{ 'selected' if color_mode=='auto' else '' }}>Automatyczna paleta (dowolne K)</option>
      </select>
    </div>
    <div class="row">
      <label for="balance_lines"><input type="checkbox" name="balance_lines" id="balance_lines" {{ 'checked' if balance_lines else '' }} style="width:auto"> Zbalansuj front/srodek/zaplecze</label>
      <div style="font-size:11px;color:#999;margin-top:2px;margin-left:150px">Analizuje pobliskie obce plemiona i dba, zeby kazdy czlon mial rowny udzial graczy blisko wroga (front), w srodku i w zapleczu.</div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Wyswietlanie</legend>
    <div class="row">
      <label for="show_grid"><input type="checkbox" name="show_grid" id="show_grid" {{ 'checked' if show_grid else '' }} style="width:auto"> Pokaz siatke</label>
    </div>
    <div class="row">
      <label for="show_continents"><input type="checkbox" name="show_continents" id="show_continents" {{ 'checked' if show_continents else '' }} style="width:auto"> Pokaz granice kontynentow (K##)</label>
    </div>
    <div class="row">
      <label for="point_radius">Rozmiar kropek (px, puste = auto):</label>
      <input type="number" name="point_radius" id="point_radius" value="{{ point_radius }}" min="1" max="20" step="0.5" style="width:80px">
    </div>
  </fieldset>

  <div class="row">
    <label for="exclude">Wyklucz ID sojuszy (podszywajace sie plemiona itp.):</label>
    <input type="text" name="exclude" id="exclude" value="{{ exclude }}" placeholder="np. 146">
  </div>

  <div class="row">
    <label for="council" style="vertical-align:top">Rada / liderzy:</label>
    <textarea name="council" id="council" rows="6" placeholder="Wklej liste rady - dziala nicki (Nick1, Nick2), gole ID graczy, albo cala wklejona lista markdown z linkami do gry, np. [Nick](https://.../info_player&id=12345)">{{ council }}</textarea>
    <div style="font-size:11px;color:#999;margin-top:2px">Kazdy czlon dostanie gwarantowanie co najmniej jednego z nich. Wklejenie linkow z ID gracza jest najpewniejsze (bez pomylek przy podobnych nickach).</div>
  </div>

  <button type="submit">Generuj mape</button>
</form>

{% if error %}
  <div class="error">{{ error }}</div>
{% endif %}

{% if svg %}
  <div class="result">
    {{ svg | safe }}
    {% if roster %}{{ roster | safe }}{% endif %}
    <div class="stats">
      <pre>{{ stats_text }}</pre>
    </div>
  </div>
{% endif %}

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    world = request.form.get("world", "pl232").strip()
    mode = request.form.get("mode", "family")
    family = request.form.get("family", "").strip()
    allies = request.form.get("allies", "").strip()
    k = int(request.form.get("k", 4) or 4)
    max_per_group = int(request.form.get("max_per_group", 50) or 50)
    exclude = request.form.get("exclude", "").strip()
    color_mode = request.form.get("color_mode", "fixed4")
    show_grid = request.form.get("show_grid") == "on" if request.method == "POST" else True
    show_continents = request.form.get("show_continents") == "on" if request.method == "POST" else True
    point_radius_raw = request.form.get("point_radius", "").strip()
    point_radius = float(point_radius_raw) if point_radius_raw else None

    method = request.form.get("method", "kdtree")
    council = request.form.get("council", "").strip()
    balance_lines_flag = request.form.get("balance_lines") == "on" if request.method == "POST" else False
    svg = None
    roster = None
    error = None
    stats_text = ""

    if request.method == "POST":
        try:
            exclude_ally_ids = {int(x) for x in exclude.split(",") if x.strip()}
            fetch_world(world)
            if mode == "family":
                points, legend_items, title, stats = build_family_map(
                    world, exclude_ally_ids=exclude_ally_ids)
                svg = render_map(points, title, None, legend_items,
                                 max_width=1800, max_height=1400,
                                 show_grid=show_grid, point_radius=point_radius,
                                 show_continents=show_continents)
                lines = [f"Wykryto {len(stats['families'])} rodzin, "
                         f"{stats['villages_shown']} wiosek pokazanych, "
                         f"{stats['villages_skipped']} pominietych (bez rodziny/sojuszu)."]
                for f in stats["families"]:
                    lines.append(f"  - {f['name']}: {f['total_members']} graczy "
                                 f"[{', '.join(f['tags'])}]")
                stats_text = "\n".join(lines)
            else:
                points, legend_items, title, stats = build_split_map(
                    world, family=family or None, allies_str=allies or None,
                    k=k, max_per_group=max_per_group, exclude_ally_ids=exclude_ally_ids,
                    force_auto_colors=(color_mode == "auto"), method=method,
                    council_text=council, balance_lines_flag=balance_lines_flag)
                roster = render_roster(stats["roster"])
                svg = render_map(points, title, None, legend_items,
                                 show_grid=show_grid, point_radius=point_radius,
                                 show_continents=show_continents)
                lines = [f"Podzial '{stats['label']}': {stats['total_players']} graczy razem"]
                for name, count in stats["counts"].items():
                    lines.append(f"  - {name}: {count} graczy")
                lines.append(f"Trudne przypadki / mozliwe enklawy: {len(stats['flagged'])}")
                for name, group_name in stats["flagged"]:
                    lines.append(f"  - {name} -> {group_name}")
                if council.strip():
                    if stats["council_not_found"]:
                        lines.append(f"Nie znaleziono nickow/ID rady: {', '.join(stats['council_not_found'])}")
                    if stats["council_moved"]:
                        lines.append(f"Przeniesiono dla pokrycia rady: {', '.join(stats['council_moved'])}")
                    if stats["council_missing_groups"]:
                        lines.append(f"UWAGA: czlony bez lidera rady: {stats['council_missing_groups']}")
                if balance_lines_flag:
                    for g in stats["roster"]:
                        ln = g["lines"] or {}
                        lines.append(f"  {g['name']}: front={ln.get('front',0)} "
                                     f"srodek={ln.get('mid',0)} zaplecze={ln.get('back',0)}")
                stats_text = "\n".join(lines)
        except ValueError as e:
            error = str(e)
        except Exception as e:  # pobieranie danych, zly numer swiata itp.
            error = f"Blad: {e}"

    return render_template_string(
        PAGE, world=world, mode=mode, family=family, allies=allies,
        k=k, max_per_group=max_per_group, exclude=exclude, color_mode=color_mode,
        method=method, split_methods=SPLIT_METHODS, council=council,
        balance_lines=balance_lines_flag,
        show_grid=show_grid, show_continents=show_continents, point_radius=(point_radius_raw or ""),
        svg=svg, roster=roster, error=error, stats_text=stats_text,
    )


def main():
    app.run(debug=True)


if __name__ == "__main__":
    main()
