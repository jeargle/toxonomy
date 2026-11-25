# The species-tree backbone

`distribution_pattern` is meant to be computed, not asserted. That needs a tree the
producer taxa can be placed on. This is what was built, and what it cannot do.

## Two trees, deliberately

`data/tree_eukaryota.nwk` — Open Tree of Life induced subtree over the 12 eukaryote
producers (plants, fungi, insects). A real phylogeny, synthesised from 77 supporting
studies. All 12 placed cleanly.

`data/tree_bacteria.nwk` — an NCBI taxonomy cladogram over the 17 bacterial producers.
**A placeholder, not a phylogeny.** GTDB is the intended source; its API returned 502
at connect while this was built, so `taxon.gtdb_lineage` is null throughout and
`scripts/build_tree.py` fills it on a later run.

They are not joined. A single rooted tree spanning both would require asserting a
relationship between the Bacteria clade and the Eukaryota clade, and under the
two-domain tree eukaryotes nest within Archaea rather than sitting as a sister group to
Bacteria. The sources here support neither arrangement, so the backbone declines to
choose and cross-domain comparisons run against the two trees separately.

## Open Tree cannot carry the bacteria

Five taxa are "broken" on the Open Tree synthetic tree — the taxon concept is not a
node in it — and are flagged `taxon.ott_broken`:

| Taxon | Why it matters |
|---|---|
| *Escherichia coli* | The catalog's most frequent producer; paraphyletic with *Shigella* |
| *Pseudomonas aeruginosa* | Producer of Ribocin and Exotoxin A |
| *Mycobacterium tuberculosis* | Producer of VapC20 |
| Enterobacteriaceae | Family-level record for a T6SS effector |
| *Streptomyces* | Genus-level record for SAIP |

All five are Bacteria. This is the empirical argument for the split above rather than a
preference: the eukaryote side of Open Tree is usable at species level and the
bacterial side is not.

## Higher-rank producers are internal nodes

Not every producer record is a species. SAIP is recorded at the genus *Streptomyces*
and a T6SS effector at the family Enterobacteriaceae, because that is the resolution
the papers support. In `tree_bacteria.nwk` those are labelled internal nodes, so
`reconcile.py` addresses tips and internal nodes alike and a genus-level record
correctly subsumes the species-level records beneath it.

## What reconcile.py computes, and what it does not

For each entity it finds the MRCA of its recorded producers, counts how many catalog
taxa sit inside that MRCA clade, and reports the fraction of them that actually carry
the entity. Low coverage under a deep MRCA is the HGT signature; high coverage under a
shallow one is lineage-restricted.

Two limits, both load-bearing:

**Absence means "not recorded", never "surveyed and absent."** Every count is a lower
bound over the taxa this catalog happens to sample. A real patchiness statistic needs
presence/absence from genome surveys, not from a literature-derived producer list.

**Donors are not producers.** `producer.provenance` distinguishes `de_novo` from
`horizontally_acquired`, and reconciliation uses only the former for distribution,
reporting acquirers separately. Without that split the mosquito RIP entity scored
"pan-domain" purely because the *Wolbachia* donor and the mosquito recipient were both
filed as producers — an artefact, not a finding.

At current coverage the 28 entities score: 20 "single record (not assessable)" because
only one producer is recorded for each; 5 "patchy / HGT signature" (`stx`,
`diphtheria_toxin`, `cdia_ct_trnase`, `kirromycin`, `gamma_toxin`); 2
"lineage-restricted" (`ribotoxin_fungal`, `rip_plant_t1`); and 1 recipient-only
(`rip_whitefly`, whose plant donor is not in the producer table). That is the honest
state and it says what to do next: add producers to existing entities before adding
entities.
