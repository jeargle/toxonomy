-- toxonomy: a clade-neutral catalog of biological molecules that attack other biological systems.
-- Producer taxonomy is metadata on every row and a partition key on none.
-- SQLite dialect; portable to Postgres by swapping INTEGER PRIMARY KEY for SERIAL/IDENTITY.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- references
CREATE TABLE reference (
    ref_id      TEXT PRIMARY KEY,          -- short key, e.g. 'gucinski2019'
    citation    TEXT NOT NULL,             -- 'Gucinski et al. 2019'
    title       TEXT,
    year        INTEGER,
    journal     TEXT,
    doi         TEXT,
    pmid        TEXT,
    is_preprint INTEGER NOT NULL DEFAULT 0 CHECK (is_preprint IN (0,1))
);

-- ------------------------------------------------------------------ entities
-- Three unit types that do not merge cleanly into one row shape:
--   gene_family  a toxin protein family (the molecule is an instance)
--   bgc          a biosynthetic gene cluster (the molecule is its product)
--   compound     a small molecule whose producing genes are unknown or in another taxon
CREATE TABLE entity (
    entity_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    unit_type   TEXT NOT NULL CHECK (unit_type IN ('gene_family','bgc','compound')),
    aka         TEXT,
    description TEXT
);

-- ------------------------------------------------------- controlled vocabulary
-- One table for every facet. external_id points at GO / ChEBI / InterPro / SO
-- where a public term exists; local terms are minted only where none does.
CREATE TABLE cv_term (
    term_id         TEXT PRIMARY KEY,
    facet           TEXT NOT NULL CHECK (facet IN (
                        'chemical_nature','molecular_target','mode_of_action',
                        'delivery','self_protection','antagonist_relation',
                        'mobility_context','distribution_pattern')),
    term            TEXT NOT NULL,
    definition      TEXT,
    external_id     TEXT,
    external_source TEXT CHECK (external_source IN ('GO','ChEBI','InterPro','SO','local')),
    UNIQUE (facet, term)
);

CREATE TABLE entity_facet (
    entity_id TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    term_id   TEXT NOT NULL REFERENCES cv_term(term_id),
    ref_id    TEXT REFERENCES reference(ref_id),
    PRIMARY KEY (entity_id, term_id)
);

-- --------------------------------------------------------------------- taxa
-- The species-tree backbone's node table. gtdb_lineage is nullable: the GTDB
-- API was unreachable at build time and scripts/build_tree.py fills it when up.
-- ott_broken marks taxa that are NOT nodes in the Open Tree synthetic tree
-- (e.g. Escherichia coli, paraphyletic with Shigella) and so cannot be placed
-- on the Open Tree backbone at all.
CREATE TABLE taxon (
    ncbi_taxid      INTEGER PRIMARY KEY,
    scientific_name TEXT NOT NULL UNIQUE,
    rank            TEXT,
    domain          TEXT CHECK (domain IN ('Bacteria','Archaea','Eukaryota','Virus')),
    ncbi_lineage    TEXT,
    gtdb_lineage    TEXT,
    ott_id          INTEGER,
    ott_broken      INTEGER NOT NULL DEFAULT 0 CHECK (ott_broken IN (0,1)),
    -- ott_absent: not present in the Open Tree synthetic tree at all (vs
    -- ott_broken, which is present but not as a node of its own).
    ott_absent      INTEGER NOT NULL DEFAULT 0 CHECK (ott_absent IN (0,1))
);

-- ------------------------------------------------------------------ producers
-- Many producers per entity. provenance separates making it from carrying it.
CREATE TABLE producer (
    producer_id  INTEGER PRIMARY KEY,
    entity_id    TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    taxon_name   TEXT NOT NULL,
    ncbi_taxid   INTEGER REFERENCES taxon(ncbi_taxid),
    domain       TEXT CHECK (domain IN ('Bacteria','Archaea','Eukaryota','Virus')),
    lineage_note TEXT,
    provenance   TEXT NOT NULL CHECK (provenance IN
                     ('de_novo','sequestered','symbiont_derived','horizontally_acquired','ambiguous')),
    ref_id       TEXT REFERENCES reference(ref_id)
);

-- ------------------------------------------------------------------- homology
CREATE TABLE homology (
    homology_id  INTEGER PRIMARY KEY,
    entity_id    TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    fold         TEXT NOT NULL,
    interpro_acc TEXT,
    pfam_acc     TEXT,
    note         TEXT
);

-- -------------------------------------------------------------------- immunity
-- Recorded separately from self_protection facet so that the FOLD of the
-- immunity protein can be compared against the FOLD of the toxin. Unrelated
-- immunity folds flanking similar toxin folds is the convergence test.
CREATE TABLE immunity (
    immunity_id   INTEGER PRIMARY KEY,
    entity_id     TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    immunity_name TEXT,
    immunity_fold TEXT,
    mechanism     TEXT CHECK (mechanism IN
                      ('immunity_protein','target_modification','target_replacement',
                       'drug_modification','ribosomal_protection','repair','efflux',
                       'sequestration','none_required','unknown')),
    ref_id        TEXT REFERENCES reference(ref_id)
);

-- ----------------------------------------------------------- counter-adaptation
-- The other half of every arms race: what the target lineage evolved in reply.
CREATE TABLE counter_adaptation (
    ca_id      INTEGER PRIMARY KEY,
    entity_id  TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    taxon_name TEXT NOT NULL,
    mechanism  TEXT CHECK (mechanism IN
                   ('target_site_substitution','target_modification','repair',
                    'binding_protein','metabolic_detox','surveillance_response',
                    'evasion_of_recognition','behavioural','unknown')),
    note       TEXT,
    ref_id     TEXT REFERENCES reference(ref_id)
);

CREATE TABLE entity_reference (
    entity_id TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    ref_id    TEXT NOT NULL REFERENCES reference(ref_id),
    role      TEXT CHECK (role IN ('primary','mechanism','evolution','review')),
    PRIMARY KEY (entity_id, ref_id, role)
);

CREATE INDEX idx_taxon_domain     ON taxon(domain);
CREATE INDEX idx_producer_entity  ON producer(entity_id);
CREATE INDEX idx_producer_domain  ON producer(domain);
CREATE INDEX idx_facet_term       ON entity_facet(term_id);
CREATE INDEX idx_homology_fold    ON homology(fold);
CREATE INDEX idx_immunity_fold    ON immunity(immunity_fold);

-- --------------------------------------------------------------------- views
-- Wide view: one row per entity with its facet values pivoted into columns.
CREATE VIEW v_entity_facets AS
SELECT e.entity_id, e.name, e.unit_type,
       GROUP_CONCAT(CASE WHEN c.facet='molecular_target'    THEN c.term END, '; ') AS targets,
       GROUP_CONCAT(CASE WHEN c.facet='mode_of_action'      THEN c.term END, '; ') AS modes,
       GROUP_CONCAT(CASE WHEN c.facet='chemical_nature'     THEN c.term END, '; ') AS chemistry,
       GROUP_CONCAT(CASE WHEN c.facet='delivery'            THEN c.term END, '; ') AS delivery,
       GROUP_CONCAT(CASE WHEN c.facet='self_protection'     THEN c.term END, '; ') AS self_protection,
       GROUP_CONCAT(CASE WHEN c.facet='antagonist_relation' THEN c.term END, '; ') AS antagonists
FROM entity e
LEFT JOIN entity_facet ef ON ef.entity_id = e.entity_id
LEFT JOIN cv_term c       ON c.term_id    = ef.term_id
GROUP BY e.entity_id;

-- Convergence candidates: entities sharing a molecular target but no shared fold.
CREATE VIEW v_target_convergence AS
SELECT t.term AS target, a.entity_id AS entity_a, b.entity_id AS entity_b,
       ha.fold AS fold_a, hb.fold AS fold_b
FROM entity_facet fa
JOIN cv_term t      ON t.term_id = fa.term_id AND t.facet = 'molecular_target'
JOIN entity_facet fb ON fb.term_id = fa.term_id AND fb.entity_id > fa.entity_id
JOIN entity a       ON a.entity_id = fa.entity_id
JOIN entity b       ON b.entity_id = fb.entity_id
JOIN homology ha    ON ha.entity_id = a.entity_id
JOIN homology hb    ON hb.entity_id = b.entity_id
WHERE ha.fold <> hb.fold;
