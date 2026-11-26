"""Tests for scripts/build.py. Run: python3 -m unittest discover tests"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build  # noqa: E402
import validate  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"


def _make_country_doc(code, name, emergency_numbers=(), helplines=()):
    return {
        "country": code,
        "name": name,
        "emergency": [
            {
                "number": num,
                "sources": [{
                    "url": "https://gov.example/emergency",
                    "type": "government",
                    "accessed": "2026-11-24",
                    "quote": f"Emergency number {num}",
                }],
            }
            for num in emergency_numbers
        ],
        "helplines": list(helplines),
    }


def _make_helpline(country_code, slug, number, verified=False):
    sources = [{
        "url": "https://operator.example/help",
        "type": "operator",
        "accessed": "2026-11-24",
        "quote": f"Call {number}",
    }]
    if verified:
        sources.append({
            "url": "https://health.gov.example/lines",
            "type": "government",
            "accessed": "2026-11-24",
            "quote": f"Helpline {number}",
        })
    return {
        "id": f"{country_code.lower()}-{slug}",
        "name": f"Line {slug}",
        "categories": ["crisis"],
        "audiences": ["everyone"],
        "contacts": [{"type": "phone", "value": number, "display": number}],
        "availability": "24/7",
        "cost": "free",
        "sources": sources,
        "status": "verified" if verified else "provisional",
        "last_verified": "2026-11-24",
    }


class RenderCoverageMarkdownTests(unittest.TestCase):
    def test_renders_heading_summary_sorted_table_and_links(self):
        # Intentionally unsorted and omitting explicit "provisional" on one entry.
        sample_index = [
            {
                "country": "US",
                "name": "United States",
                "helplines": 3,
                "verified": 1,
                "emergency": ["911"],
                "url": "v1/countries/US.json",
            },
            {
                "country": "AU",
                "name": "Australia",
                "helplines": 2,
                "verified": 2,
                "provisional": 0,
                "emergency": [],
                "url": "v1/countries/AU.json",
            },
            {
                "country": "IN",
                "name": "India",
                "helplines": 1,
                "verified": 0,
                "emergency": ["112", "100"],
                "url": "v1/countries/IN.json",
            },
            {
                "country": "ZZ",
                "name": "Test | Land",
                "helplines": 0,
                "verified": 0,
                "emergency": [],
                "url": "v1/countries/ZZ.json",
            },
        ]

        md = build.render_coverage_markdown(sample_index)
        lines = md.splitlines()

        self.assertTrue(lines[0].startswith("# "))
        self.assertIn("**4 countries**", md)
        self.assertIn("**6 helplines**", md)
        self.assertIn("(3 verified, 3 provisional)", md)

        header = "| Country | Code | Helplines | Verified | Provisional | Emergency | Status |"
        self.assertIn(header, lines)
        header_idx = lines.index(header)
        self.assertEqual(lines[header_idx + 1], "|---|---|---|---|---|---|---|")

        table_rows = [
            line for line in lines[header_idx + 2:]
            if line.startswith("|")
        ]
        self.assertEqual(len(table_rows), 4)
        self.assertEqual(
            table_rows[0],
            "| Australia | AU | 2 | 2 | 0 | — | Verified |",
        )
        self.assertEqual(
            table_rows[1],
            "| India | IN | 1 | 0 | 1 | 112, 100 | Provisional |",
        )
        self.assertEqual(
            table_rows[2],
            "| United States | US | 3 | 1 | 2 | 911 | Partially verified |",
        )
        self.assertEqual(
            table_rows[3],
            "| Test \\| Land | ZZ | 0 | 0 | 0 | — | No helplines |",
        )

        self.assertIn("label%3Acountry-data", md)
        self.assertIn("label%3Aneeds-second-source", md)

    def test_handles_empty_index_and_singular_counts(self):
        empty_md = build.render_coverage_markdown([])
        self.assertIn("**0 countries** · **0 helplines** (0 verified, 0 provisional)", empty_md)

        single_md = build.render_coverage_markdown([{
            "country": "GB",
            "name": "United Kingdom",
            "helplines": 1,
            "verified": 1,
            "emergency": ["999"],
            "url": "v1/countries/GB.json",
        }])
        self.assertIn("**1 country** · **1 helpline** (1 verified, 0 provisional)", single_md)


class RenderCoverageBadgeTests(unittest.TestCase):
    def test_svg_is_valid_self_contained_xml(self):
        svg = build.render_coverage_badge_svg(7, 10, 0)
        root = ET.fromstring(svg)

        self.assertEqual(root.tag, f"{{{SVG_NS}}}svg")
        self.assertEqual(root.attrib.get("role"), "img")
        self.assertEqual(root.attrib.get("height"), "20")
        self.assertGreater(int(root.attrib["width"]), 0)
        self.assertEqual(
            root.attrib.get("aria-label"),
            "coverage: 7 countries · 10 helplines (0 verified)",
        )

        title = root.find(f"{{{SVG_NS}}}title")
        self.assertIsNotNone(title)
        self.assertEqual(title.text, "coverage: 7 countries · 10 helplines (0 verified)")

        texts = [el.text for el in root.findall(f".//{{{SVG_NS}}}text")]
        self.assertIn("coverage", texts)
        self.assertIn("7 countries · 10 helplines (0 verified)", texts)

        # Self-contained: no scripts or external asset references.
        self.assertIsNone(root.find(f".//{{{SVG_NS}}}script"))
        self.assertNotIn("http://", svg.replace(SVG_NS, ""))
        self.assertNotIn("https://", svg)

    def test_svg_width_grows_with_larger_counts(self):
        small_root = ET.fromstring(build.render_coverage_badge_svg(1, 1, 0))
        large_root = ET.fromstring(build.render_coverage_badge_svg(195, 1200, 900))
        self.assertGreater(int(large_root.attrib["width"]), int(small_root.attrib["width"]))

    def test_svg_colors_and_singular_grammar(self):
        zero_svg = build.render_coverage_badge_svg(0, 0, 0)
        self.assertIn("#9f9f9f", zero_svg)
        self.assertIn("0 countries · 0 helplines (0 verified)", zero_svg)

        all_verified_svg = build.render_coverage_badge_svg(1, 1, 1)
        self.assertIn("#2ea44f", all_verified_svg)
        self.assertIn("1 country · 1 helpline (1 verified)", all_verified_svg)

        partial_svg = build.render_coverage_badge_svg(2, 4, 2)
        self.assertIn("#97ca00", partial_svg)

        provisional_svg = build.render_coverage_badge_svg(2, 4, 0)
        self.assertIn("#007ec6", provisional_svg)

    def test_badge_json_matches_shields_endpoint_schema(self):
        payload = json.loads(build.render_badge_json(7, 10, 0))
        self.assertEqual(payload, {
            "schemaVersion": 1,
            "label": "helplines",
            "message": "7 countries · 10 helplines (0 verified)",
            "color": "blue",
        })

        verified_payload = json.loads(build.render_badge_json(1, 3, 3))
        self.assertEqual(verified_payload["color"], "brightgreen")
        self.assertEqual(verified_payload["message"], "1 country · 3 helplines (3 verified)")

    def test_badge_json_hardcodes_shields_schema_version_1(self):
        with mock.patch.object(build, "SCHEMA_VERSION", 2):
            payload = json.loads(build.render_badge_json(5, 10, 5))
            self.assertEqual(payload["schemaVersion"], 1)


class BuildMainIntegrationTests(unittest.TestCase):
    def test_build_main_on_repository_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist_dir = Path(tmp).resolve() / "dist"
            with mock.patch.object(build, "DIST", dist_dir), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = build.main()

            self.assertEqual(rc, 0)
            self.assertTrue((dist_dir / "v1" / "index.json").is_file())
            self.assertTrue((dist_dir / "v1" / "all.json").is_file())
            self.assertTrue((dist_dir / "v1" / "badge.json").is_file())
            self.assertTrue((dist_dir / "coverage.md").is_file())
            self.assertTrue((dist_dir / "badge.svg").is_file())
            self.assertTrue((dist_dir / "index.html").is_file())
            self.assertTrue((dist_dir / ".nojekyll").is_file())

            index_doc = json.loads((dist_dir / "v1" / "index.json").read_text(encoding="utf-8"))
            countries = index_doc["countries"]
            self.assertEqual(len(countries), len(list(build.DATA_DIR.glob("*.json"))))

            for entry in countries:
                self.assertEqual(entry["verified"] + entry["provisional"], entry["helplines"])
                self.assertTrue((dist_dir / entry["url"]).is_file())

            total_countries = len(countries)
            total_helplines = sum(c["helplines"] for c in countries)
            total_verified = sum(c["verified"] for c in countries)
            total_provisional = total_helplines - total_verified

            coverage_md = (dist_dir / "coverage.md").read_text(encoding="utf-8")
            self.assertIn(
                f"({total_verified} verified, {total_provisional} provisional)",
                coverage_md,
            )
            for entry in countries:
                self.assertIn(f"| {entry['name']} | {entry['country']} |", coverage_md)

            badge_svg = (dist_dir / "badge.svg").read_text(encoding="utf-8")
            svg_root = ET.fromstring(badge_svg)
            self.assertEqual(svg_root.tag, f"{{{SVG_NS}}}svg")
            expected_msg = (
                f"{total_countries} countries · {total_helplines} helplines "
                f"({total_verified} verified)"
            )
            self.assertIn(expected_msg, badge_svg)

            badge_json = json.loads((dist_dir / "v1" / "badge.json").read_text(encoding="utf-8"))
            self.assertEqual(badge_json["schemaVersion"], 1)
            self.assertEqual(badge_json["label"], "helplines")
            self.assertEqual(badge_json["message"], expected_msg)

    def test_build_main_verified_vs_provisional_math_with_synthetic_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            data_dir = tmp_path / "countries"
            data_dir.mkdir()
            dist_dir = tmp_path / "dist"

            aa_doc = _make_country_doc(
                "AA",
                "Alpha",
                emergency_numbers=("112", "999"),
                helplines=[
                    _make_helpline("AA", "one", "116123", verified=True),
                    _make_helpline("AA", "two", "116124", verified=False),
                    _make_helpline("AA", "three", "116125", verified=False),
                ],
            )
            bb_doc = _make_country_doc("BB", "Beta", emergency_numbers=(), helplines=[])

            (data_dir / "AA.json").write_text(json.dumps(aa_doc), encoding="utf-8")
            (data_dir / "BB.json").write_text(json.dumps(bb_doc), encoding="utf-8")

            with mock.patch.object(build, "DATA_DIR", data_dir), \
                    mock.patch.object(build, "DIST", dist_dir), \
                    mock.patch.object(validate, "DATA_DIR", data_dir), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = build.main()

            self.assertEqual(rc, 0)

            index_doc = json.loads((dist_dir / "v1" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index_doc["countries"], [
                {
                    "country": "AA",
                    "name": "Alpha",
                    "helplines": 3,
                    "verified": 1,
                    "provisional": 2,
                    "emergency": ["112", "999"],
                    "url": "v1/countries/AA.json",
                },
                {
                    "country": "BB",
                    "name": "Beta",
                    "helplines": 0,
                    "verified": 0,
                    "provisional": 0,
                    "emergency": [],
                    "url": "v1/countries/BB.json",
                },
            ])

            coverage_md = (dist_dir / "coverage.md").read_text(encoding="utf-8")
            self.assertIn("**2 countries** · **3 helplines** (1 verified, 2 provisional)", coverage_md)
            self.assertIn("| Alpha | AA | 3 | 1 | 2 | 112, 999 | Partially verified |", coverage_md)
            self.assertIn("| Beta | BB | 0 | 0 | 0 | — | No helplines |", coverage_md)

            badge_svg = (dist_dir / "badge.svg").read_text(encoding="utf-8")
            ET.fromstring(badge_svg)
            self.assertIn("2 countries · 3 helplines (1 verified)", badge_svg)
            self.assertIn("#97ca00", badge_svg)

            badge_json = json.loads((dist_dir / "v1" / "badge.json").read_text(encoding="utf-8"))
            self.assertEqual(badge_json["schemaVersion"], 1)
            self.assertEqual(badge_json["label"], "helplines")
            self.assertEqual(badge_json["message"], "2 countries · 3 helplines (1 verified)")
            self.assertEqual(badge_json["color"], "yellowgreen")

    def test_build_main_refuses_invalid_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            data_dir = tmp_path / "countries"
            data_dir.mkdir()
            dist_dir = tmp_path / "dist"
            (data_dir / "BAD.json").write_text("{not json", encoding="utf-8")

            with mock.patch.object(build, "DATA_DIR", data_dir), \
                    mock.patch.object(build, "DIST", dist_dir), \
                    mock.patch.object(validate, "DATA_DIR", data_dir), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = build.main()

            self.assertEqual(rc, 1)
            self.assertFalse(dist_dir.exists())


if __name__ == "__main__":
    unittest.main()
