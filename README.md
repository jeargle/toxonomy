# toxonomy

A clade-neutral catalog of biological molecules that attack other biological systems —
protein toxins, specialized metabolites including antibiotics, and the defense systems
that deploy them. Organized by what a molecule is, what it attacks, and how its producer
survives it, never by which branch of the tree the producer sits on.

The name is a deliberate pun: a taxonomy of toxins that refuses producer taxonomy as the
organizing axis.

## Status

Schema and a seed catalog. The seed covers one thread — molecules that attack the
translation apparatus — chosen because it contains the clearest convergence in the
literature: five unrelated protein folds cleave or depurinate the same loop of ribosomal
RNA, and the producers span bacteria, fungi, plants, insects and endosymbionts.

28 entities, 36 producers, 24 fold assignments, 15 self-protection records, 9
counter-adaptations, 64 vocabulary terms, 36 references.

## Layout

    schema/schema.sql      DDL (SQLite; portable to Postgres)
    docs/facets.md         the eight facets, and the axes deliberately excluded
    docs/backbone.md       the species-tree backbone and why it is two trees
    data/*.csv             the catalog, one CSV per table — edit these, not the DB
    data/tree_*.nwk        the species-tree backbone, one Newick per domain
    scripts/build_db.py    rebuild toxonomy.db from schema + data
    scripts/build_tree.py  refetch taxonomy and rebuild the backbone
    scripts/reconcile.py   score each entity's distribution against the backbone
    scripts/queries.sql    the queries the scheme exists to answer

## Build

    python scripts/build_db.py toxonomy.db

Rebuilds from scratch each time; the CSVs are the source of truth and the database is
derived, so it never needs migrating during schema development.

## What the seed data already shows

Running `scripts/queries.sql` against the seed:

- The sarcin/ricin loop is attacked by **5 distinct folds** across **11 entities**, with
  producers in both Bacteria and Eukaryota. The tRNA anticodon loop is attacked by
  **6 folds** across 7 entities.
- Self-protection correlates with chemistry, not clade: every protein toxin in the seed
  uses an immunity protein, compartmentalisation, latency, or needs no protection
  because the target is absent; every small-molecule producer uses target modification,
  target replacement, or drug modification.
- Two CdiA-CT toxins share the BECR fold and the same substrate but carry immunity
  proteins of unrelated folds — a beta-sandwich dimer against an alpha-solenoid monomer.
  This is the convergence signature the schema was built to make queryable.
- **Archaea contribute zero rows.** That is the honest state of the field rather than a
  sampling choice here, and it is visible in the clade-neutrality audit (Q3) by design.

## The species-tree backbone

Current scores over the 28 entities: 20 single-record (not assessable), 5 patchy/HGT
signature (`stx`, `diphtheria_toxin`, `cdia_ct_trnase`, `kirromycin`, `gamma_toxin`),
2 lineage-restricted (`ribotoxin_fungal`, `rip_plant_t1`), and 1 recipient-only
(`rip_whitefly`, no de novo producer recorded).

`taxon` holds all 29 producer taxa with NCBI taxid, rank, domain, full NCBI lineage
and Open Tree id; `data/tree_eukaryota.nwk` and `data/tree_bacteria.nwk` are the
topology. `scripts/reconcile.py` scores each entity's distribution against it.

Two trees, not one, and the reason is in `docs/backbone.md`: joining them would mean
asserting a root relationship between Bacteria and Eukaryota that neither source
supports, which is the same objection that rules out "prokaryote" here.

## Intended direction

A DB-backed web service. The CSV-plus-rebuild arrangement is for the period while the
facets are still moving; once they settle, the loader becomes a migration path and the
tables get a web front end.

Next steps, roughly in order: more producers per entity — the backbone works but 20 of
28 entities currently have a single recorded producer, so `distribution_pattern` is not
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
- Literature backing this catalog lives in `~/Downloads/Lit/ribosome-toxins/`.
