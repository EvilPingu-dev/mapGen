"""Budowa danych mapy (punkty + legenda + statystyki), uzywana przez CLI i webapp."""
import re
from collections import defaultdict

from .clustering import (
    balance_lines,
    classify_lines,
    ensure_council_coverage,
    nearest_neighbors_purity,
    split_players,
)
from .colors import FIXED_4_COLORS, FIXED_4_ORDER, distinct_colors
from .data import load_allies, load_players, load_villages
from .families import detect_families

LINE_LABELS = {"front": "pierwsza linia", "mid": "srodek", "back": "zaplecze"}
LINE_ICONS = {"front": "\u2694\ufe0f", "mid": "\u25cf", "back": "\U0001F6E1\ufe0f"}


def _compute_group_tiers(player_points, assignment, k):
    """Dla kazdego gracza oblicza tier (front/mid/back) wzgledem
    GLOBALNEGO centroidu calej rodziny (miejsca, gdzie czlony sie spotykaja).
    Sortowanie odbywa sie WEWNATRZ kazdej grupy - porownujemy graczy
    danego czlonu miedzy soba, ale miarą jest odleglosc od wspolnego centrum.
    Efekt: "zaplecze" czlonu = ci gracze, ktorzy sa najblizej centrum calej
    rodziny (gdzie czlony stykaja sie ze soba); "front" = ci najdalej wysunieci
    od centrum, na zewnetrznej krawedzi terytorium czlonu."""
    pids_all = list(player_points.keys())
    global_cx = sum(player_points[pid][0] for pid in pids_all) / len(pids_all)
    global_cy = sum(player_points[pid][1] for pid in pids_all) / len(pids_all)

    tiers = {}
    for gi in range(k):
        members = [pid for pid, g in assignment.items() if g == gi]
        if not members:
            continue
        # dystans od globalnego centrum - malejaco = front
        dists = {pid: (player_points[pid][0] - global_cx) ** 2 +
                       (player_points[pid][1] - global_cy) ** 2
                 for pid in members}
        ordered = sorted(members, key=lambda pid: -dists[pid])
        n = len(ordered)
        for i, pid in enumerate(ordered):
            frac = i / n
            tiers[pid] = "front" if frac < 1 / 3 else ("mid" if frac < 2 / 3 else "back")
    return tiers


def parse_council_input(text):
    """Parsuje wklejona liste rady - obsluguje markdown linki w stylu
    [Nick](https://.../game.php?village=..&screen=info_player&id=NNN)
    (dokladne dopasowanie po ID gracza), gole ID graczy oraz zwykle nicki
    oddzielone przecinkiem lub nowa linia. Zwraca (ids: set[int], names: list[str])."""
    ids = set()
    names = []
    remaining = text or ""
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", remaining):
        label, url = m.group(1), m.group(2)
        id_match = re.search(r"[?&]id=(\d+)", url)
        if id_match:
            ids.add(int(id_match.group(1)))
        else:
            names.append(label.strip())
    remaining = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", " ", remaining)
    for token in re.split(r"[,\n]+", remaining):
        token = token.strip().strip("*# ").strip()
        if not token:
            continue
        if token.isdigit():
            ids.add(int(token))
        else:
            names.append(token)
    return ids, names


def build_family_map(world, min_size=2, exclude_ally_ids=None):
    """Zwraca (points, legend_items, title, stats). points maja etykiete
    hover z nickiem gracza i tagiem plemienia."""
    allies = load_allies(world)
    players = load_players(world)
    villages = load_villages(world)

    families = detect_families(allies, min_size=min_size, exclude_ally_ids=exclude_ally_ids)
    ally_to_family = {}
    for fi, f in enumerate(families):
        for aid in f["ally_ids"]:
            ally_to_family[aid] = fi
    colors = distinct_colors(len(families))

    points = []
    for v in villages:
        p = players.get(v["player_id"])
        if not p or p["ally_id"] == 0:
            continue
        fi = ally_to_family.get(p["ally_id"])
        if fi is None:
            continue  # plemie bez wykrytej rodziny - pomijamy dla czytelnosci
        tag = allies.get(p["ally_id"], {}).get("tag", "")
        label = "\n".join([
            p["name"],
            f"Plemie: {tag} ({families[fi]['name']})",
            f"Punkty: {p['points']}",
            f"Wioski: {p['villages']}",
        ])
        points.append((v["x"], v["y"], colors[fi], "#00000055", label, v["player_id"]))

    order = sorted(range(len(families)), key=lambda i: -families[i]["total_members"])
    legend_items = [(colors[i], f"{families[i]['name']} ({families[i]['total_members']})")
                    for i in order]

    title = f"Rodziny plemion - swiat {world} ({len(families)} rodzin, {len(points)} wiosek)"
    stats = {
        "families": families,
        "villages_shown": len(points),
        "villages_skipped": len(villages) - len(points),
    }
    return points, legend_items, title, stats


def build_split_map(world, family=None, allies_str=None, k=4, max_per_group=50,
                    exclude_ally_ids=None, force_auto_colors=False, method="kdtree",
                    council_text=None, balance_lines_flag=False):
    """Zwraca (points, legend_items, title, stats) albo rzuca ValueError.
    force_auto_colors=True uzyje automatycznej palety zamiast stalych 4
    kolorow (niebieski/zielony/bialy/zolty) nawet gdy k == 4.
    method: patrz mapgen.clustering.SPLIT_METHODS (kdtree/kmeans/sector/strength/grid/growth).
    council_text: wklejona lista rady/liderow - markdown linki z ID gracza
    w URL, gole ID lub zwykle nicki (patrz parse_council_input). Kazdy czlon
    dostanie gwarantowanie >=1 z nich, o ile jest ich wystarczajaco duzo.
    balance_lines_flag: analizuje polozenie "obcych" wiosek wokol i dzieli
    graczy w kazdym czlonie na front/srodek/zaplecze wg bliskosci wroga,
    a nastepnie wyrownuje udzial tych warstw miedzy czlonami."""
    allies = load_allies(world)
    players = load_players(world)
    villages = load_villages(world)
    exclude_ally_ids = set(exclude_ally_ids or ())

    if family:
        families = detect_families(allies, min_size=2, exclude_ally_ids=exclude_ally_ids)
        match = next((f for f in families if family.lower() in f["name"].lower()), None)
        if not match:
            raise ValueError(f"Nie znaleziono rodziny pasujacej do '{family}'")
        ally_ids = set(match["ally_ids"])
        label = match["name"]
    elif allies_str:
        ally_ids = {int(x) for x in allies_str.split(",") if x.strip()} - exclude_ally_ids
        label = "/".join(allies[a]["tag"] for a in ally_ids if a in allies)
    else:
        raise ValueError("Podaj family lub allies_str")

    our_player_ids = {pid for pid, p in players.items() if p["ally_id"] in ally_ids}
    our_villages = [v for v in villages if v["player_id"] in our_player_ids]
    if not our_villages:
        raise ValueError(f"Brak wiosek dla '{label}' na swiecie {world}")

    player_villages = defaultdict(list)
    for v in our_villages:
        player_villages[v["player_id"]].append((v["x"], v["y"]))
    player_points = {pid: (sum(c[0] for c in coords) / len(coords),
                           sum(c[1] for c in coords) / len(coords))
                     for pid, coords in player_villages.items()}

    player_strength = {pid: players[pid]["points"] for pid in player_points}
    assignment = split_players(method, player_points, k, max_per_group,
                               player_strength=player_strength)

    tiers = None
    if balance_lines_flag:
        enemy_points = [(v["x"], v["y"]) for v in villages
                       if v["player_id"] != 0 and v["player_id"] not in our_player_ids]
        tiers_global, _exposure = classify_lines(player_points, enemy_points)
        assignment = balance_lines(assignment, player_points, tiers_global, k)

    # Klasyfikacja per-czlon: front/mid/back wzgledem centroidu WLASNEJ grupy
    # (strategicznie wazniejsze - kto jest na skraju SWOJEGO czlonu, nie calej rodziny)
    tiers = _compute_group_tiers(player_points, assignment, k)

    council_ids_input, council_names = parse_council_input(council_text)
    name_to_pid = {players[pid]["name"].lower(): pid for pid in player_points}
    council_pids = set()
    council_not_found = []
    for pid in council_ids_input:
        if pid in player_points:
            council_pids.add(pid)
        else:
            council_not_found.append(f"id:{pid}")
    for name in council_names:
        pid = name_to_pid.get(name.lower())
        if pid is None:
            council_not_found.append(name)
        else:
            council_pids.add(pid)
    council_moved = []
    if council_pids:
        assignment, council_moved = ensure_council_coverage(
            assignment, player_points, council_pids, k)

    flagged = nearest_neighbors_purity(player_points, assignment)

    if k == 4 and not force_auto_colors:
        color_names = FIXED_4_ORDER
        colors = [FIXED_4_COLORS[c] for c in color_names]
    else:
        colors = distinct_colors(k)
        color_names = [f"grupa {i+1}" for i in range(k)]

    counts = defaultdict(int)
    for g in assignment.values():
        counts[g] += 1

    points = []
    for v in our_villages:
        g = assignment.get(v["player_id"])
        if g is None:
            continue
        color = colors[g]
        stroke = "#000000" if color_names[g] == "bialy" else "#00000055"
        p = players[v["player_id"]]
        is_council = v["player_id"] in council_pids
        label_lines = [f"\U0001F451 {p['name']} (RADA)" if is_council else p["name"]]
        label_lines.append(f"Czlon: {color_names[g]}")
        t = tiers[v["player_id"]]
        label_lines.append(f"{LINE_ICONS[t]} {LINE_LABELS[t]}")
        label_lines += [
            f"Punkty: {p['points']}",
            f"Wioski: {p['villages']}",
        ]
        point_label = "\n".join(label_lines)
        points.append((v["x"], v["y"], color, stroke, point_label, v["player_id"]))
    for pid in flagged:
        x, y = player_points[pid]
        p = players[pid]
        flag_label = "\n".join([
            p["name"],
            "Trudny przypadek / mozliwa enklawa",
            f"Czlon: {color_names[assignment[pid]]}",
            f"Punkty: {p['points']}",
            f"Wioski: {p['villages']}",
        ])
        points.append((x, y, "none", "#ff3355", flag_label, pid))

    legend_items = [(colors[i], f"Czlon {i+1} ({color_names[i]}): {counts.get(i,0)} graczy")
                    for i in range(k)]
    title = f"Podzial '{label}' na {k} czlonow - swiat {world} (razem {len(player_points)} graczy) [{method}]"

    roster = []
    for i in range(k):
        member_pids = sorted((pid for pid, g in assignment.items() if g == i),
                             key=lambda pid: -players[pid]["points"])
        line_counts = defaultdict(int)
        for pid in member_pids:
            line_counts[tiers[pid]] += 1
        roster.append({
            "color": colors[i],
            "name": f"Czlon {i+1} ({color_names[i]})",
            "leaders": [players[pid]["name"] for pid in member_pids if pid in council_pids],
            "lines": dict(line_counts),
            "members": [(players[pid]["name"], players[pid]["points"], pid in council_pids,
                        tiers[pid])
                        for pid in member_pids],
        })

    stats = {
        "label": label,
        "total_players": len(player_points),
        "counts": {color_names[i]: counts.get(i, 0) for i in range(k)},
        "flagged": [(players[pid]["name"], color_names[assignment[pid]]) for pid in flagged],
        "roster": roster,
        "council_not_found": council_not_found,
        "council_moved": [players[pid]["name"] for pid in council_moved],
        "council_missing_groups": [
            i + 1 for i in range(k)
            if not any(pid in council_pids for pid, g in assignment.items() if g == i)
        ] if council_pids else [],
    }
    return points, legend_items, title, stats
