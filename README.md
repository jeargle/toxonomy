# toxonomy

A clade-neutral catalog of biological molecules that attack other biological systems —
protein toxins, specialized metabolites including antibiotics, and the defense systems
that deploy them. Organized by what a molecule is, what it attacks, and how its producer
survives it, never by which branch of the tree the producer sits on.

The name is a deliberate pun: a taxonomy of toxins that refuses producer taxonomy as the
organizing axis.

## Status

Schema plus a seed catalog covering two rounds. The first round took one thread —
molecules that attack the translation apparatus. The second widened it across the facet
space: membrane and cell-wall attack, ion channels, the cytoskeleton, DNA, the NAD+
pool, small-molecule chemistry, and the first archaeal entries.

54 entities, 66 producer records over 56 taxa (28 Bacteria, 26 Eukaryota, 2 Archaea),
39 fold assignments, 26 self-protection records, 17 counter-adaptations, 85 vocabulary
terms of which 80 are in use, 426 facet assignments, 74 references.

## Layout

    pyproject.toml         dependencies (uv); uv.lock pins them
    schema/schema.sql      DDL (SQLite; portable to Postgres)
    docs/facets.md         the eight facets, and the axes deliberately excluded
    docs/backbone.md       the species-tree backbone and why it is two trees
    data/*.csv             the catalog, one CSV per table — edit these, not the DB
    data/tree_*.nwk        the backbone: tree_eukaryota.nwk and tree_bacteria_archaea.nwk
    scripts/build_db.py    rebuild toxonomy.db from schema + data
    scripts/build_tree.py  refetch taxonomy and rebuild the backbone
    scripts/reconcile.py   score each entity's distribution against the backbone
    scripts/build_site.py  render the database as a static website (_site/)
    scripts/check.py       integrity checks beyond what the foreign keys catch
    scripts/queries.sql    the queries the scheme exists to answer

## Build

Dependencies are managed with [uv](https://docs.astral.sh/uv/):

    uv sync
    uv run python scripts/build_db.py toxonomy.db   # schema + data -> toxonomy.db
    uv run python scripts/check.py                  # catalog integrity
    uv run python scripts/reconcile.py              # distribution scores
    uv run python scripts/build_site.py             # toxonomy.db -> _site/

`build_db.py` rebuilds from scratch each time; the CSVs are the source of truth and the
database is derived, so it never needs migrating during schema development.

`scripts/build_tree.py` refetches the backbone from NCBI, Open Tree and GTDB. Run it by
hand when the taxon set changes and commit the regenerated `taxon.csv` and `tree_*.nwk`;
it is deliberately kept out of CI so pushes do not hit those services.

## Website

Browse the catalog at <https://jeargle.github.io/toxonomy/>. Every push to `main` that
passes the checks rebuilds the database, renders it with `scripts/build_site.py` and
publishes it to GitHub Pages. The site is static: one page per entity, vocabulary term,
fold, taxon and reference, a filterable entity index, and `toxonomy.db` / `toxonomy.json`
downloads. Links are relative, so `_site/index.html` also works opened straight from disk.

Facet assignments with no `ref_id` are shown as *uncited*, and a `pan-domain` facet that the
producer rows do not support is flagged on the entity page.

## What the seed data already shows

Running `scripts/queries.sql` and `scripts/reconcile.py` against the catalog:

- **Immunity proteins track how the toxin is encoded, not what it does.** A cognate
  immunity protein appears only for ribosomally encoded toxins — 10 protein entities
  and one RiPP, nisin with NisI. No non-ribosomal peptide, polyketide, aminoglycoside,
  alkaloid or steroid glycoside in the catalog has one; they use target modification,
  target replacement, drug modification, a sequestering binding protein, or need no
  protection at all (penicillin, whose fungal producer has no peptidoglycan). A
  polyketide cannot have a cognate immunity gene sitting next to it; a gene-encoded
  toxin can. This falls out of a two-table join with no clade term in it.
- **The membrane bilayer is the single most converged-on target**, tied with the tRNA
  anticodon loop at 6 distinct folds each; the sarcin/ricin loop has 5 across 11
  entities and the NAD+ pool 3 across 3. Aggregated by target class the translation
  apparatus is still far ahead — 15 folds across 24 entities, against 8 across 10 for
  membrane targets — which reflects the catalog's history rather than biology, since
  the first round was translation-only.
- One fold in the catalog spans producer domains on the evidence of its own rows:
  MACPF/CDC, covering bacterial cholesterol-dependent cytolysins and animal perforin-2.
  The RIP fold also spans Bacteria and Eukaryota, across 6 entities. The aerolysin-like
  beta-PFT is carried as `pan-domain` on the strength of the literature, but both of its
  catalog entities — a fungal aerolysin-like protein and a snail anti-trematode toxin —
  are eukaryotic, so the facet is an assertion the rows do not yet support.
- Two CdiA-CT toxins share the BECR fold and the same substrate but carry immunity
  proteins of unrelated folds — a beta-sandwich dimer against an alpha-solenoid monomer.
- Distribution scores over the 54 entities: 43 single-record (not assessable), 6 patchy
  or HGT signature, 2 lineage-restricted, 1 pan-domain (saxitoxin, made by both a
  dinoflagellate and a cyanobacterium), and 2 carrier-only. Breadth improved this round;
  producers per entity did not, and that is still the binding constraint.

## Intended direction

A DB-backed web service. The CSV-plus-rebuild arrangement is for the period while the
facets are still moving; once they settle, the loader becomes a migration path and the
tables get a web front end.

Next steps, roughly in order: more producers per entity — the backbone works but 43 of
54 entities currently have a single recorded producer, so `distribution_pattern` is not
yet assessable for them, and that is the binding constraint rather than entity count;
a GTDB lineage fill once the API is reachable; bulk ingestion from Toxinome, UniProt Tox-Prot,
MIBiG and DefenseFinder/PADLOC with InterPro accessions as the join key; and a second
thread — membrane-attacking toxins, where the pore-forming folds offer an independent
test of whether these facets generalize beyond translation.

## Conventions

- "Bacteria and Archaea", never "prokaryote": the term names a grade, not a clade, and
  under the two-domain tree eukaryotes nest within Archaea.
- Source databases that use "prokaryotic" in field names keep the original string in a
  `source_term` column at ingestion, so the mapping back to the literature stays auditable.
- Every catalog row is anchored to a published source: `data/reference.csv` carries the
  citation, DOI and PMID for each `ref_id`, and the other tables cite it by key.
