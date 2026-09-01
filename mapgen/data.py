"""Wczytywanie i pobieranie danych swiata Plemiona.pl (ally/player/village.txt)."""
import csv
import os
import urllib.parse
import urllib.request

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def world_dir(world):
    d = os.path.join(DATA_ROOT, world)
    os.makedirs(d, exist_ok=True)
    return d


def fetch_world(world, refresh=False):
    d = world_dir(world)
    files = ["ally.txt", "player.txt", "village.txt"]
    for fname in files:
        path = os.path.join(d, fname)
        if refresh or not os.path.exists(path):
            url = f"https://{world}.plemiona.pl/map/{fname}"
            print(f"Pobieram {url} ...")
            urllib.request.urlretrieve(url, path)
    return d


def load_allies(world):
    """id -> {name, tag, members, villages, points, all_points, rank}"""
    path = os.path.join(world_dir(world), "ally.txt")
    allies = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            aid, name, tag, members, villages, points, all_points, rank = row
            allies[int(aid)] = {
                "name": urllib.parse.unquote_plus(name),
                "tag": urllib.parse.unquote_plus(tag),
                "members": int(members),
                "villages": int(villages),
                "points": int(points),
                "rank": int(rank),
            }
    return allies


def load_players(world):
    path = os.path.join(world_dir(world), "player.txt")
    players = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            pid, name, ally_id, villages, points, rank = row
            players[int(pid)] = {
                "name": urllib.parse.unquote_plus(name),
                "ally_id": int(ally_id),
                "villages": int(villages),
                "points": int(points),
            }
    return players


def load_villages(world):
    path = os.path.join(world_dir(world), "village.txt")
    villages = []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            vid, name, x, y, player_id, points, rank = row
            villages.append({
                "id": int(vid),
                "name": urllib.parse.unquote_plus(name),
                "x": int(x),
                "y": int(y),
                "player_id": int(player_id),
                "points": int(points),
            })
    return villages
