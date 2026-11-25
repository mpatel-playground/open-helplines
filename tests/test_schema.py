"""Tests for schema/country.schema.json and parity with scripts/validate.py."""
import copy
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "country.schema.json"
DATA_DIR = ROOT / "data" / "countries"

sys.path.insert(0, str(ROOT / "scripts"))
import validate  # noqa: E402

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover - optional in stdlib-only CI
    jsonschema = None


def _resolve_ref(ref, root):
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported $ref: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _check_type(value, expected):
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _validate_stdlib(value, schema, root, path="$"):
    """Validate a JSON value against the subset of Draft 2020-12 used here."""
    errors = []
    if "$ref" in schema:
        errors.extend(_validate_stdlib(value, _resolve_ref(schema["$ref"], root), root, path))

    if "type" in schema and not _check_type(value, schema["type"]):
        errors.append(f"{path}: expected {schema['type']}, got {type(value).__name__}")
        return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: length {len(value)} < minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']!r}")
        if schema.get("format") == "date":
            try:
                dt.date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: invalid ISO date {value!r}")
        elif schema.get("format") == "uri":
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"{path}: invalid URI {value!r}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: {len(value)} items < minItems {schema['minItems']}")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            errors.append(f"{path}: duplicate items in array")
        if "items" in schema:
            for idx, item in enumerate(value):
                errors.extend(_validate_stdlib(item, schema["items"], root, f"{path}[{idx}]"))

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required key {req!r}")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            if extra:
                errors.append(f"{path}: unexpected properties {sorted(extra)}")
        for key, prop_schema in props.items():
            if key in value:
                errors.extend(_validate_stdlib(value[key], prop_schema, root, f"{path}.{key}"))

    for sub in schema.get("allOf", []):
        errors.extend(_validate_stdlib(value, sub, root, path))

    if "if" in schema and "then" in schema:
        if not _validate_stdlib(value, schema["if"], root, path):
            errors.extend(_validate_stdlib(value, schema["then"], root, path))

    return errors


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class SchemaTests(unittest.TestCase):
    def test_schema_metadata_and_draft_2020_12(self):
        schema = _load_schema()
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        if jsonschema is not None:
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_schema_parity_with_validator_constants(self):
        schema = _load_schema()
        top_props = set(schema["properties"])
        self.assertEqual(top_props, validate.COUNTRY_ALLOWED)

        helpline = schema["$defs"]["helpline"]
        self.assertEqual(set(helpline["required"]), validate.HELPLINE_REQUIRED)
        self.assertEqual(set(helpline["properties"]), validate.HELPLINE_ALLOWED)
        self.assertEqual(set(helpline["properties"]["categories"]["items"]["enum"]), validate.CATEGORIES)
        self.assertEqual(set(helpline["properties"]["audiences"]["items"]["enum"]), validate.AUDIENCES)
        self.assertEqual(set(helpline["properties"]["availability"]["enum"]), validate.AVAILABILITY)
        self.assertEqual(set(helpline["properties"]["cost"]["enum"]), validate.COSTS)
        self.assertEqual(set(helpline["properties"]["status"]["enum"]), validate.STATUSES)

        contact = schema["$defs"]["contact"]
        self.assertEqual(set(contact["properties"]["type"]["enum"]), validate.CONTACT_TYPES)

        source = schema["$defs"]["source"]
        self.assertEqual(set(source["properties"]["type"]["enum"]), validate.SOURCE_TYPES)

    def test_seed_data_validates_against_schema(self):
        schema = _load_schema()
        files = sorted(DATA_DIR.glob("*.json"))
        self.assertTrue(files, "Expected seed country files in data/countries/")
        validator = jsonschema.Draft202012Validator(schema) if jsonschema is not None else None
        for path in files:
            doc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.name):
                self.assertEqual(_validate_stdlib(doc, schema, schema), [])
                if validator is not None:
                    self.assertEqual(list(validator.iter_errors(doc)), [])

    def test_schema_rejects_invalid_structures(self):
        schema = _load_schema()
        sample = json.loads((DATA_DIR / "US.json").read_text(encoding="utf-8"))

        bad_extra = copy.deepcopy(sample)
        bad_extra["helplines"][0]["phone"] = "988"
        self.assertTrue(_validate_stdlib(bad_extra, schema, schema))

        bad_contact = copy.deepcopy(sample)
        bad_contact["helplines"][0]["contacts"][0]["value"] = "not digits"
        self.assertTrue(_validate_stdlib(bad_contact, schema, schema))

        bad_verified = copy.deepcopy(sample)
        bad_verified["helplines"][0]["status"] = "verified"
        self.assertTrue(_validate_stdlib(bad_verified, schema, schema))

        if jsonschema is not None:
            validator = jsonschema.Draft202012Validator(schema)
            for doc in (bad_extra, bad_contact, bad_verified):
                self.assertTrue(list(validator.iter_errors(doc)))


if __name__ == "__main__":
    unittest.main()
