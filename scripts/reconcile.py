"""Score each entity's distribution against the species-tree backbone.

Absence in this catalog means "not recorded", never "surveyed and absent", so
every count here is a LOWER BOUND over the taxa the catalog happens to sample.
"""
import csv
from pathlib import Path
from Bio import Phylo

ROOT = Path(__file__).resolve().parent.parent
# Bacteria and Archaea share one backbone file; eukaryotes have their own.
TREE_OF_DOMAIN = {"Eukaryota": "tree_eukaryota.nwk",
                  "Bacteria": "tree_bacteria_archaea.nwk",
                  "Archaea": "tree_bacteria_archaea.nwk"}


def load_trees():
    """Read each backbone once; return {filename: tree}."""
    out = {}
    for fname in set(TREE_OF_DOMAIN.values()):
        path = ROOT / "data" / fname
        if path.exists():
            out[fname] = Phylo.read(str(path), "newick")
    return out


def node_by_name(tree, name):
    """The clade carrying this taxon label, tip or internal."""
    for clade in tree.find_clades():
        if clade.name == name:
            return clade
    return None


def catalog_taxa_under(tree, clade, catalog):
    """Catalog taxa at or below this clade."""
    names = {c.name for c in clade.find_clades() if c.name}
    return names & catalog


def score_one(tree, present, catalog):
    """MRCA span and coverage for one entity within one domain tree."""
    nodes = [node_by_name(tree, n) for n in present]
    nodes = [n for n in nodes if n is not None]
    if not nodes:
        return None
    mrca = nodes[0] if len(nodes) == 1 else tree.common_ancestor(nodes)
    under = catalog_taxa_under(tree, mrca, catalog)
    return {"n_present": len(nodes), "n_in_mrca_clade": len(under),
            "coverage": len(present & under) / len(under) if under else 1.0}


def classify(domains, spans):
    """Heuristic distribution_pattern from the per-domain spans."""
    if len(domains) > 1:
        return "pan-domain"
    span = next(iter(spans.values()))
    if span["n_present"] == 1:
        return "single record (not assessable)"
    if span["coverage"] < 0.6:
        return "patchy / HGT signature"
    return "lineage-restricted"


def split_producers(prod):
    """Partition producer rows into made-here and carried-only taxon sets per entity.

    Only de novo producers describe where a toxin is MADE. Organisms that
    acquired the genes, host a symbiont that makes it, or sequester it from
    the diet carry it without making it, and would otherwise inflate the
    apparent distribution across the tree.
    """
    carried = {"horizontally_acquired", "sequestered", "symbiont_derived"}
    by_entity, acquired = {}, {}
    for row in prod:
        bucket = acquired if row["provenance"] in carried else by_entity
        bucket.setdefault(row["entity_id"], set()).add(row["taxon_name"])
    return by_entity, acquired


def score_entity(present, taxa, trees):
    """Per-backbone spans for one entity's de novo producer set."""
    domains = sorted({taxa.get(t) for t in present if taxa.get(t)})
    spans = {}
    for fname in sorted({TREE_OF_DOMAIN[d] for d in domains if d in TREE_OF_DOMAIN}):
        catalog = {t for t, d in taxa.items() if TREE_OF_DOMAIN.get(d) == fname}
        span = score_one(trees[fname], present & catalog, catalog)
        if span:
            spans[fname] = span
    return domains, spans


def score_all(data=None):
    """One record per scored entity, made-here entities first, then carrier-only.

    Each record: entity_id, domains (list), n (int), coverage (float or None),
    pattern (str), carried_by (sorted list of carrier taxa).
    """
    data = Path(data) if data else ROOT / "data"
    prod = list(csv.DictReader((data / "producer.csv").open()))
    taxa = {r["scientific_name"]: r["domain"]
            for r in csv.DictReader((data / "taxon.csv").open())}
    trees = load_trees()
    by_entity, acquired = split_producers(prod)
    out = []
    for entity, present in sorted(by_entity.items()):
        domains, spans = score_entity(present, taxa, trees)
        if not spans:
            continue
        out.append({"entity_id": entity, "domains": domains,
                    "n": sum(s["n_present"] for s in spans.values()),
                    "coverage": min(s["coverage"] for s in spans.values()),
                    "pattern": classify(domains, spans),
                    "carried_by": sorted(acquired.get(entity, ()))})
    for entity, taxa_set in sorted(acquired.items()):
        if entity not in by_entity:
            out.append({"entity_id": entity, "domains": [], "n": len(taxa_set),
                        "coverage": None, "pattern": "carrier only",
                        "carried_by": sorted(taxa_set)})
    return out


def main():
    print(f"{'entity':20s} {'domains':18s} {'n':>2s} {'cov':>5s}  pattern")
    for r in score_all():
        if r["coverage"] is None:
            print(f"{r['entity_id']:20s} {'(recipient only)':18s} {r['n']:2d}    -  "
                  f"carried, not made, by: {', '.join(r['carried_by'])}")
            continue
        tag = r["pattern"]
        if r["carried_by"]:
            tag += f"; carried by {', '.join(r['carried_by'])}"
        print(f"{r['entity_id']:20s} {','.join(r['domains']):18s} {r['n']:2d} "
              f"{r['coverage']:5.2f}  {tag}")
    print("\nCounts are lower bounds over sampled taxa; absence means not recorded.")


if __name__ == "__main__":
    main()
