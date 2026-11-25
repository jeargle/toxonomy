-- toxonomy: queries the facet scheme exists to answer.

-- Q1. Convergence on a target: distinct folds per molecular target,
--     with the producer domains those folds are drawn from.
SELECT c.term AS target,
       COUNT(DISTINCT h.fold)          AS n_folds,
       COUNT(DISTINCT e.entity_id)     AS n_entities,
       GROUP_CONCAT(DISTINCT h.fold)   AS folds,
       GROUP_CONCAT(DISTINCT p.domain) AS producer_domains
FROM entity e
JOIN entity_facet ef ON ef.entity_id = e.entity_id
JOIN cv_term c       ON c.term_id = ef.term_id AND c.facet = 'molecular_target'
LEFT JOIN homology h ON h.entity_id = e.entity_id
LEFT JOIN producer p ON p.entity_id = e.entity_id
GROUP BY c.term
ORDER BY n_folds DESC;

-- Q2. The convergence test: same toxin fold, unrelated immunity folds.
SELECT h.fold, e.name, i.immunity_name, i.immunity_fold
FROM homology h
JOIN entity e   ON e.entity_id = h.entity_id
JOIN immunity i ON i.entity_id = h.entity_id AND i.mechanism = 'immunity_protein'
WHERE h.fold IN (SELECT fold FROM homology GROUP BY fold HAVING COUNT(*) > 1)
ORDER BY h.fold, e.name;

-- Q3. Clade neutrality audit: entity counts per producer domain per target.
SELECT c.term AS target, p.domain, COUNT(DISTINCT e.entity_id) AS n
FROM entity e
JOIN entity_facet ef ON ef.entity_id = e.entity_id
JOIN cv_term c       ON c.term_id = ef.term_id AND c.facet = 'molecular_target'
JOIN producer p      ON p.entity_id = e.entity_id
GROUP BY c.term, p.domain
ORDER BY c.term, p.domain;

-- Q4. Self-protection strategy by chemical nature (protein toxins vs metabolites).
SELECT cn.term AS chemistry, sp.term AS self_protection, COUNT(*) AS n
FROM entity_facet f1
JOIN cv_term cn ON cn.term_id = f1.term_id AND cn.facet = 'chemical_nature'
JOIN entity_facet f2 ON f2.entity_id = f1.entity_id
JOIN cv_term sp ON sp.term_id = f2.term_id AND sp.facet = 'self_protection'
GROUP BY cn.term, sp.term
ORDER BY cn.term, n DESC;
