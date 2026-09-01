#!/usr/bin/env python3
"""
mapgen.cli - wielofunkcyjne narzedzie do mapy Plemiona.pl (Tribal Wars).

Funkcje:
  fetch        - pobiera i buforuje dane swiata (ally/player/village.txt)
  families     - wykrywa "rodziny" plemion (te same tagi/nazwy w wariantach)
                 i listuje je
  map --mode family  - rysuje mape calego swiata, kazda rodzina plemion
                        w innym kolorze
  map --mode split   - dzieli wskazanych graczy (po ID sojuszy lub nazwie
                        rodziny) na K zwartych grup <= max-per-group graczy
                        i rysuje wynik (np. do rozdzielenia jednego
                        plemienia na czlony)

Przyklady:
  uv run mapgen fetch --world pl232
  uv run mapgen families --world pl232
  uv run mapgen map --world pl232 --mode family --out family_map.html
  uv run mapgen map --world pl232 --mode split --family Galowie \
      --k 4 --max-per-group 50 --out split_map.html
"""
import argparse
import json
import os

from .builders import build_family_map, build_split_map
from .clustering import SPLIT_METHODS
from .data import fetch_world, load_allies, world_dir
from .families import detect_families, solo_allies
from .render import render_map, render_roster


def cmd_fetch(args):
    fetch_world(args.world, refresh=args.refresh)
    print(f"Dane zapisane w {world_dir(args.world)}")


def cmd_families(args):
    fetch_world(args.world)
    allies = load_allies(args.world)
    exclude_ally_ids = {int(x) for x in (args.exclude or "").split(",") if x.strip()}
    families = detect_families(allies, min_size=args.min_size, exclude_ally_ids=exclude_ally_ids)
    print(f"Wykryto {len(families)} rodzin (>= {args.min_size} plemion):\n")
    for f in families:
        tags = ", ".join(f["tags"])
        ids = ", ".join(str(i) for i in f["ally_ids"])
        print(f"- {f['name']}  [{tags}]  razem {f['total_members']} graczy  (ally id: {ids})")
    solo = solo_allies(allies, families)
    print(f"\nPlemiona bez wykrytej rodziny: {len(solo)}")

    with open(os.path.join(world_dir(args.world), "families.json"), "w", encoding="utf-8") as f:
        json.dump(families, f, ensure_ascii=False, indent=2)


def cmd_map(args):
    fetch_world(args.world)
    exclude_ally_ids = {int(x) for x in (args.exclude or "").split(",") if x.strip()}

    if args.mode == "family":
        points, legend_items, title, stats = build_family_map(
            args.world, args.min_size, exclude_ally_ids=exclude_ally_ids)
        out = render_map(points, title, args.out, legend_items,
                         max_width=1800, max_height=1400, show_grid=not args.no_grid,
                         point_radius=args.point_radius, show_continents=not args.no_continents)
        print(f"Zapisano {out}")
        print(f"Rodzin: {len(stats['families'])}, pominietych "
              f"(samotne plemiona/barbarzynskie/bez sojuszu): {stats['villages_skipped']} wiosek")
        return

    if not args.family and not args.allies:
        raise SystemExit("Podaj --family NAZWA lub --allies id1,id2,...")
    council_text = args.council or ""
    if args.council_file:
        with open(args.council_file, encoding="utf-8") as f:
            council_text += "\n" + f.read()
    try:
        points, legend_items, title, stats = build_split_map(
            args.world, family=args.family, allies_str=args.allies,
            k=args.k, max_per_group=args.max_per_group, exclude_ally_ids=exclude_ally_ids,
            force_auto_colors=args.auto_colors, method=args.method, council_text=council_text,
            balance_lines_flag=args.balance_lines)
    except ValueError as e:
        raise SystemExit(str(e))

    print(f"Graczy w '{stats['label']}': {stats['total_players']}")
    roster_html = render_roster(stats["roster"])
    out = render_map(points, title, args.out, legend_items,
                     show_grid=not args.no_grid, point_radius=args.point_radius,
                     show_continents=not args.no_continents, extra_html=roster_html)
    print(f"Zapisano {out}")
    for name, count in stats["counts"].items():
        print(f"  Czlon ({name}): {count} graczy")
    print(f"Trudne przypadki / mozliwe enklawy: {len(stats['flagged'])}")
    for name, group_name in stats["flagged"]:
        print(f"  - {name} -> {group_name}")
    if council_text.strip():
        if stats["council_not_found"]:
            print(f"Nie znaleziono w rodzinie nickow/ID rady: {', '.join(stats['council_not_found'])}")
        if stats["council_moved"]:
            print(f"Przeniesiono dla pokrycia rady: {', '.join(stats['council_moved'])}")
        if stats["council_missing_groups"]:
            print(f"UWAGA: czlony bez lidera rady: {stats['council_missing_groups']}")
    if args.balance_lines:
        for g in stats["roster"]:
            lines = g["lines"] or {}
            print(f"  {g['name']}: front={lines.get('front',0)} mid={lines.get('mid',0)} "
                  f"back={lines.get('back',0)}")


def build_parser():
    p = argparse.ArgumentParser(description="Wielofunkcyjne narzedzie mapy Plemiona.pl")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("fetch", help="pobierz dane swiata")
    pf.add_argument("--world", required=True, help="np. pl232")
    pf.add_argument("--refresh", action="store_true", help="wymus ponowne pobranie")
    pf.set_defaults(func=cmd_fetch)

    pfam = sub.add_parser("families", help="wykryj rodziny plemion")
    pfam.add_argument("--world", required=True)
    pfam.add_argument("--min-size", type=int, default=2)
    pfam.add_argument("--exclude", help="ID sojuszy do wykluczenia z rodzin, po przecinku")
    pfam.set_defaults(func=cmd_families)

    pm = sub.add_parser("map", help="wygeneruj mape SVG/HTML")
    pm.add_argument("--world", required=True)
    pm.add_argument("--mode", choices=["family", "split"], required=True)
    pm.add_argument("--min-size", type=int, default=2, help="[family] min. plemion w rodzinie")
    pm.add_argument("--family", help="[split] nazwa rodziny (fragment, np. Galowie)")
    pm.add_argument("--allies", help="[split] lista ID sojuszy oddzielona przecinkami")
    pm.add_argument("--k", type=int, default=4, help="[split] liczba czlonow")
    pm.add_argument("--max-per-group", type=int, default=50, help="[split] limit graczy/czlon")
    pm.add_argument("--method", choices=list(SPLIT_METHODS), default="kdtree",
                    help="[split] algorytm podzialu: " +
                         "; ".join(f"{k}={v}" for k, v in SPLIT_METHODS.items()))
    pm.add_argument("--exclude", help="ID sojuszy do wykluczenia (np. podszywajace sie plemie), po przecinku")
    pm.add_argument("--council",
                    help="[split] lista rady/liderow - markdown linki z ID gracza (np. z gry), "
                         "gole ID lub nicki po przecinku/nowej linii - kazdy czlon dostanie >=1")
    pm.add_argument("--council-file", help="[split] plik z wklejona lista rady (jak --council)")
    pm.add_argument("--balance-lines", action="store_true",
                    help="[split] analizuje pobliskie obce plemiona i wyrownuje udzial "
                         "pierwszej linii/srodka/zaplecza w kazdym czlonie")
    pm.add_argument("--auto-colors", action="store_true",
                    help="[split] uzyj automatycznej palety zamiast stalych 4 kolorow")
    pm.add_argument("--no-grid", action="store_true", help="nie rysuj siatki")
    pm.add_argument("--no-continents", action="store_true",
                    help="nie rysuj granic i etykiet kontynentow (K##)")
    pm.add_argument("--point-radius", type=float, help="wymus stala promien kropek")
    pm.add_argument("--out", default="map.html")
    pm.set_defaults(func=cmd_map)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
