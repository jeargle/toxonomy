"""Render toxonomy.db as a static, browsable website.

    uv run python scripts/build_site.py [toxonomy.db] [_site]

Every link is relative, so the output works from GitHub Pages under /toxonomy/
and opened straight from disk. The page set:

    index.html            filterable entity table
    entity/<id>.html      one page per entity
    term/<term_id>.html   one page per vocabulary term
    facets.html           the eight facets and their terms
    folds.html            folds, with the entities and producer domains under each
    taxa.html             producer taxa by domain, made versus carried
    references.html       every reference, with the entities that cite it
    about.html            conventions and how to read the pages
    toxonomy.db, toxonomy.json   downloads

Distribution scores come from scripts/reconcile.py, so the site and CI can
never disagree about them.
"""
import html
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconcile  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/jeargle/toxonomy"
FACETS = ["chemical_nature", "molecular_target", "mode_of_action", "delivery",
          "self_protection", "antagonist_relation", "mobility_context",
          "distribution_pattern"]
DOMAINS = ["Bacteria", "Archaea", "Eukaryota", "Virus"]
NAV = [("index.html", "Entities"), ("facets.html", "Facets"), ("folds.html", "Folds"),
       ("taxa.html", "Taxa"), ("references.html", "References"), ("about.html", "About")]
CARRIED = {"horizontally_acquired", "sequestered", "symbiont_derived"}


# ------------------------------------------------------------------ helpers
def esc(value):
    """HTML-escape, rendering None as an empty string."""
    return "" if value is None else html.escape(str(value))


def label(facet):
    """'molecular_target' -> 'Molecular target'."""
    return facet.replace("_", " ").capitalize()


def slug(text):
    """A stable anchor id from free text."""
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    return "-".join(p for p in "".join(keep).split("-") if p)


def clean_pmid(pmid):
    """PMIDs that went through a float column arrive as '41441611.0'."""
    if pmid is None:
        return None
    text = str(pmid)
    return text[:-2] if text.endswith(".0") else text


def rows(conn, sql, *args):
    """All rows of a query as dicts."""
    return [dict(r) for r in conn.execute(sql, args)]


def table(headers, body_rows, cls=""):
    """An HTML table; body_rows are lists of already-escaped cell HTML."""
    if not body_rows:
        return '<p class="none">None recorded.</p>'
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                   for r in body_rows)
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def domain_tag(domain):
    """A coloured badge for a producer domain."""
    if not domain:
        return ""
    return f'<span class="dom dom-{esc(domain.lower())}">{esc(domain)}</span>'


# ------------------------------------------------------------------ loading
def load(conn):
    """Everything the pages need, indexed for lookup."""
    d = {"entities": rows(conn, "SELECT * FROM entity ORDER BY name COLLATE NOCASE"),
         "terms": {t["term_id"]: t for t in rows(conn, "SELECT * FROM cv_term")},
         "refs": {r["ref_id"]: r for r in rows(conn, "SELECT * FROM reference")},
         "taxa": {t["scientific_name"]: t for t in rows(conn, "SELECT * FROM taxon")}}
    d["by_entity"] = {name: group(rows(conn, f"SELECT * FROM {name}"))
                      for name in ["entity_facet", "producer", "homology", "immunity",
                                   "counter_adaptation", "entity_reference"]}
    d["scores"] = {s["entity_id"]: s for s in reconcile.score_all()}
    d["names"] = {e["entity_id"]: e["name"] for e in d["entities"]}
    return d


def group(records):
    """Group rows by entity_id."""
    out = defaultdict(list)
    for r in records:
        out[r["entity_id"]].append(r)
    return out


def facet_terms(d, entity_id):
    """{facet: [(term row, ref_id)]} for one entity, in vocabulary order."""
    out = defaultdict(list)
    for ef in d["by_entity"]["entity_facet"].get(entity_id, []):
        term = d["terms"][ef["term_id"]]
        out[term["facet"]].append((term, ef["ref_id"]))
    for facet in out:
        out[facet].sort(key=lambda pair: pair[0]["term"].lower())
    return out


def made_domains(d, entity_id):
    """Producer domains among de novo (or ambiguous) producers only."""
    prods = d["by_entity"]["producer"].get(entity_id, [])
    return sorted({p["domain"] for p in prods
                   if p["domain"] and p["provenance"] not in CARRIED})


# ------------------------------------------------------------------ links
def ref_link(d, ref_id, root):
    """Citation text linked to its reference entry; '' when uncited."""
    if not ref_id:
        return ""
    ref = d["refs"].get(ref_id)
    text = ref["citation"] if ref else ref_id
    return f'<a href="{root}references.html#{esc(ref_id)}">{esc(text)}</a>'


def term_link(term, root):
    return f'<a href="{root}term/{esc(term["term_id"])}.html">{esc(term["term"])}</a>'


def entity_link(d, entity_id, root):
    return f'<a href="{root}entity/{esc(entity_id)}.html">{esc(d["names"][entity_id])}</a>'


def external_ids(rec):
    """Links out to DOI and PubMed for a reference row."""
    out = []
    if rec.get("doi"):
        out.append(f'<a href="https://doi.org/{esc(rec["doi"])}">doi:{esc(rec["doi"])}</a>')
    pmid = clean_pmid(rec.get("pmid"))
    if pmid:
        out.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{esc(pmid)}/">PMID {esc(pmid)}</a>')
    return " · ".join(out)


def fold_links(h):
    """InterPro / Pfam links for a homology row."""
    out = []
    if h.get("interpro_acc"):
        acc = esc(h["interpro_acc"])
        out.append(f'<a href="https://www.ebi.ac.uk/interpro/entry/InterPro/{acc}/">{acc}</a>')
    if h.get("pfam_acc"):
        acc = esc(h["pfam_acc"])
        out.append(f'<a href="https://www.ebi.ac.uk/interpro/entry/pfam/{acc}/">{acc}</a>')
    return " ".join(out)


# ------------------------------------------------------------------ layout
def page(title, body, root, active=""):
    """Wrap a body in the shared header, nav and footer."""
    nav = "".join(
        f'<a href="{root}{href}"{" class=on" if href == active else ""}>{text}</a>'
        for href, text in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · toxonomy</title>
<link rel="stylesheet" href="{root}style.css"></head>
<body><header><a class="brand" href="{root}index.html">toxonomy</a><nav>{nav}</nav></header>
<main>{body}</main>
<footer>Generated from the CSVs in <a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a>.
Absence in this catalog means <em>not recorded</em>, never <em>surveyed and absent</em>.</footer>
</body></html>
"""


def write(out_dir, rel, text):
    path = out_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# ------------------------------------------------------------------ entity pages
def score_html(score):
    """The computed distribution block for an entity."""
    if not score:
        return '<p class="none">No producer on a backbone; not scored.</p>'
    cov = "–" if score["coverage"] is None else f'{score["coverage"]:.2f}'
    taxa = "taxon" if score["n"] == 1 else "taxa"
    parts = [f'<b>{esc(score["pattern"])}</b>',
             f'{score["n"]} producer {taxa} on the backbone',
             f"coverage of MRCA clade {cov}"]
    if score["domains"]:
        parts.append("made in " + " ".join(domain_tag(x) for x in score["domains"]))
    if score["carried_by"]:
        parts.append("carried, not made, by " + esc(", ".join(score["carried_by"])))
    return "<p>" + "; ".join(parts) + ".</p>"


def fold_domains(d, entity_id):
    """Domains of de novo producers across every entity sharing a fold with this one."""
    folds = {h["fold"] for h in d["by_entity"]["homology"].get(entity_id, [])}
    mates = {eid for eid, hs in d["by_entity"]["homology"].items()
             if any(h["fold"] in folds for h in hs)}
    return {x for eid in mates for x in made_domains(d, eid)}


def assertion_note(d, entity_id):
    """Say how far the rows support a pan-domain facet asserted from the literature."""
    asserted = {t["term"] for t, _ in facet_terms(d, entity_id).get("distribution_pattern", [])}
    if "pan-domain" not in asserted or len(made_domains(d, entity_id)) > 1:
        return ""
    if len(fold_domains(d, entity_id)) > 1:
        return ('<p class="meta">The <code>pan-domain</code> facet is supported at the fold '
                "level: entities sharing this fold are made in more than one domain.</p>")
    return ('<p class="uncited">The <code>pan-domain</code> facet is asserted from the '
            "literature; neither this entity's producer rows nor its fold-mates in the "
            "catalog span more than one domain.</p>")


def facets_section(d, entity_id, root):
    terms = facet_terms(d, entity_id)
    body = []
    for facet in FACETS:
        for term, ref_id in terms.get(facet, []):
            src = ref_link(d, ref_id, root) or '<span class="uncited">uncited</span>'
            body.append([label(facet), term_link(term, root), src])
    return table(["Facet", "Term", "Source"], body, "facets")


def producers_section(d, entity_id, root):
    body = []
    for p in d["by_entity"]["producer"].get(entity_id, []):
        taxon = f'<a href="{root}taxa.html#{slug(p["taxon_name"])}"><i>{esc(p["taxon_name"])}</i></a>'
        prov = esc(p["provenance"].replace("_", " "))
        body.append([taxon, domain_tag(p["domain"]), prov, esc(p["lineage_note"]),
                     ref_link(d, p["ref_id"], root)])
    return table(["Taxon", "Domain", "Provenance", "Lineage", "Source"], body)


def folds_section(d, entity_id, root):
    body = [[f'<a href="{root}folds.html#{slug(h["fold"])}">{esc(h["fold"])}</a>',
             fold_links(h), esc(h["note"])]
            for h in d["by_entity"]["homology"].get(entity_id, [])]
    return table(["Fold", "Accessions", "Note"], body)


def immunity_section(d, entity_id, root):
    body = [[esc(i["immunity_name"]), esc(i["immunity_fold"]),
             esc((i["mechanism"] or "").replace("_", " ")), ref_link(d, i["ref_id"], root)]
            for i in d["by_entity"]["immunity"].get(entity_id, [])]
    return table(["Name", "Fold", "Mechanism", "Source"], body)


def counter_section(d, entity_id, root):
    body = [[f'<i>{esc(c["taxon_name"])}</i>', esc((c["mechanism"] or "").replace("_", " ")),
             esc(c["note"]), ref_link(d, c["ref_id"], root)]
            for c in d["by_entity"]["counter_adaptation"].get(entity_id, [])]
    return table(["Target lineage", "Mechanism", "Note", "Source"], body)


def refs_section(d, entity_id, root):
    body = []
    for er in d["by_entity"]["entity_reference"].get(entity_id, []):
        ref = d["refs"].get(er["ref_id"], {})
        body.append([esc(er["role"]), ref_link(d, er["ref_id"], root),
                     esc(ref.get("title")), external_ids(ref)])
    return table(["Role", "Citation", "Title", "Links"], body)


def entity_page(d, e):
    root = "../"
    eid = e["entity_id"]
    aka = f'<p class="aka">Also: {esc(e["aka"])}</p>' if e["aka"] else ""
    sections = [("Facets", facets_section), ("Producers", producers_section),
                ("Folds", folds_section), ("Self-protection", immunity_section),
                ("Counter-adaptations", counter_section), ("References", refs_section)]
    body = [f'<h1>{esc(e["name"])}</h1>', aka,
            f'<p class="meta"><code>{esc(eid)}</code> · {esc(e["unit_type"].replace("_", " "))}</p>',
            f'<p>{esc(e["description"])}</p>',
            "<h2>Distribution, computed from producer rows</h2>",
            score_html(d["scores"].get(eid)), assertion_note(d, eid)]
    for title, fn in sections:
        body += [f"<h2>{title}</h2>", fn(d, eid, root)]
    return page(e["name"], "\n".join(body), root)


# ------------------------------------------------------------------ index
def index_row(d, e):
    """One filterable row of the entity table."""
    eid = e["entity_id"]
    terms = facet_terms(d, eid)
    score = d["scores"].get(eid, {})
    cells = {f: "; ".join(t["term"] for t, _ in terms.get(f, []))
             for f in ["chemical_nature", "molecular_target", "mode_of_action"]}
    doms = made_domains(d, eid)
    attrs = {"chem": "|".join(t["term"] for t, _ in terms.get("chemical_nature", [])),
             "target": "|".join(t["term"] for t, _ in terms.get("molecular_target", [])),
             "domain": "|".join(doms), "pattern": score.get("pattern", "not scored"),
             "text": " ".join([e["name"], e["aka"] or "", e["description"] or "",
                               *cells.values()]).lower()}
    data = " ".join(f'data-{k}="{esc(v)}"' for k, v in attrs.items())
    return (f"<tr {data}><td>{entity_link(d, eid, '')}</td>"
            f"<td>{esc(cells['chemical_nature'])}</td><td>{esc(cells['molecular_target'])}</td>"
            f"<td>{esc(cells['mode_of_action'])}</td>"
            f"<td>{' '.join(domain_tag(x) for x in doms)}</td>"
            f"<td>{esc(attrs['pattern'])}</td></tr>")


def select(name, title, values):
    opts = "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted(values))
    return f'<label>{title} <select data-filter="{name}"><option value="">any</option>{opts}</select></label>'


def index_page(d, counts):
    def used(facet):
        return {t["term"] for t in d["terms"].values() if t["facet"] == facet}
    patterns = {s["pattern"] for s in d["scores"].values()} | {"not scored"}
    filters = "".join([
        '<label>Search <input type="search" data-filter="text" placeholder="name, target, mode…"></label>',
        select("chem", "Chemistry", used("chemical_nature")),
        select("target", "Target", used("molecular_target")),
        select("domain", "Made in", [x for x in DOMAINS if x != "Virus"]),
        select("pattern", "Distribution", patterns)])
    stats = " · ".join(f"{n} {k}" for k, n in counts.items())
    rows_html = "".join(index_row(d, e) for e in d["entities"])
    body = f"""<h1>A clade-neutral catalog of biological antagonists</h1>
<p class="lede">Protein toxins, specialized metabolites including antibiotics, and the defense
systems that deploy them, organized by what a molecule is, what it attacks, and how its
producer survives it. Producer taxonomy is metadata on every row and a partition key on none.</p>
<p class="meta">{stats}</p>
<div class="filters">{filters}</div>
<p class="meta"><span id="shown"></span></p>
<table id="entities" class="sortable"><thead><tr><th>Entity</th><th>Chemistry</th>
<th>Target</th><th>Mode of action</th><th>Made in</th><th>Distribution</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<script src="filter.js"></script>"""
    return page("Entities", body, "", "index.html")


# ------------------------------------------------------------------ term and facet pages
def entities_with_term(d, term_id):
    return sorted({ef["entity_id"] for efs in d["by_entity"]["entity_facet"].values()
                   for ef in efs if ef["term_id"] == term_id},
                  key=lambda x: d["names"][x].lower())


def term_page(d, t):
    root = "../"
    ents = entities_with_term(d, t["term_id"])
    ext = esc(t["external_id"]) if t["external_id"] else ""
    src = f' ({esc(t["external_source"])}{" " + ext if ext else ""})' if t["external_source"] else ""
    body = [f'<p class="meta"><a href="{root}facets.html#{t["facet"]}">{label(t["facet"])}</a></p>',
            f'<h1>{esc(t["term"])}</h1>', f'<p>{esc(t["definition"])}{src}</p>',
            f"<h2>{len(ents)} entities</h2>",
            table(["Entity", "Made in"],
                  [[entity_link(d, x, root), " ".join(domain_tag(y) for y in made_domains(d, x))]
                   for x in ents])]
    return page(t["term"], "\n".join(body), root)


def facets_page(d):
    body = ['<h1>Facets</h1><p>Eight facets, one controlled vocabulary each. '
            'Terms with no entity yet are listed in grey.</p>']
    for facet in FACETS:
        terms = sorted((t for t in d["terms"].values() if t["facet"] == facet),
                       key=lambda t: t["term"].lower())
        items = []
        for t in terms:
            n = len(entities_with_term(d, t["term_id"]))
            cls = "" if n else ' class="unused"'
            items.append(f'<li{cls}>{term_link(t, "")} <span class="n">{n}</span></li>')
        body.append(f'<h2 id="{facet}">{label(facet)}</h2><ul class="terms">{"".join(items)}</ul>')
    return page("Facets", "\n".join(body), "", "facets.html")


# ------------------------------------------------------------------ folds, taxa, references
def folds_page(d):
    by_fold = defaultdict(list)
    for eid, hs in d["by_entity"]["homology"].items():
        for h in hs:
            by_fold[h["fold"]].append((eid, h))
    body = ["<h1>Folds</h1><p>Each fold with the entities that carry it and the domains "
            "their de novo producers sit in. A fold spanning domains on its own rows is "
            "the evidence the catalog can offer; a facet asserting it is not.</p>"]
    for fold in sorted(by_fold, key=str.lower):
        members = sorted(by_fold[fold], key=lambda p: d["names"][p[0]].lower())
        doms = sorted({x for eid, _ in members for x in made_domains(d, eid)})
        rows_html = [[entity_link(d, eid, ""), fold_links(h),
                      " ".join(domain_tag(x) for x in made_domains(d, eid))]
                     for eid, h in members]
        body.append(f'<h2 id="{slug(fold)}">{esc(fold)} <span class="n">{len(members)}</span> '
                    f'{" ".join(domain_tag(x) for x in doms)}</h2>'
                    + table(["Entity", "Accessions", "Made in"], rows_html))
    return page("Folds", "\n".join(body), "", "folds.html")


def taxon_entities(d):
    """{taxon_name: [(entity_id, provenance)]}."""
    out = defaultdict(list)
    for eid, prods in d["by_entity"]["producer"].items():
        for p in prods:
            out[p["taxon_name"]].append((eid, p["provenance"]))
    return out


def taxon_links(t):
    out = []
    if t.get("ncbi_taxid"):
        out.append(f'<a href="https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={t["ncbi_taxid"]}">NCBI {t["ncbi_taxid"]}</a>')
    if t.get("ott_id"):
        out.append(f'<a href="https://tree.opentreeoflife.org/taxonomy/browse?id={t["ott_id"]}">OTT {t["ott_id"]}</a>')
    return " · ".join(out)


def taxon_row(d, name, entries):
    t = d["taxa"].get(name, {})
    made = [entity_link(d, e, "") for e, p in entries if p not in CARRIED]
    carried = [entity_link(d, e, "") + f' <span class="n">{esc(p.replace("_", " "))}</span>'
               for e, p in entries if p in CARRIED]
    note = ' <span class="uncited">not on a backbone</span>' if t.get("ott_broken") or t.get("ott_absent") else ""
    return [f'<i id="{slug(name)}">{esc(name)}</i>{note}', esc(t.get("rank")),
            "<br>".join(made), "<br>".join(carried), taxon_links(t)]


def taxa_page(d):
    by_taxon = taxon_entities(d)
    body = ["<h1>Producer taxa</h1><p>Grouped by domain for navigation only. "
            "<em>Makes</em> counts de novo producers; <em>carries</em> covers horizontally "
            "acquired, sequestered and symbiont-derived records, which distribution scoring "
            "excludes.</p>"]
    for dom in DOMAINS:
        names = sorted(n for n in by_taxon
                       if (d["taxa"].get(n, {}).get("domain") or producer_domain(d, n)) == dom)
        if not names:
            continue
        body.append(f"<h2>{domain_tag(dom)} {len(names)}</h2>"
                    + table(["Taxon", "Rank", "Makes", "Carries", "Links"],
                            [taxon_row(d, n, by_taxon[n]) for n in names]))
    return page("Taxa", "\n".join(body), "", "taxa.html")


def producer_domain(d, taxon_name):
    """Domain from producer rows, for taxa without a taxon-table row."""
    for prods in d["by_entity"]["producer"].values():
        for p in prods:
            if p["taxon_name"] == taxon_name and p["domain"]:
                return p["domain"]
    return None


def citing_entities(d):
    """{ref_id: set(entity_id)} across every table that cites a reference."""
    out = defaultdict(set)
    for name in ["entity_facet", "producer", "immunity", "counter_adaptation", "entity_reference"]:
        for eid, recs in d["by_entity"][name].items():
            for r in recs:
                if r.get("ref_id"):
                    out[r["ref_id"]].add(eid)
    return out


def references_page(d):
    cites = citing_entities(d)
    items = []
    for ref in sorted(d["refs"].values(), key=lambda r: (r["citation"].lower(), r["ref_id"])):
        pre = ' <span class="uncited">preprint</span>' if ref["is_preprint"] else ""
        ents = ", ".join(entity_link(d, e, "") for e in
                         sorted(cites.get(ref["ref_id"], ()), key=lambda x: d["names"][x].lower()))
        items.append(f'<li id="{esc(ref["ref_id"])}"><b>{esc(ref["citation"])}</b>{pre}. '
                     f'{esc(ref["title"])} <i>{esc(ref["journal"])}</i>. {external_ids(ref)}'
                     f'<div class="cites">{ents}</div></li>')
    body = f'<h1>References</h1><ol class="refs">{"".join(items)}</ol>'
    return page("References", body, "", "references.html")


def about_page(counts):
    stats = "".join(f"<li>{n} {k}</li>" for k, n in counts.items())
    body = f"""<h1>About</h1>
<p>toxonomy is a taxonomy of toxins that refuses producer taxonomy as its organizing axis.
Source and issues: <a href="{REPO_URL}">{REPO_URL}</a>.</p>
<h2>Reading the pages</h2>
<ul>
<li><b>Uncited</b> marks a facet assignment with no reference behind it yet: a defensible
reading, not a cited finding.</li>
<li><b>Made in</b> counts only de novo producers. Organisms that acquired the genes, host a
symbiont that makes the molecule, or sequester it from the diet carry it without making it.</li>
<li><b>Distribution</b> is computed by <code>scripts/reconcile.py</code> against two species
trees that are never joined: Open Tree of Life for eukaryotes and an NCBI cladogram for
Bacteria and Archaea. Counts are lower bounds over the taxa the catalog samples. A single
recorded producer is not assessable.</li>
<li>The <code>distribution_pattern</code> facet is an assertion from the literature; the
computed distribution is what the rows support. Where they disagree, the rows win.</li>
</ul>
<h2>Downloads</h2>
<ul><li><a href="toxonomy.db">toxonomy.db</a> (SQLite)</li>
<li><a href="toxonomy.json">toxonomy.json</a> (every table, as row lists)</li></ul>
<h2>Contents</h2><ul>{stats}</ul>"""
    return page("About", body, "", "about.html")


# ------------------------------------------------------------------ static assets
CSS = """
:root{--fg:#1d2327;--mute:#5f6b73;--line:#dde3e7;--bg:#fff;--accent:#1f5f8b;
--bac:#d9ecf7;--arc:#f7e6cf;--euk:#dff1df;--vir:#eee}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,sans-serif;color:var(--fg);background:var(--bg)}
header{display:flex;gap:1.5rem;align-items:baseline;padding:.8rem 1.5rem;border-bottom:1px solid var(--line);flex-wrap:wrap}
.brand{font-weight:700;font-size:1.2rem;color:var(--fg);text-decoration:none}
nav a{margin-right:1rem;color:var(--mute);text-decoration:none}nav a.on,nav a:hover{color:var(--accent)}
main{max-width:1150px;margin:0 auto;padding:1rem 1.5rem 3rem}footer{color:var(--mute);font-size:.85rem;padding:1rem 1.5rem;border-top:1px solid var(--line)}
a{color:var(--accent)}h1{font-size:1.6rem;margin:.6rem 0}h2{font-size:1.15rem;margin-top:1.8rem;border-bottom:1px solid var(--line);padding-bottom:.2rem}
.lede{max-width:52rem}.meta,.aka,.n,.none{color:var(--mute)}.n{font-size:.85em}
table{border-collapse:collapse;width:100%;margin:.4rem 0;font-size:.92rem}
th,td{text-align:left;vertical-align:top;padding:.35rem .5rem;border-bottom:1px solid var(--line)}
th{font-weight:600;background:#f6f8f9;position:sticky;top:0}
.sortable th{cursor:pointer;user-select:none}.sortable th:hover{color:var(--accent)}
.dom{display:inline-block;padding:0 .4rem;border-radius:.6rem;font-size:.8rem;margin-right:.2rem}
.dom-bacteria{background:var(--bac)}.dom-archaea{background:var(--arc)}.dom-eukaryota{background:var(--euk)}.dom-virus{background:var(--vir)}
.uncited{color:#9a6b00;font-size:.85em}
.filters{display:flex;flex-wrap:wrap;gap:.6rem 1.2rem;margin:1rem 0 .3rem}
.filters label{font-size:.9rem;color:var(--mute)}.filters input,.filters select{font:inherit;padding:.2rem .3rem;max-width:16rem}
ul.terms{columns:3 16rem;padding-left:1.2rem}ul.terms li.unused a{color:var(--mute)}
ol.refs li{margin-bottom:.7rem}.cites{font-size:.85rem;color:var(--mute)}
"""

FILTER_JS = """
(function(){
  var rows=[].slice.call(document.querySelectorAll('#entities tbody tr'));
  var ctl=[].slice.call(document.querySelectorAll('[data-filter]'));
  var shown=document.getElementById('shown');
  function match(r){
    return ctl.every(function(c){
      var v=c.value.trim().toLowerCase(), k=c.dataset.filter;
      if(!v) return true;
      var have=(r.dataset[k]||'').toLowerCase();
      return k==='text' ? have.indexOf(v)>=0 : have.split('|').indexOf(v)>=0;
    });
  }
  function apply(){
    var n=0;
    rows.forEach(function(r){var ok=match(r);r.style.display=ok?'':'none';if(ok)n++;});
    shown.textContent=n+' of '+rows.length+' entities shown';
  }
  ctl.forEach(function(c){c.addEventListener('input',apply);});
  var tbody=document.querySelector('#entities tbody');
  [].slice.call(document.querySelectorAll('#entities th')).forEach(function(th,i){
    var asc=true;
    th.addEventListener('click',function(){
      rows.sort(function(a,b){
        var x=a.cells[i].textContent.toLowerCase(), y=b.cells[i].textContent.toLowerCase();
        return (x<y?-1:x>y?1:0)*(asc?1:-1);
      });
      asc=!asc; rows.forEach(function(r){tbody.appendChild(r);});
    });
  });
  apply();
})();
"""


# ------------------------------------------------------------------ build
def dump_json(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: rows(conn, f"SELECT * FROM {t}") for t in tables}


def build(db_path, out_dir):
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    d = load(conn)
    counts = {"entities": len(d["entities"]),
              "producer records": sum(len(v) for v in d["by_entity"]["producer"].values()),
              "taxa": len(d["taxa"]), "references": len(d["refs"])}
    write(out_dir, "style.css", CSS)
    write(out_dir, "filter.js", FILTER_JS)
    write(out_dir, "index.html", index_page(d, counts))
    write(out_dir, "facets.html", facets_page(d))
    write(out_dir, "folds.html", folds_page(d))
    write(out_dir, "taxa.html", taxa_page(d))
    write(out_dir, "references.html", references_page(d))
    write(out_dir, "about.html", about_page(counts))
    for e in d["entities"]:
        write(out_dir, f"entity/{e['entity_id']}.html", entity_page(d, e))
    for t in d["terms"].values():
        write(out_dir, f"term/{t['term_id']}.html", term_page(d, t))
    write(out_dir, "toxonomy.json", json.dumps(dump_json(conn), indent=1))
    conn.close()
    shutil.copyfile(db_path, out_dir / "toxonomy.db")
    return sum(1 for _ in out_dir.rglob("*.html"))


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "toxonomy.db")
    out = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "_site")
    print(f"wrote {build(db, out)} pages to {out}")
