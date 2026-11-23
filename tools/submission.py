#!/usr/bin/env python3
"""Check a result submitted through the GitHub issue form, and add it once approved.

  python3 tools/submission.py check BODY_FILE REPORT_FILE
      Parses and verifies the submission; writes a Markdown report. Exit 0 if valid.
  python3 tools/submission.py add BODY_FILE ISSUE_NUMBER GITHUB_USER
      Verifies again and writes results/NNNN-model-dD/{result.json,graph.txt}.

The issue body is untrusted input: it is only parsed as text, never executed.
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ordergraph import (GraphError, edge_list, lower_bound, missing_requirements,  # noqa: E402
                        parse_graph)

FIELDS = {"Model": "model", "Dimension d": "d", "Graph": "graph", "Contributors": "contributors",
          "Method": "method", "Reference": "reference", "Link": "url", "Comment": "comment"}
MAXLEN = {"contributors": 300, "method": 500, "reference": 500, "url": 300, "comment": 2000}


class SubmissionError(ValueError):
    pass


def parse_body(text):
    parts = re.split(r"^### +(.+?) *$", text.replace("\r", ""), flags=re.M)
    raw = {}
    for i in range(1, len(parts) - 1, 2):
        key = FIELDS.get(parts[i].strip())
        if key:
            val = parts[i + 1].strip()
            raw[key] = "" if val == "_No response_" else val
    return raw


def best_known(model, d):
    best = None
    rdir = os.path.join(ROOT, "results")
    for rid in os.listdir(rdir):
        p = os.path.join(rdir, rid, "result.json")
        if os.path.isfile(p):
            r = json.load(open(p, encoding="utf-8"))
            if r["model"] == model and r["d"] == d and (best is None or r["edges"] < best):
                best = r["edges"]
    return best


def validate(raw):
    model_txt = raw.get("model", "").lower()
    if model_txt.startswith("bi"):
        model = "bi"
    elif model_txt.startswith("uni"):
        model = "uni"
    else:
        raise SubmissionError("the model must be Bidirectional or Unidirectional")
    try:
        d_claimed = int(raw.get("d", "").strip())
    except ValueError:
        raise SubmissionError("the dimension d must be an integer")
    graph = raw.get("graph", "")
    graph = re.sub(r"^```\w*\s*$", "", graph, flags=re.M)   # drop code fences, if any
    try:
        d, E = parse_graph(graph)
    except GraphError as e:
        raise SubmissionError(f"the graph could not be read: {e}")
    if d != d_claimed:
        raise SubmissionError(f"the graph has dimension {d}, but the form says d = {d_claimed}")
    if d < 3 or d > 12:
        raise SubmissionError("only dimensions 3 to 12 are accepted")
    if not raw.get("contributors", "").strip():
        raise SubmissionError("please give the name of the contributors")
    for k, n in MAXLEN.items():
        if len(raw.get(k, "")) > n:
            raise SubmissionError(f"the field '{k}' is too long (at most {n} characters)")
    url = raw.get("url", "").strip()
    if url and not re.match(r"^https?://\S+$", url):
        raise SubmissionError("the link must be a single http(s) URL")
    missing = missing_requirements(E, d, model == "uni")
    return model, d, E, missing


def check(body_file, report_file):
    raw = parse_body(open(body_file, encoding="utf-8").read())
    lines = []
    ok = False
    try:
        model, d, E, missing = validate(raw)
        name = "unidirectional" if model == "uni" else "bidirectional"
        if missing:
            S, x = missing[0]
            lines.append(f"❌ The graph has {len(E)} edges but is **not complete** in the {name} model: "
                         f"{len(missing)} requirements are not served, for example S = "
                         f"{{{', '.join(map(str, sorted(S)))}}}, x = {x}.")
            lines.append("\nYou can edit the issue to fix it; it will be checked again.")
        else:
            ok = True
            best = best_known(model, d)
            lb = lower_bound(model, d)
            lines.append(f"✅ Verified: a complete order graph with **{len(E)} edges** for d = {d}, "
                         f"{name} model (lower bound {lb}).")
            if best is None:
                lines.append("There is no previous result for this case.")
            elif len(E) < best:
                lines.append(f"It **improves** the best known size, {best}.")
            elif len(E) == best:
                lines.append(f"It matches the best known size, {best}.")
            else:
                lines.append(f"It does not improve the best known size, {best}.")
            lines.append("\nThe maintainer will review the submission. Once it is approved (label "
                         "`approved`), it is added to the page automatically.")
    except SubmissionError as e:
        lines.append(f"❌ The submission could not be accepted: {e}.")
        lines.append("\nYou can edit the issue to fix it; it will be checked again.")
    open(report_file, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


def add(body_file, issue, user):
    raw = parse_body(open(body_file, encoding="utf-8").read())
    model, d, E, missing = validate(raw)
    if missing:
        raise SubmissionError("the graph is not complete")
    rdir = os.path.join(ROOT, "results")
    n = 1 + max([int(x[:4]) for x in os.listdir(rdir) if x[:4].isdigit()] or [0])
    rid = f"{n:04d}-{model}-d{d}"
    os.makedirs(os.path.join(rdir, rid))
    ref_text = raw.get("reference", "").strip()
    url = raw.get("url", "").strip()
    rec = {"model": model, "d": d, "edges": len(E),
           "date": datetime.date.today().isoformat(),
           "contributors": raw["contributors"].strip(),
           "method": raw.get("method", "").strip(),
           "reference": {"text": ref_text or url, "url": url} if (ref_text or url) else None,
           "comment": raw.get("comment", "").strip(),
           "graph": "graph.txt",
           "submission": {"issue": int(issue), "user": user}}
    open(os.path.join(rdir, rid, "graph.txt"), "w").write(edge_list(E, d, model))
    json.dump(rec, open(os.path.join(rdir, rid, "result.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(rid)
    return rid


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "check":
        sys.exit(check(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) == 5 and sys.argv[1] == "add":
        try:
            add(sys.argv[2], sys.argv[3], sys.argv[4])
        except SubmissionError as e:
            sys.exit(f"cannot add: {e}")
    else:
        print(__doc__)
        sys.exit(2)
