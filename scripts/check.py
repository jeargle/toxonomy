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
TREE_OF_DOMAIN = {"Eukaryota": "tree_eukaryota.nwk",
                  "Bacteria": "tree_bacteria_archaea.nwk",
                  "Archaea": "tree_bacteria_archaea.nwk"}
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


def check_not_empty(problems):
    """A table that silently lost its rows should fail, not pass."""
    required = ["entity.csv", "cv_term.csv", "entity_facet.csv", "producer.csv",
                "taxon.csv", "reference.csv"]
    for name in required:
        if not (DATA / name).exists():
            problems.append(f"{name}: missing")
        elif not rows(name):
            problems.append(f"{name}: no data rows")


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
    """Every producer resolves to a taxon row and a node on its domain tree.

    Eukaryotes flagged ott_broken or ott_absent cannot be placed: the Open Tree
    induced subtree is their only backbone, so they are reported as unplaceable
    rather than failed. Bacteria and Archaea always get a node in the NCBI
    cladogram, so a missing label there is a real failure.
    """
    taxa = {t["scientific_name"]: t for t in rows("taxon.csv")}
    unplaceable = []
    labels = {d: tree_labels(f) for d, f in TREE_OF_DOMAIN.items()
              if (DATA / f).exists()}
    for row in rows("producer.csv"):
        name = row["taxon_name"]
        record = taxa.get(name)
        if record is None:
            problems.append(f"producer: {name!r} has no taxon row")
            continue
        if record["ncbi_taxid"] != row["ncbi_taxid"]:
            problems.append(f"producer: {name!r} taxid disagrees with taxon.csv")
        domain = record["domain"]
        if domain not in labels or name in labels[domain]:
            continue
        flagged = record.get("ott_broken") == "1" or record.get("ott_absent") == "1"
        if domain == "Eukaryota" and flagged:
            unplaceable.append(name)
        else:
            problems.append(f"producer: {name!r} is not a node on the {domain} tree")
    if unplaceable:
        print(f"note: {len(set(unplaceable))} taxon/taxa unplaceable on a backbone: "
              f"{', '.join(sorted(set(unplaceable)))}")


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
    check_not_empty(problems)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
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
