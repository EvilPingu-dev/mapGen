"""Rozne strategie podzialu graczy na K grup (rozne kompromisy miedzy
zwartoscia geograficzna, frontami i rownowaga sily)."""
import math
import random
from collections import defaultdict


SPLIT_METHODS = {
    "kdtree": "Zwarte kwadranty (kd-tree) - domyslnie, najbardziej zwarte terytoria",
    "kmeans": "K-srodkow - bardziej okragle/organiczne skupiska",
    "sector": "Wycinki kata (fronty) - kazdy czlon to spojny kierunek/front od centrum",
    "strength": "Rownowaga sily - ignoruje geografie, wyrownuje sume punktow miedzy czlonami",
    "grid": "Siatka wierszy/kolumn - regularne, przewidywalne prostokatne dzielnice",
    "growth": "Wzrost od zarodkow (region growing) - organiczne, bardzo zwarte skupiska",
    "cone": "Kierunkowe wycinki/stożki - grupy jako wycinki kata względem wskazanego kierunku/frontu",
    "bar": "Pasy/prowadnice - grupy w postaci równoległych pasów skierowanych ku wskazanemu kierunkowi",
}



def geo_split(player_points, k, max_per_group=None):
    """Alias wstecznie kompatybilny dla kdtree_split."""
    return kdtree_split(player_points, k, max_per_group)


def kdtree_split(player_points, k, max_per_group=None):
    """player_points: dict pid -> (x, y). Zwraca dict pid -> indeks grupy 0..k-1.
    Rekurencyjna bisekcja wzdluz osi o najwiekszym rozrzucie - daje zwarte,
    prostokatne, zrownowazone terytoria."""
    pids = list(player_points.keys())

    def rec(idxs, groups_count):
        if groups_count == 1:
            return [idxs]
        k1 = groups_count // 2
        k2 = groups_count - k1
        n = len(idxs)
        n1 = round(n * k1 / groups_count)
        n1 = max(0, min(n, n1))
        xs = [player_points[pids[i]][0] for i in idxs]
        ys = [player_points[pids[i]][1] for i in idxs]
        axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
        idxs_sorted = sorted(idxs, key=lambda i: player_points[pids[i]][axis])
        left, right = idxs_sorted[:n1], idxs_sorted[n1:]
        return rec(left, k1) + rec(right, k2)

    groups_idx = rec(list(range(len(pids))), k)
    assignment = {}
    for gi, idxs in enumerate(groups_idx):
        for i in idxs:
            assignment[pids[i]] = gi

    if max_per_group:
        assignment = _enforce_capacity(player_points, assignment, k, max_per_group)
    return assignment


def kmeans_split(player_points, k, max_per_group=None, iterations=60, seed=42):
    """Kapacytowany k-means (kmeans++ init + zachlanne przypisanie wg
    odleglosci z limitem miejsc) - daje bardziej okragle/organiczne skupiska
    niz kdtree, kosztem czasem mniej regularnych ksztaltow przy jednym gestym
    rdzeniu graczy."""
    rng = random.Random(seed)
    pids = list(player_points.keys())
    pts = [player_points[pid] for pid in pids]
    n = len(pts)

    def dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    centers = [rng.choice(pts)]
    while len(centers) < k:
        d2 = [min(dist2(p, c) for c in centers) for p in pts]
        total = sum(d2) or 1
        r = rng.uniform(0, total)
        acc = 0
        for p, d in zip(pts, d2):
            acc += d
            if acc >= r:
                centers.append(p)
                break
        else:
            centers.append(pts[-1])

    cap = max_per_group or math.ceil(n / k)
    assignment_list = [-1] * n
    for _ in range(iterations):
        pairs = []
        for i, p in enumerate(pts):
            for gi in range(k):
                pairs.append((dist2(p, centers[gi]), i, gi))
        pairs.sort(key=lambda t: t[0])

        assigned = [False] * n
        cap_left = [cap] * k
        new_assignment = [-1] * n
        remaining = n
        for _, i, gi in pairs:
            if assigned[i] or cap_left[gi] == 0:
                continue
            new_assignment[i] = gi
            assigned[i] = True
            cap_left[gi] -= 1
            remaining -= 1
            if remaining == 0:
                break

        if new_assignment == assignment_list:
            assignment_list = new_assignment
            break
        assignment_list = new_assignment

        sums = [[0.0, 0.0, 0] for _ in range(k)]
        for i, gi in enumerate(assignment_list):
            sums[gi][0] += pts[i][0]
            sums[gi][1] += pts[i][1]
            sums[gi][2] += 1
        for gi in range(k):
            if sums[gi][2] > 0:
                centers[gi] = (sums[gi][0] / sums[gi][2], sums[gi][1] / sums[gi][2])

    assignment = {pids[i]: assignment_list[i] for i in range(n)}
    if max_per_group:
        assignment = _enforce_capacity(player_points, assignment, k, max_per_group)
    return assignment


def sector_split(player_points, k, max_per_group=None):
    """Dzieli graczy na K spojnych wycinkow kata (jak kawalki tortu) wokol
    wspolnego centroidu - kazdy czlon dostaje jeden, spojny kierunek/front
    (np. polnoc, poludniowy-wschod...), co dobrze odwzorowuje mechanike
    frontow w Plemiona.pl."""
    pids = list(player_points.keys())
    cx = sum(p[0] for p in player_points.values()) / len(pids)
    cy = sum(p[1] for p in player_points.values()) / len(pids)

    def angle(pid):
        x, y = player_points[pid]
        return math.atan2(y - cy, x - cx) % (2 * math.pi)

    ordered = sorted(pids, key=angle)
    n = len(ordered)
    assignment = {}
    start = 0
    for gi in range(k):
        remaining_groups = k - gi
        take = round((n - start) / remaining_groups)
        for pid in ordered[start:start + take]:
            assignment[pid] = gi
        start += take

    if max_per_group:
        assignment = _enforce_capacity(player_points, assignment, k, max_per_group)
    return assignment


def grid_split(player_points, k, max_per_group=None):
    """Dzieli obszar na siatke kolumn x wierszy (liczba kolumn ~ sqrt(k)),
    kazda kolumna dostaje proporcjonalna liczbe wierszy tak, by dac lacznie
    K prostokatnych, przewidywalnych dzielnic."""
    pids = list(player_points.keys())
    n = len(pids)
    ncols = max(1, round(math.sqrt(k)))
    # rozdziel k grup na ncols kolumn mozliwie rowno
    rows_per_col = [k // ncols + (1 if i < k % ncols else 0) for i in range(ncols)]

    by_x = sorted(pids, key=lambda pid: player_points[pid][0])
    assignment = {}
    start = 0
    group_idx = 0
    for ci, rows in enumerate(rows_per_col):
        remaining_cols = ncols - ci
        col_size = round((n - start) * rows / sum(rows_per_col[ci:]))
        col_pids = by_x[start:start + col_size]
        start += col_size

        by_y = sorted(col_pids, key=lambda pid: player_points[pid][1])
        row_start = 0
        m = len(by_y)
        for ri in range(rows):
            remaining_rows = rows - ri
            row_size = round((m - row_start) / remaining_rows)
            for pid in by_y[row_start:row_start + row_size]:
                assignment[pid] = group_idx
            row_start += row_size
            group_idx += 1

    if max_per_group:
        assignment = _enforce_capacity(player_points, assignment, k, max_per_group)
    return assignment


def growth_split(player_points, k, max_per_group=None, seed=42):
    """Region growing: wybiera K rozproszonych zarodkow (greedy k-center),
    a nastepnie zachlannie dolacza kolejnych najblizszych graczy do
    najblizszej grupy (jak rosnace plamy) - daje bardzo zwarte, organiczne
    ksztalty, czesto bardziej "biologiczne" niz kdtree/kmeans."""
    rng = random.Random(seed)
    pids = list(player_points.keys())
    n = len(pids)
    cap = max_per_group or math.ceil(n / k)

    def dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    # greedy k-center: pierwszy zarodek losowy, kolejne - najdalsze od juz wybranych
    seeds = [rng.choice(pids)]
    while len(seeds) < k:
        far = max(pids, key=lambda pid: min(
            dist2(player_points[pid], player_points[s]) for s in seeds))
        seeds.append(far)

    assignment = {}
    group_members = defaultdict(list)
    for gi, pid in enumerate(seeds):
        assignment[pid] = gi
        group_members[gi].append(pid)
    unassigned = [pid for pid in pids if pid not in assignment]

    while unassigned:
        best = None
        for pid in unassigned:
            for gi in range(k):
                if len(group_members[gi]) >= cap:
                    continue
                d = min(dist2(player_points[pid], player_points[m]) for m in group_members[gi])
                if best is None or d < best[0]:
                    best = (d, pid, gi)
        if best is None:
            # wszystkie grupy pelne (nie powinno sie zdarzyc, ale na wszelki wypadek)
            for pid in unassigned:
                assignment[pid] = min(range(k), key=lambda gi: len(group_members[gi]))
                group_members[assignment[pid]].append(pid)
            break
        _, pid, gi = best
        assignment[pid] = gi
        group_members[gi].append(pid)
        unassigned.remove(pid)

    return assignment


def strength_balanced_split(player_points, player_strength, k, max_per_group=None):
    """Ignoruje geografie - dzieli graczy tak, aby suma punktow (sily) byla
    mozliwie rowna w kazdym czlonie (klasyczny "snake draft"). Przydatne, gdy
    wazniejsza jest rownowaga militarna miedzy czlonami niz zwartosc mapy."""
    pids = sorted(player_points.keys(), key=lambda pid: -player_strength.get(pid, 0))
    assignment = {}
    counts = defaultdict(int)
    cap = max_per_group or math.ceil(len(pids) / k)
    totals = [0] * k
    for pid in pids:
        candidates = [gi for gi in range(k) if counts[gi] < cap]
        gi = min(candidates, key=lambda g: totals[g])
        assignment[pid] = gi
        counts[gi] += 1
        totals[gi] += player_strength.get(pid, 0)
    return assignment


def split_players(method, player_points, k, max_per_group=None, player_strength=None):
    """Dispatcher: wybiera algorytm podzialu po nazwie (patrz SPLIT_METHODS)."""
    if method == "kmeans":
        return kmeans_split(player_points, k, max_per_group)
    if method == "sector":
        return sector_split(player_points, k, max_per_group)
    if method == "strength":
        return strength_balanced_split(player_points, player_strength or {}, k, max_per_group)
    if method == "grid":
        return grid_split(player_points, k, max_per_group)
    if method == "growth":
        return growth_split(player_points, k, max_per_group)
    return kdtree_split(player_points, k, max_per_group)


LINE_TIERS = ("front", "mid", "back")


def classify_lines(player_points, enemy_points, sample_cap=4000):
    """Klasyfikuje graczy na front/mid/back.

    Metryka: odleglosc od centroidu wlasnego skupiska graczy.
      - Najdalej od centrum = front (zewnetrzna krawedz, wystawiona na wrogow)
      - Blisko centrum     = back  (bezpieczny rdzen skupiska)
    To bezposrednio odpowiada koncentrycznym piercieniom widocznym na mapie:
    wewnetrzny okrag = zaplecze, zewnetrzny = pierwsza linia.
    Jezeli podano enemy_points i sa one nierownomiernie rozlozone (wrogie
    skupisko z jednej strony), wynik jest skalowany: gracze wystawieni w
    strone prawdziwego wroga przesuwaja sie ku frontowi nawet jesli sa blisko
    centroidu (kombinacja obu sygnałów, 70% dystans od centroidu + 30% bliskosc wroga).
    Zwraca (tiers: dict pid->'front'/'mid'/'back', exposure: dict pid->wynik)."""
    pids = list(player_points.keys())
    cx = sum(player_points[pid][0] for pid in pids) / len(pids)
    cy = sum(player_points[pid][1] for pid in pids) / len(pids)

    centroid_dist = {
        pid: (player_points[pid][0] - cx) ** 2 + (player_points[pid][1] - cy) ** 2
        for pid in pids
    }

    if enemy_points:
        if len(enemy_points) > sample_cap:
            enemy_points = random.Random(7).sample(enemy_points, sample_cap)
        enemy_dist = {
            pid: min((player_points[pid][0] - ex) ** 2 + (player_points[pid][1] - ey) ** 2
                     for ex, ey in enemy_points)
            for pid in pids
        }
        max_cd = max(centroid_dist.values()) or 1
        max_ed = max(enemy_dist.values()) or 1
        # normalizacja do [0,1]: centroid_dist duzy = front, enemy_dist maly = front
        exposure = {
            pid: 0.7 * (centroid_dist[pid] / max_cd) + 0.3 * (1 - enemy_dist[pid] / max_ed)
            for pid in pids
        }
    else:
        exposure = centroid_dist

    ordered = sorted(pids, key=lambda pid: -exposure[pid])  # malejaco: najbardziej wystawieni pierwsi
    n = len(ordered)
    tiers = {}
    for i, pid in enumerate(ordered):
        frac = i / n
        if frac < 1 / 3:
            tiers[pid] = "front"
        elif frac < 2 / 3:
            tiers[pid] = "mid"
        else:
            tiers[pid] = "back"
    return tiers, exposure


def balance_lines(assignment, player_points, tiers, k, iterations=400):
    """Wyrownuje udzial front/mid/back w kazdym czlonie (zeby zaden czlon nie
    byl caly na pierwszej linii albo caly w zapleczu) - zamienia miejscami
    graczy miedzy czlonami z nadwyzka/niedoborem danej warstwy, zachowujac
    rozmiary grup bez zmian."""
    groups_tier = defaultdict(lambda: defaultdict(list))
    for pid, g in assignment.items():
        groups_tier[g][tiers[pid]].append(pid)

    total_by_tier = defaultdict(int)
    for pid in assignment:
        total_by_tier[tiers[pid]] += 1
    ideal = {t: total_by_tier[t] / k for t in LINE_TIERS}

    for _ in range(iterations):
        devs = {g: {t: len(groups_tier[g][t]) - ideal[t] for t in LINE_TIERS} for g in range(k)}
        move = None
        for t in LINE_TIERS:
            over = sorted((g for g in range(k) if devs[g][t] > 0.5), key=lambda g: -devs[g][t])
            under = sorted((g for g in range(k) if devs[g][t] < -0.5), key=lambda g: devs[g][t])
            if over and under and groups_tier[over[0]][t]:
                move = (t, over[0], under[0])
                break
        if not move:
            break
        t, g_over, g_under = move
        pid_over = groups_tier[g_over][t][0]
        other_under = [pid for t2, lst in groups_tier[g_under].items() if t2 != t for pid in lst]
        if not other_under:
            break
        pid_under = other_under[0]

        assignment[pid_over], assignment[pid_under] = g_under, g_over
        groups_tier[g_over][t].remove(pid_over)
        groups_tier[g_under][t].append(pid_over)
        t_under = tiers[pid_under]
        groups_tier[g_under][t_under].remove(pid_under)
        groups_tier[g_over][t_under].append(pid_under)

    return assignment


def ensure_council_coverage(assignment, player_points, council_pids, k):
    """Gwarantuje, ze kazdy z K czlonow ma >=1 czlonka rady (lidera).
    Jesli jakis czlon nie ma nikogo z rady, przenosi tam najblizszego
    (geograficznie) czlonka rady z czlonu, ktory ma ich nadmiar - zamieniajac
    go miejscami z jego najdalszym "zwyklym" graczem, zeby nie zaburzyc
    limitow liczebnosci. Zwraca (assignment, lista_przeniesionych_pidow).
    Jesli czlonkow rady jest mniej niz K, nie da sie pokryc wszystkich -
    brakujace czlony zostaja bez lidera."""
    council_pids = {pid for pid in council_pids if pid in assignment}
    groups_council = defaultdict(set)
    for pid in council_pids:
        groups_council[assignment[pid]].add(pid)

    empty_groups = [g for g in range(k) if not groups_council.get(g)]
    moved = []
    for eg in empty_groups:
        donors = sorted((g for g in range(k) if len(groups_council.get(g, ())) > 1),
                        key=lambda g: -len(groups_council[g]))
        if not donors:
            continue  # za malo czlonkow rady, zeby pokryc wszystkie czlony

        eg_members = [pid for pid, g in assignment.items() if g == eg]
        if eg_members:
            ecx = sum(player_points[pid][0] for pid in eg_members) / len(eg_members)
            ecy = sum(player_points[pid][1] for pid in eg_members) / len(eg_members)
        else:
            ecx = ecy = 0.0

        donor_g = donors[0]
        council_candidate = min(
            groups_council[donor_g],
            key=lambda pid: (player_points[pid][0] - ecx) ** 2 + (player_points[pid][1] - ecy) ** 2,
        )

        eg_noncouncil = [pid for pid in eg_members if pid not in council_pids]
        if eg_noncouncil:
            donor_members = [pid for pid, g in assignment.items() if g == donor_g]
            dcx = sum(player_points[pid][0] for pid in donor_members) / len(donor_members)
            dcy = sum(player_points[pid][1] for pid in donor_members) / len(donor_members)
            swap_out = min(
                eg_noncouncil,
                key=lambda pid: (player_points[pid][0] - dcx) ** 2 + (player_points[pid][1] - dcy) ** 2,
            )
            assignment[swap_out] = donor_g

        assignment[council_candidate] = eg
        groups_council[donor_g].discard(council_candidate)
        groups_council[eg].add(council_candidate)
        moved.append(council_candidate)

    return assignment, moved


def _enforce_capacity(player_points, assignment, k, max_per_group):
    """Przesuwa nadmiarowe (najdalsze od centroidu) punkty do najblizszej
    grupy z wolnym miejscem - twardo egzekwuje limit graczy na czlon."""
    def centroids():
        sums = defaultdict(lambda: [0.0, 0.0, 0])
        for pid, g in assignment.items():
            x, y = player_points[pid]
            s = sums[g]
            s[0] += x
            s[1] += y
            s[2] += 1
        return {g: (s[0] / s[2], s[1] / s[2]) for g, s in sums.items() if s[2] > 0}

    for _ in range(20):
        counts = defaultdict(int)
        for g in assignment.values():
            counts[g] += 1
        overflow = {g: c - max_per_group for g, c in counts.items() if c > max_per_group}
        if not overflow:
            break
        cent = centroids()
        for g, over in overflow.items():
            members = [pid for pid, gg in assignment.items() if gg == g]
            cx, cy = cent[g]
            members.sort(key=lambda pid: -((player_points[pid][0] - cx) ** 2 +
                                            (player_points[pid][1] - cy) ** 2))
            for pid in members[:over]:
                x, y = player_points[pid]
                best_g, best_d = None, None
                for og in range(k):
                    if og == g or counts[og] >= max_per_group:
                        continue
                    ocx, ocy = cent.get(og, (x, y))
                    d = (x - ocx) ** 2 + (y - ocy) ** 2
                    if best_d is None or d < best_d:
                        best_d, best_g = d, og
                if best_g is not None:
                    assignment[pid] = best_g
                    counts[g] -= 1
                    counts[best_g] += 1
    return assignment


def nearest_neighbors_purity(player_points, assignment, k=6):
    """Wykrywa "trudne przypadki" - graczy, ktorych wiekszosc najblizszych
    sasiadow nalezy do innego czlonu (mozliwe enklawy)."""
    pids = list(player_points.keys())
    flagged = []
    for i, pid in enumerate(pids):
        p = player_points[pid]
        dists = []
        for j, pid2 in enumerate(pids):
            if i == j:
                continue
            q = player_points[pid2]
            dists.append(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2, pid2))
        dists.sort(key=lambda t: t[0])
        neigh = dists[:k]
        own = assignment[pid]
        other = sum(1 for _, pid2 in neigh if assignment[pid2] != own)
        if other > k // 2:
            flagged.append(pid)
    return flagged
