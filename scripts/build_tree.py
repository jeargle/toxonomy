"""Rebuild the species-tree backbone from producer.csv.

Eukaryotes: Open Tree of Life induced subtree (a real phylogeny).
Bacteria/Archaea: NCBI taxonomy cladogram, a PLACEHOLDER. GTDB is the intended
source; its API was unreachable when this was written, so gtdb_lineage is left
null and fill_gtdb() is here for when it returns.

The two domains are written as SEPARATE trees on purpose. Joining them would
require asserting a root relationship these sources do not support.
"""
import csv
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from Bio import Phylo

ROOT = Path(__file__).resolve().parent.parent
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OTL = "https://api.opentreeoflife.org/v3/"
GTDB = "https://api.gtdb.ecogenomic.org"
DOMAINS = ("Bacteria", "Archaea", "Eukaryota")


def fetch_ncbi(taxids):
    """NCBI taxonomy records for a list of taxids."""
    resp = requests.get(EUTILS + "efetch.fcgi", timeout=90,
                        params={"db": "taxonomy", "id": ",".join(map(str, taxids)),
                                "retmode": "xml"})
    resp.raise_for_status()
    out = {}
    for node in ET.fromstring(resp.text).findall("Taxon"):
        ex = node.find("LineageEx")
        lineage = [t.findtext("ScientificName") for t in ex.findall("Taxon")] if ex is not None else []
        out[node.findtext("ScientificName")] = {
            "taxid": int(node.findtext("TaxId")), "rank": node.findtext("Rank"),
            "lineage_str": node.findtext("Lineage"), "lineage": lineage,
            "domain": next((d for d in lineage if d in DOMAINS), None)}
    return out


def match_ott(names):
    """Open Tree TNRS match; returns {name: ott_id}."""
    resp = requests.post(OTL + "tnrs/match_names", json={"names": names}, timeout=60)
    resp.raise_for_status()
    out = {}
    for res in resp.json()["results"]:
        if res["matches"]:
            out[res["name"]] = res["matches"][0]["taxon"]["ott_id"]
    return out


def induced_subtree(ott_ids):
    """Open Tree induced subtree; returns (newick, broken_ott_ids)."""
    resp = requests.post(OTL + "tree_of_life/induced_subtree", timeout=90,
                         json={"ott_ids": list(ott_ids), "label_format": "name_and_id"})
    resp.raise_for_status()
    body = resp.json()
    broken = {int(k.replace("ott", "")) for k in body.get("broken", {})}
    return body["newick"], broken


def relabel(newick, ott_to_name):
    """Replace Open Tree tip labels with catalog taxon names; drop internal labels."""
    tree = Phylo.read(io.StringIO(newick), "newick")
    for clade in tree.get_terminals():
        found = re.search(r"ott(\d+)$", (clade.name or "").replace(" ", "_"))
        if found:
            clade.name = ott_to_name.get(int(found.group(1)), clade.name)
    for clade in tree.get_nonterminals():
        clade.name = None
    tree.ladderize()
    buf = io.StringIO()
    Phylo.write(tree, buf, "newick")
    return buf.getvalue().strip()


def cladogram(paths, catalog):
    """Newick cladogram from lineage paths; catalog taxa keep labels when internal."""
    trie = {}
    for path in paths.values():
        node = trie
        for step in path:
            node = node.setdefault(step, {})

    def render(node, label):
        tag = f"'{label}'" if label in catalog else ""
        if not node:
            return tag or f"'{label}'"
        kids = ",".join(render(v, k) for k, v in sorted(node.items()))
        return f"({kids}){tag}" if (len(node) > 1 or tag) else kids

    roots = [render(v, k) for k, v in sorted(trie.items())]
    return ("(" + ",".join(roots) + ");") if len(roots) > 1 else roots[0] + ";"


def fill_gtdb(name):
    """GTDB lineage string for one taxon, or None when the API is unavailable."""
    try:
        resp = requests.get(f"{GTDB}/taxon/search/{name}", timeout=30, params={"limit": 1})
        resp.raise_for_status()
        rows = resp.json()
        return rows[0].get("gtdbTaxonomy") if rows else None
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def main():
    data = ROOT / "data"
    gtdb_up = True
    producers = list(csv.DictReader((data / "producer.csv").open()))
    names = sorted({r["taxon_name"] for r in producers})
    ncbi = fetch_ncbi(sorted({int(r["ncbi_taxid"]) for r in producers}))
    ott = match_ott(names)

    # One call over ALL taxa to learn which are broken on the Open Tree backbone,
    # then a eukaryote-only call for the tree itself (bacteria go to the cladogram).
    _, broken = induced_subtree([ott[n] for n in names if n in ott])
    euk = [n for n in names if ncbi.get(n, {}).get("domain") == "Eukaryota"]
    newick, _ = induced_subtree([ott[n] for n in euk if n in ott])
    ott_to_name = {v: k for k, v in ott.items()}
    (data / "tree_eukaryota.nwk").write_text(relabel(newick, ott_to_name) + "\n")

    pro = [n for n in names if ncbi.get(n, {}).get("domain") in ("Bacteria", "Archaea")]
    paths = {n: ncbi[n]["lineage"] + [n] for n in pro}
    (data / "tree_bacteria.nwk").write_text(cladogram(paths, set(pro)) + "\n")

    with (data / "taxon.csv").open("w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(["ncbi_taxid", "scientific_name", "rank", "domain",
                      "ncbi_lineage", "gtdb_lineage", "ott_id", "ott_broken"])
        for name in names:
            rec = ncbi[name]
            gtdb = None
            if gtdb_up and rec["domain"] in ("Bacteria", "Archaea"):
                gtdb = fill_gtdb(name)
                gtdb_up = gtdb is not None
            out.writerow([rec["taxid"], name, rec["rank"], rec["domain"],
                          rec["lineage_str"], gtdb, ott.get(name),
                          int(ott.get(name) in broken)])
    print(f"{len(euk)} eukaryote tips, {len(pro)} bacterial/archaeal nodes, "
          f"{len(broken)} broken on the Open Tree backbone")


if __name__ == "__main__":
    main()
