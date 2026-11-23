# Complete order graphs: best known sizes

This repository holds the page that tracks the smallest known complete order graphs, in the
bidirectional and unidirectional models, together with the graphs themselves. The page is
published from `docs/` with GitHub Pages.

**To submit a result**, open a [new result issue](../../issues/new?template=new-result.yml). The
graph is verified automatically and a bot comments on the issue; once the maintainer approves it,
it is added to the page.

**To report a lower bound**, open a [lower-bound claim](../../issues/new?template=lower-bound.yml),
with a proof or a reference. Lower bounds cannot be verified automatically: once approved, they
are listed as unverified claims, and they are used in the table only after the maintainer marks
them as accepted.

## Layout

| Path | Contents |
|---|---|
| `results/NNNN-model-dD/result.json` | One result: model, d, size, contributors, method, reference, comment. |
| `results/NNNN-model-dD/graph.txt` | Its graph, one edge per line (`order label`). |
| `data/site.json` | Page title, paper reference, repository name. |
| `claims/NNNN-model/claim.json` | One lower-bound claim; `"status"` is `"claimed"` or `"accepted"`. |
| `tools/ordergraph.py` | Graph parsing, completeness check, lower bounds, compact format. |
| `tools/build_site.py` | Rebuilds `docs/` from the results, verifying every graph again. |
| `tools/submission.py` | Checks and adds results and claims submitted through the issue forms. |
| `docs/` | The generated page (do not edit by hand). |

Everything uses only the Python 3 standard library. To check a graph locally:

```bash
python3 tools/ordergraph.py check graph.txt          # bidirectional
python3 tools/ordergraph.py check graph.txt --uni    # unidirectional
```

## Workflows

* **Check submission**: on every new or edited issue labeled `new-result`, verifies the graph,
  comments with the outcome, and labels the issue `verified` or `invalid`.
* **Add approved result**: when the repository owner labels a submission `approved`, verifies it
  again, adds it to `results/`, rebuilds the page, and closes the issue.
* **Rebuild page**: rebuilds `docs/` after any direct edit of `results/`, `data/`, or `tools/`.
* **Set up labels**: run once by hand to create the labels.
