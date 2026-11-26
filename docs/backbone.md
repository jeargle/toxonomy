# The species-tree backbone

`distribution_pattern` is meant to be computed, not asserted. That needs a tree the
producer taxa can be placed on. This is what was built, and what it cannot do.

## Two trees, deliberately

`data/tree_eukaryota.nwk` — Open Tree of Life induced subtree over the eukaryote
producers (plants, fungi, insects, molluscs, amphibians, fish, mammals). A real
phylogeny synthesised from published studies. 25 of 26 placed; the exception is noted
below.

`data/tree_bacteria_archaea.nwk` — an NCBI taxonomy cladogram over the 30 bacterial and
archaeal nodes.
**A placeholder, not a phylogeny.** GTDB is the intended source; its API returned 502
at connect while this was built, so `taxon.gtdb_lineage` is null throughout and
`scripts/build_tree.py` fills it on a later run.

They are not joined. A single rooted tree spanning both would require asserting a
relationship between the Bacteria clade and the Eukaryota clade, and under the
two-domain tree eukaryotes nest within Archaea rather than sitting as a sister group to
Bacteria. The sources here support neither arrangement, so the backbone declines to
choose and cross-domain comparisons run against the two trees separately.

## Open Tree cannot carry the bacteria

Twelve taxa are "broken" on the Open Tree synthetic tree — the taxon concept is present
but not as a node of its own — and are flagged `taxon.ott_broken`. Two more are absent
from it entirely and are flagged `taxon.ott_absent`. Representative cases:

| Taxon | Why it matters |
|---|---|
| *Escherichia coli* | The catalog's most frequent producer; paraphyletic with *Shigella* |
| *Pseudomonas aeruginosa* | Producer of Ribocin and Exotoxin A |
| *Mycobacterium tuberculosis* | Producer of VapC20 |
| Enterobacteriaceae | Family-level record for a T6SS effector |
| *Streptomyces* | Genus-level record for SAIP |
| *Staphylococcus aureus*, *Listeria monocytogenes*, *Streptococcus pneumoniae*, *Clostridium perfringens*, *Bacillus*, *Pseudomonas* | Pore-forming and phospholipase producers added in the second round |
| *Haloferax mediterranei* (absent) | Archaeal halocin producer |
| *Heteroscytonema crispum* (absent) | Cyanobacterial saxitoxin producer |

Eleven of the twelve broken taxa are Bacteria, and both absent taxa go to the
cladogram anyway. This is the empirical argument for the split above rather than a
preference: the eukaryote side of Open Tree is usable at species level and the
bacterial side is not.

The one broken eukaryote is *Alexandrium*, the saxitoxin-producing dinoflagellate. It
has no cladogram fallback, so it is the catalog's only genuinely unplaceable taxon and
`check.py` reports it as such rather than failing. Protists are where the Open Tree
synthesis is thinnest, which is worth knowing before the catalog takes on more of them.

## Higher-rank producers are internal nodes

Not every producer record is a species. SAIP is recorded at the genus *Streptomyces*
and a T6SS effector at the family Enterobacteriaceae, because that is the resolution
the papers support. In `tree_bacteria_archaea.nwk` those are labelled internal nodes, so
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

**Carrying is not making.** `producer.provenance` separates `de_novo` from
`horizontally_acquired`, `sequestered` and `symbiont_derived`; reconciliation scores
distribution on de novo producers only and reports the rest as carriers. Two artefacts
came out of getting this wrong. The mosquito RIP entity scored "pan-domain" because the
*Wolbachia* donor and the mosquito recipient were both filed as producers. Tetrodotoxin
scored "pan-domain" because the pufferfish and the newt were counted as making a toxin
their symbionts make. Corrected, TTX reads as a bacterial product carried by
*Takifugu rubripes* and *Taricha granulosa*, and the one real pan-domain entity left is
saxitoxin, made independently by a dinoflagellate and a cyanobacterium.

At current coverage the 54 entities score: 43 "single record (not assessable)" because
only one de novo producer is recorded for each; 6 "patchy / HGT signature"
(`stx`, `diphtheria_toxin`, `cdia_ct_trnase`, `kirromycin`, `gamma_toxin`,
`cdc_cytolysin`); 2 "lineage-restricted" (`ribotoxin_fungal`, `rip_plant_t1`);
1 pan-domain (`saxitoxin`); and 2 carrier-only (`batrachotoxin`, `rip_whitefly`), whose
de novo producers — a dietary arthropod and a plant — are not in the producer table.
The second round widened the facet space without improving this, so it still says the
same thing: add producers to existing entities before adding entities.
