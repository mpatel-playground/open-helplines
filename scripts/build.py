#!/usr/bin/env python3
"""Build the static JSON API, site, and coverage artifacts into dist/ (published to GitHub Pages).

    python3 scripts/build.py

Output:
    dist/v1/index.json            list of countries with counts
    dist/v1/all.json              every country in one file
    dist/v1/countries/<CC>.json   one country
    dist/v1/badge.json            Shields.io endpoint JSON badge
    dist/index.html               the human-facing lookup page
    dist/coverage.md              Markdown coverage table by country
    dist/badge.svg                SVG coverage badge
"""
import datetime as dt
import json
import math
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "countries"
DIST = ROOT / "dist"
SCHEMA_VERSION = 1
REPO_URL = "https://github.com/mpatel-playground/open-helplines"

_NARROW_CHARS = set("ilI|!.,:;·'\"")
_SLIM_CHARS = set(" fjrt()[]")
_WIDE_CHARS = set("mwMW@%&")


def _plural(count, singular, plural):
    return singular if count == 1 else plural


def _format_badge_message(countries_count, helplines_count, verified_count):
    c_word = _plural(countries_count, "country", "countries")
    h_word = _plural(helplines_count, "helpline", "helplines")
    return f"{countries_count} {c_word} · {helplines_count} {h_word} ({verified_count} verified)"


def _badge_color(helplines_count, verified_count):
    if helplines_count <= 0:
        return "lightgrey", "#9f9f9f"
    if verified_count >= helplines_count:
        return "brightgreen", "#2ea44f"
    if verified_count > 0:
        return "yellowgreen", "#97ca00"
    return "blue", "#007ec6"


def _badge_text_width(text):
    """Estimate Verdana 11px text width in pixels plus horizontal padding."""
    width = 0.0
    for ch in text:
        if ch in _NARROW_CHARS:
            width += 3.6
        elif ch in _SLIM_CHARS:
            width += 4.5
        elif ch in _WIDE_CHARS:
            width += 9.8
        elif ch.isupper():
            width += 8.0
        elif ch.isascii():
            width += 6.8
        else:
            width += 7.5
    return math.ceil(width) + 12


def _country_status(helplines_count, verified_count):
    if helplines_count == 0:
        return "No helplines"
    if verified_count >= helplines_count:
        return "Verified"
    if verified_count > 0:
        return "Partially verified"
    return "Provisional"


def _md_cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_coverage_markdown(index):
    """Render a per-country Markdown coverage table and contribution links."""
    countries_count = len(index)
    helplines_count = sum(c["helplines"] for c in index)
    verified_count = sum(c["verified"] for c in index)
    provisional_count = helplines_count - verified_count

    c_word = _plural(countries_count, "country", "countries")
    h_word = _plural(helplines_count, "helpline", "helplines")

    lines = [
        "# Open Helplines Coverage",
        "",
        f"**{countries_count} {c_word}** · **{helplines_count} {h_word}** "
        f"({verified_count} verified, {provisional_count} provisional)",
        "",
        f"Generated from [`data/countries/`]({REPO_URL}/tree/main/data/countries). "
        "Every helpline requires a verbatim source quote; `verified` entries are "
        "confirmed by two or more independent websites.",
        "",
        "| Country | Code | Helplines | Verified | Provisional | Emergency | Status |",
        "|---|---|---|---|---|---|---|",
    ]

    for c in sorted(index, key=lambda item: item["country"]):
        total_hl = c["helplines"]
        verified = c["verified"]
        provisional = total_hl - verified
        emergency = ", ".join(c.get("emergency") or []) or "—"
        status = _country_status(total_hl, verified)
        lines.append(
            f"| {_md_cell(c['name'])} | {_md_cell(c['country'])} | "
            f"{total_hl} | {verified} | {provisional} | "
            f"{_md_cell(emergency)} | {status} |"
        )

    lines.extend([
        "",
        "## Help expand coverage",
        "",
        f"- **Add a missing country:** browse open [`country-data`]({REPO_URL}/issues?q=is%3Aopen+label%3Acountry-data) issues or read [`CONTRIBUTING.md`]({REPO_URL}/blob/main/CONTRIBUTING.md).",
        f"- **Verify a provisional helpline:** add a second independent source on [`needs-second-source`]({REPO_URL}/issues?q=is%3Aopen+label%3Aneeds-second-source) issues.",
        "",
    ])
    return "\n".join(lines)


def render_coverage_badge_svg(countries_count, helplines_count, verified_count):
    """Render a self-contained Shields-style SVG coverage badge."""
    label = "coverage"
    message = _format_badge_message(countries_count, helplines_count, verified_count)
    _, color_hex = _badge_color(helplines_count, verified_count)

    left_w = _badge_text_width(label)
    right_w = _badge_text_width(message)
    total_w = left_w + right_w
    left_x = left_w * 5
    right_x = left_w * 10 + right_w * 5

    esc_label = xml_escape(label, {'"': "&quot;"})
    esc_msg = xml_escape(message, {'"': "&quot;"})
    esc_title = xml_escape(f"{label}: {message}", {'"': "&quot;"})

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" '
        f'viewBox="0 0 {total_w} 20" role="img" aria-label="{esc_title}">\n'
        f'  <title>{esc_title}</title>\n'
        f'  <linearGradient id="s" x2="0" y2="100%">\n'
        f'    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        f'    <stop offset="1" stop-opacity=".1"/>\n'
        f'  </linearGradient>\n'
        f'  <clipPath id="r">\n'
        f'    <rect width="{total_w}" height="20" rx="3" fill="#fff"/>\n'
        f'  </clipPath>\n'
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{left_w}" height="20" fill="#555"/>\n'
        f'    <rect x="{left_w}" width="{right_w}" height="20" fill="{color_hex}"/>\n'
        f'    <rect width="{total_w}" height="20" fill="url(#s)"/>\n'
        f'  </g>\n'
        f'  <g fill="#fff" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'text-rendering="geometricPrecision" font-size="110">\n'
        f'    <text aria-hidden="true" x="{left_x}" y="150" fill="#010101" '
        f'fill-opacity=".3" transform="scale(.1)">{esc_label}</text>\n'
        f'    <text x="{left_x}" y="140" fill="#fff" '
        f'transform="scale(.1)">{esc_label}</text>\n'
        f'    <text aria-hidden="true" x="{right_x}" y="150" fill="#010101" '
        f'fill-opacity=".3" transform="scale(.1)">{esc_msg}</text>\n'
        f'    <text x="{right_x}" y="140" fill="#fff" '
        f'transform="scale(.1)">{esc_msg}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def render_badge_json(countries_count, helplines_count, verified_count):
    """Render a Shields.io endpoint schema v1 JSON badge payload."""
    color_name, _ = _badge_color(helplines_count, verified_count)
    payload = {
        "schemaVersion": 1,
        "label": "helplines",
        "message": _format_badge_message(countries_count, helplines_count, verified_count),
        "color": color_name,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate
    if validate.main([]) != 0:
        print("Refusing to build: fix validation errors first.")
        return 1

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "v1" / "countries").mkdir(parents=True)

    built_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    meta = {
        "schema_version": SCHEMA_VERSION,
        "built_at": built_at,
        "license": "CC0-1.0",
        "source": REPO_URL,
        "disclaimer": "Not an emergency service. If someone is in immediate danger, "
                      "call the local emergency number. Entries marked 'provisional' "
                      "have a single source; verify before relying on them.",
    }

    countries, index = {}, []
    for path in sorted(DATA_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        countries[doc["country"]] = doc
        (DIST / "v1" / "countries" / path.name).write_text(
            json.dumps({**meta, **doc}, ensure_ascii=False, indent=2), encoding="utf-8")
        hl = doc["helplines"]
        verified = sum(1 for h in hl if h["status"] == "verified")
        index.append({
            "country": doc["country"],
            "name": doc["name"],
            "helplines": len(hl),
            "verified": verified,
            "provisional": len(hl) - verified,
            "emergency": [e["number"] for e in doc.get("emergency", [])],
            "url": f"v1/countries/{path.name}",
        })

    total = sum(c["helplines"] for c in index)
    verified_total = sum(c["verified"] for c in index)

    (DIST / "v1" / "index.json").write_text(
        json.dumps({**meta, "countries": index}, ensure_ascii=False, indent=2), encoding="utf-8")
    (DIST / "v1" / "all.json").write_text(
        json.dumps({**meta, "countries": countries}, ensure_ascii=False), encoding="utf-8")
    (DIST / "v1" / "badge.json").write_text(
        render_badge_json(len(index), total, verified_total) + "\n", encoding="utf-8")
    (DIST / "coverage.md").write_text(
        render_coverage_markdown(index), encoding="utf-8")
    (DIST / "badge.svg").write_text(
        render_coverage_badge_svg(len(index), total, verified_total) + "\n", encoding="utf-8")
    shutil.copy(ROOT / "site" / "index.html", DIST / "index.html")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    try:
        dist_label = DIST.relative_to(ROOT)
    except ValueError:
        dist_label = DIST
    print(f"Built {len(index)} countries, {total} helplines into {dist_label}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
