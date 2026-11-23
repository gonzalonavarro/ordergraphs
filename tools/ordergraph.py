#!/usr/bin/env python3
"""Order graphs: parsing, completeness checking, lower bounds, and the compact format.

Model (Arroyuelo et al., TODS 2024): attributes are 1..d, nodes are orders (permutations), and an
edge (pi, a), with a != pi[0], goes from pi to a.pi (a moved to the front). A requirement (S, x),
x not in S, is served by a path with |S|+1 edges labeled S + {x}, with the edge labeled x first or
last (only last in the unidirectional model). A graph is complete if it serves every requirement.

Graph formats accepted by parse_graph():
  * Edge list: one edge per line, "order label", e.g. "412563 6". For d >= 10, write the order
    with commas, e.g. "3,1,2,4,5,6,7,8,9,10 7".
  * Compact (d <= 9): one line per component, "start: code", e.g. "412563: 3[6[5]]6*".
    A digit a is an edge labeled a from the current node to a.(current node); the brackets that
    follow it list the edges leaving that target; a star marks an edge whose target was already
    described. Lines starting with # are ignored in both formats.

Usage:
  python3 tools/ordergraph.py check FILE [--uni]
"""
import itertools
import sys
from math import comb

sys.setrecursionlimit(1_000_000)


class GraphError(ValueError):
    pass


def move_front(pi, a):
    return (a,) + tuple(z for z in pi if z != a)


def lb_bi(d):
    """Lower bound for the bidirectional model: max_m C(d,m) ceil(m/2)."""
    return max(comb(d, m) * ((m + 1) // 2) for m in range(1, d + 1))


def lb_uni(d):
    """Lower bound for the unidirectional model: d C(d-1, floor((d-1)/2))."""
    return d * comb(d - 1, (d - 1) // 2)


def lower_bound(model, d):
    return lb_uni(d) if model == "uni" else lb_bi(d)


# ---------------------------------------------------------------- parsing

def _order(tok):
    if "," in tok:
        return tuple(int(c) for c in tok.split(",") if c.strip())
    return tuple(int(c) for c in tok)


def _compact_edges(start, code):
    edges, stack, cur, last = [], [], start, None
    for ch in code:
        if ch.isdigit():
            a = int(ch)
            edges.append((cur, a))
            last = move_front(cur, a)
        elif ch == "[":
            if last is None:
                raise GraphError("'[' must follow an edge label")
            stack.append(cur)
            cur = last
        elif ch == "]":
            if not stack:
                raise GraphError("unbalanced ']'")
            cur = stack.pop()
        elif ch in "* \t":
            continue
        else:
            raise GraphError(f"unexpected character {ch!r} in compact code")
    if stack:
        raise GraphError("unbalanced '['")
    return edges


def parse_graph(text, max_edges=200_000):
    """Parse a graph in either format; return (d, set of edges)."""
    edges = []
    for raw in text.replace("\r", "").split("\n"):
        line = raw.strip().strip("`")
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            start, code = line.split(":", 1)
            edges += _compact_edges(_order(start.strip()), code.strip())
        else:
            toks = line.split()
            if len(toks) != 2:
                raise GraphError(f"cannot read line {raw.strip()[:60]!r}: expected 'order label' "
                                 "or 'start: code'")
            try:
                edges.append((_order(toks[0]), int(toks[1])))
            except ValueError:
                raise GraphError(f"cannot read line {raw.strip()[:60]!r}")
        if len(edges) > max_edges:
            raise GraphError(f"more than {max_edges} edges")
    if not edges:
        raise GraphError("no edges found")
    d = len(edges[0][0])
    full = set(range(1, d + 1))
    for pi, a in edges:
        if len(pi) != d or set(pi) != full:
            raise GraphError(f"{''.join(map(str, pi))} is not an order of 1..{d}")
        if a not in full:
            raise GraphError(f"label {a} is not an attribute of 1..{d}")
        if a == pi[0]:
            raise GraphError(f"edge {''.join(map(str, pi))} --{a}--> is a self-loop")
    E = set(edges)
    if len(E) != len(edges):
        raise GraphError("the graph has repeated edges")
    return d, E


# ---------------------------------------------------------------- completeness

def missing_requirements(edges, d, unidirectional=False):
    """Requirements (S, x) not served by the graph; empty iff the graph is complete.

    h(v) is the length of the longest path with distinct labels ending at v (such a path has labels
    v[k-1], ..., v[0], so paths of every length <= h(v) end at v); it is computed as a least
    fixpoint. Edge (v, a), with a at 1-based position p of v, ends a path with m edges and distinct
    labels iff m <= p and m - 1 <= h(v); that path serves (v[0..m-2], a) and, when m >= 2 in the
    bidirectional model, (v[0..m-3] + {a}, v[m-2])."""
    into = {}
    nodes = set()
    for (u, y) in edges:
        v = move_front(u, y)
        into.setdefault(v, []).append((u, y))
        nodes.add(u)
        nodes.add(v)
    h = {v: 0 for v in nodes}
    changed = True
    while changed:
        changed = False
        for v, inc in into.items():
            best = max(min(d, 1 + min(h[u], u.index(y))) for (u, y) in inc)
            if best > h[v]:
                h[v] = best
                changed = True
    served = set()
    for (v, a) in edges:
        p = v.index(a) + 1
        for m in range(1, min(p, h[v] + 1) + 1):
            served.add((frozenset(v[:m - 1]), a))
            if m >= 2 and not unidirectional:
                served.add((frozenset(v[:m - 2]) | {a}, v[m - 2]))
    missing = []
    for k in range(d):
        for S in itertools.combinations(range(1, d + 1), k):
            for x in range(1, d + 1):
                if x not in S and (frozenset(S), x) not in served:
                    missing.append((set(S), x))
    return missing


# ---------------------------------------------------------------- output formats

def order_str(pi):
    return "".join(map(str, pi)) if len(pi) <= 9 else ",".join(map(str, pi))


def edge_list(edges, d, model, header=True):
    lines = []
    if header:
        name = "unidirectional" if model == "uni" else "bidirectional"
        lines += [f"# complete order graph, d={d}, {name} model, {len(edges)} edges",
                  "# one edge per line: source order, label (target = label moved to the front)"]
    lines += [f"{order_str(u)} {a}" for u, a in sorted(edges)]
    return "\n".join(lines) + "\n"


def compact(edges):
    """Compact encoding (d <= 9): list of (start order string, code)."""
    out = {}
    for (u, a) in edges:
        out.setdefault(u, []).append(a)
    nodes = {u for u, _ in edges} | {move_front(u, a) for u, a in edges}
    indeg = {v: 0 for v in nodes}
    pred = {}
    for (u, a) in edges:
        v = move_front(u, a)
        indeg[v] += 1
        pred[v] = u
    seen = set()

    def dfs(u):
        seen.add(u)
        parts = []
        for a in sorted(out.get(u, [])):
            v = move_front(u, a)
            if v in seen:
                parts.append(f"{a}*")
            else:
                sub = dfs(v)
                parts.append(f"{a}[{sub}]" if sub else f"{a}")
        return "".join(parts)

    comps = []
    for r in sorted(v for v in nodes if indeg[v] == 0):
        if r not in seen:
            comps.append((r, dfs(r)))
    while len(seen) < len(nodes):
        v = min(nodes - seen)
        trail = set()
        while v not in trail and v in pred and pred[v] not in seen:
            trail.add(v)
            v = pred[v]
        comps.append((v, dfs(v)))
    return [("".join(map(str, p)), s) for p, s in comps]


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "check":
        print(__doc__)
        sys.exit(2)
    uni = "--uni" in sys.argv
    try:
        d, E = parse_graph(open(sys.argv[2]).read())
    except GraphError as e:
        print(f"invalid graph: {e}")
        sys.exit(1)
    miss = missing_requirements(E, d, uni)
    print(f"d={d}, {len(E)} edges, {'uni' if uni else 'bi'}directional: "
          f"{'complete' if not miss else f'NOT complete ({len(miss)} requirements missing)'}")
    sys.exit(0 if not miss else 1)
