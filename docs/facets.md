# Facets

Eight axes. None is producer taxonomy. Every entity may take more than one value on
any axis, so all of them are many-to-many (`entity_facet`). Terms carry a GO, ChEBI
or InterPro accession wherever a public term exists; `external_source = 'local'`
marks a term minted here because no public one covers it.

| Facet | Question it answers | Example values |
|---|---|---|
| `chemical_nature` | What kind of molecule is it? | protein, RiPP, non-ribosomal peptide, polyketide, terpenoid, alkaloid, nucleic acid |
| `molecular_target` | What does it attack? | sarcin/ricin loop, decoding centre, helix 69, tRNA anticodon loop, eEF2 diphthamide, EF-Tu |
| `mode_of_action` | How does it act? | rRNA N-glycosylase, endoribonuclease, mono-ADP-ribosyltransferase, stoichiometric binding, host-factor-assisted, abortive infection |
| `delivery` | How does it reach the target? | diffusible, type VI secretion, contact-dependent inhibition, receptor-mediated import, intracellular, symbiont-borne |
| `self_protection` | How does the producer survive it? | immunity protein, target modification, target replacement, drug modification, ribosomal protection, repair, latency, none required |
| `antagonist_relation` | Who is it aimed at? | competitor, phage, predator, parasite, host, herbivore, non-specific |
| `mobility_context` | Where is it encoded? | chromosomal core, defence island, plasmid, prophage, ICE, virus-like element, biosynthetic gene cluster |
| `distribution_pattern` | How is it distributed on the species tree? | vertical, patchy/HGT signature, lineage-restricted, pan-domain |

## Axes deliberately excluded

**Producer taxonomy.** Recorded in full on `producer` — NCBI taxid, domain, lineage
note — and joined wherever it is needed, but never a partition. The reason is visible
in the seed data: partitioning the sarcin/ricin-loop attackers by producer separates
ricin from Shiga toxin, which share a fold, and groups ricin with unrelated plant
lectins, which do not.

**Defense versus offense.** The same molecule is defensive for the producer and
offensive from the recipient's side, and VapC20 — which cleaves the sarcin/ricin loop
of its own ribosome — satisfies neither label. `antagonist_relation` captures what the
distinction was reaching for without the contradiction.

## Why homology and immunity are separate tables

`homology.fold` records what the toxin *is*; the facets record what it *does*. Rows
where these disagree are the convergence catalog. `immunity.immunity_fold` is recorded
separately again so that the toxin fold and the immunity fold can be compared: since
toxin and immunity genes evolve as a linked pair, similar toxin folds flanked by
unrelated immunity folds is evidence of convergence rather than common descent. No
public database records that pairing as a field.

## Provenance, not just production

`producer.provenance` separates making a toxin from carrying it: `de_novo`,
`sequestered`, `symbiont_derived`, `horizontally_acquired`, `ambiguous`. A pufferfish
and a *Spiroplasma*-protected fly both "have" a toxin that their own genome does not
encode, and an origin question asked of the wrong taxon has no answer.
