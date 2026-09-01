"""Wykrywanie "rodzin" plemion (te same tagi/nazwy w wariantach: ~G~, :G:,
-G-, ;G; / "Polanie", "Polanie 2", "Polanie 3" itd.)."""
import re
from collections import defaultdict


class UnionFind:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _normalize_tag(tag):
    return re.sub(r"[^A-Za-z0-9]", "", tag).upper()


def _normalize_name(name):
    core = re.sub(r"[^A-Za-z0-9]", "", name).lower()
    # usun koncowe cyfry / cyfry rzymskie - warianty typu "Polanie 2", "Polanie II"
    core = re.sub(r"(ii+|iv|v|vi+|[0-9]+)$", "", core)
    return core


def detect_families(allies, min_size=2, exclude_ally_ids=None):
    """Zwraca liste rodzin: [{id, name, ally_ids, tags}], posortowana malejaco
    wg laczonej liczby czlonkow. exclude_ally_ids pozwala wykluczyc plemiona,
    ktore przypadkiem pasuja nazwa/tagiem (np. podszywajace sie "obce"
    plemie), ale w rzeczywistosci nie naleza do rodziny."""
    exclude_ally_ids = set(exclude_ally_ids or ())
    considered = {aid: a for aid, a in allies.items() if aid not in exclude_ally_ids}
    uf = UnionFind(list(considered.keys()))

    by_tag = defaultdict(list)
    by_name = defaultdict(list)
    for aid, a in considered.items():
        by_tag[_normalize_tag(a["tag"])].append(aid)
        by_name[_normalize_name(a["name"])].append(aid)

    for group in list(by_tag.values()) + list(by_name.values()):
        if len(group) < 2:
            continue
        for other in group[1:]:
            uf.union(group[0], other)

    clusters = defaultdict(list)
    for aid in considered:
        clusters[uf.find(aid)].append(aid)

    families = []
    for root, ids in clusters.items():
        if len(ids) < min_size:
            continue
        ids.sort(key=lambda i: -allies[i]["members"])
        rep_name = allies[ids[0]]["name"]
        total_members = sum(allies[i]["members"] for i in ids)
        families.append({
            "ally_ids": ids,
            "name": rep_name,
            "tags": [allies[i]["tag"] for i in ids],
            "total_members": total_members,
        })
    families.sort(key=lambda f: -f["total_members"])
    return families


def solo_allies(allies, families):
    grouped = {aid for f in families for aid in f["ally_ids"]}
    return [aid for aid in allies if aid not in grouped]
