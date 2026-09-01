"""mapgen - wielofunkcyjne narzedzie do mapy Plemiona.pl (Tribal Wars).

Logika podzielona na moduly:
  data        - pobieranie/wczytywanie danych swiata
  families    - wykrywanie rodzin plemion
  clustering  - podzial graczy na K zwartych grup
  colors      - palety kolorow
  render      - rysowanie SVG/HTML
  builders    - laczenie powyzszego w gotowe dane mapy (CLI + webapp)
  cli         - interfejs wiersza polecen
"""
from .builders import build_family_map, build_split_map
from .clustering import SPLIT_METHODS
from .data import fetch_world, load_allies, load_players, load_villages, world_dir
from .families import detect_families, solo_allies
from .render import render_map, render_roster

__all__ = [
    "build_family_map",
    "build_split_map",
    "SPLIT_METHODS",
    "fetch_world",
    "load_allies",
    "load_players",
    "load_villages",
    "world_dir",
    "detect_families",
    "solo_allies",
    "render_map",
    "render_roster",
]
