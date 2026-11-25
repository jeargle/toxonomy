"""Integrity checks for the toxonomy catalog.

The database build already enforces foreign keys, so this covers what SQL
cannot: that the Newick backbones parse, that every producer is addressable on
the tree for its domain, and that the facet vocabulary has not drifted.

Exit status is 1 if any check fails, so CI stops on a bad commit.
"""
import csv
import sys
from pathlib import Path

from Bio import Phylo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TREES = {"Eukaryota": "tree_eukaryota.nwk", "Bacteria": "tree_bacteria.nwk"}
FACETS = {"chemical_nature", "molecular_target", "mode_of_action", "delivery",
          "self_protection", "antagonist_relation", "mobility_context",
          "distribution_pattern"}


def rows(name):
    """Rows of data/<name>.csv as dicts."""
    with (DATA / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def tree_labels(fname):
    """Every labelled node in a Newick file, tips and internal alike."""
    tree = Phylo.read(str(DATA / fname), "newick")
    return {c.name for c in tree.find_clades() if c.name}


def check_vocabulary(problems):
    """Facet names are in the fixed set and every used term is defined."""
    terms = rows("cv_term.csv")
    defined = {t["term_id"] for t in terms}
    bad_facets = {t["facet"] for t in terms} - FACETS
    if bad_facets:
        problems.append(f"cv_term: unknown facet(s) {sorted(bad_facets)}")
    used = {r["term_id"] for r in rows("entity_facet.csv")}
    missing = used - defined
    if missing:
        problems.append(f"entity_facet: undefined term(s) {sorted(missing)}")
    orphan = defined - used
    if orphan:
        print(f"note: {len(orphan)} vocabulary term(s) defined but unused")


def check_taxa(problems):
    """Every producer resolves to a taxon row and a node on its domain tree."""
    taxa = {t["scientific_name"]: t for t in rows("taxon.csv")}
    labels = {d: tree_labels(f) for d, f in TREES.items() if (DATA / f).exists()}
    for row in rows("producer.csv"):
        name = row["taxon_name"]
        record = taxa.get(name)
        if record is None:
            problems.append(f"producer: {name!r} has no taxon row")
            continue
        if record["ncbi_taxid"] != row["ncbi_taxid"]:
            problems.append(f"producer: {name!r} taxid disagrees with taxon.csv")
        domain = record["domain"]
        if domain in labels and name not in labels[domain]:
            problems.append(f"producer: {name!r} is not a node on the {domain} tree")


def check_references(problems):
    """Every ref_id cited anywhere exists in reference.csv."""
    known = {r["ref_id"] for r in rows("reference.csv")}
    sources = {"producer.csv": "ref_id", "immunity.csv": "ref_id",
               "counter_adaptation.csv": "ref_id", "entity_reference.csv": "ref_id",
               "entity_facet.csv": "ref_id"}
    for fname, column in sources.items():
        if not (DATA / fname).exists():
            continue
        for row in rows(fname):
            value = row.get(column)
            if value and value not in known:
                problems.append(f"{fname}: unknown ref_id {value!r}")


def main():
    problems = []
    check_vocabulary(problems)
    check_taxa(problems)
    check_references(problems)
    for problem in problems:
        print(f"FAIL {problem}")
    if problems:
        print(f"\n{len(problems)} problem(s)")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
