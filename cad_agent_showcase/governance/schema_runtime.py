"""Offline validation of the published Draft 2020-12 contracts.

Projection checks never validate the legacy engineering/authorization fields.
Callers must conjoin those existing contracts before admitting a carrier.
"""

import copy
import json
import math
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

from .envelope import InputError

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = PACKAGE_ROOT / "contracts" / "cognition"
COGNITION_SCHEMAS = (
    "common", "entry", "facts", "source-manifest", "generalization",
    "candidate-cognition", "scene-cognition", "neutral-evidence-map",
    "semantic-check",
)
REQUIREMENTS_SCHEMAS = ("content-export", "content-record", "requirements-content")
SCHEMAS = COGNITION_SCHEMAS + REQUIREMENTS_SCHEMAS
PROJECTION_SCHEMAS = {
    "brief": "entry", "facts": "facts", "generalization": "generalization",
    "candidate": "candidate-cognition", "scene": "scene-cognition",
}
_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
_LIST_SCHEMAS = ("allOf", "anyOf", "oneOf")
_SINGLE_SCHEMAS = ("items", "additionalProperties", "if", "then", "else", "not")
_MAP_SCHEMAS = ("properties", "$defs")
_LENGTHS = ("minLength", "minItems", "maxItems")
_SUPPORTED = {
    "$schema", "$id", "$ref", "title", "type", "const", "enum", "required",
    "pattern", "format", "uniqueItems", "minimum", "exclusiveMinimum",
    *_LIST_SCHEMAS, *_SINGLE_SCHEMAS, *_MAP_SCHEMAS, *_LENGTHS,
}


def json_value(value, location="$"):
    """Reject values outside the JSON data model before library validation."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for index, item in enumerate(value):
            json_value(item, "%s/%d" % (location, index))
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for key, item in value.items():
            json_value(item, location + "/" + key)
        return
    raise InputError("COGNITION_JSON_VALUE", "Not a finite JSON value", location)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    try:
        return decode_json(Path(path).read_bytes())
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise InputError("COGNITION_JSON_READ", str(exc), str(path)) from exc


def decode_json(data):
    """Decode UTF-8 JSON with finite values and no duplicate object keys."""
    result = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs)
    json_value(result)
    return result


def _date_time(value):
    if not isinstance(value, str):
        return True
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})", value, re.I) is None:
        return False
    if value[-6:-5] in ("+", "-") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        return False
    try:
        datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _resolve_ref(ref, home, registry):
    uri, _, fragment = ref.partition("#")
    uri = uri or home
    target = registry[uri]
    if fragment:
        pointer = unquote(fragment)
        if not pointer.startswith("/"):
            raise ValueError("Bundled references require JSON Pointers")
        for part in pointer[1:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            target = target[int(key)] if isinstance(target, list) else target[key]
    if type(target) not in (dict, bool):
        raise ValueError("Reference target is not a schema: " + ref)
    return target, uri


def _strings(value):
    return (isinstance(value, list) and all(isinstance(item, str) and item for item in value)
            and len(set(value)) == len(value))


def _check_definition(schema, home, registry):
    """Reject malformed or unsupported changes to the bundled schema vocabulary."""
    if type(schema) is bool:
        return
    if not isinstance(schema, dict):
        raise ValueError("A schema must be an object or boolean")
    unknown = schema.keys() - _SUPPORTED
    if unknown:
        raise ValueError("Unsupported bundled schema keywords: " + ", ".join(sorted(unknown)))
    if schema is not registry[home] and ("$id" in schema or "$schema" in schema):
        raise ValueError("Only schema roots may introduce a dialect or identifier")
    if "$ref" in schema:
        _resolve_ref(schema["$ref"], home, registry)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not types or not _strings(types) or set(types) - _TYPES:
            raise ValueError("Invalid schema type declaration")
    if "required" in schema and not _strings(schema["required"]):
        raise ValueError("Invalid required property names")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError("Invalid schema enum")
    if "pattern" in schema:
        re.compile(schema["pattern"])
    if "format" in schema and schema["format"] != "date-time":
        raise ValueError("Unsupported bundled schema format")
    if "uniqueItems" in schema and type(schema["uniqueItems"]) is not bool:
        raise ValueError("uniqueItems must be boolean")
    for key in ("minimum", "exclusiveMinimum"):
        if key in schema and type(schema[key]) not in (int, float):
            raise ValueError(key + " must be numeric")
    for key in _LENGTHS:
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise ValueError(key + " must be a nonnegative integer")
    children = [schema[key] for key in _SINGLE_SCHEMAS if key in schema]
    for key in _MAP_SCHEMAS:
        if key in schema:
            children.extend(schema[key].values())
    for key in _LIST_SCHEMAS:
        if key in schema:
            if not isinstance(schema[key], list) or not schema[key]:
                raise ValueError(key + " requires a nonempty schema array")
            children.extend(schema[key])
    for child in children:
        _check_definition(child, home, registry)


def _json_key(value):
    """Use JSON Schema equality, including type-sensitive booleans."""
    kind = type(value)
    if kind is dict:
        return kind, tuple(sorted((key, _json_key(item)) for key, item in value.items()))
    if kind is list:
        return kind, tuple(_json_key(item) for item in value)
    return (int if kind is float else kind), value


def _is_type(value, kind):
    if kind == "number":
        return type(value) in (int, float)
    if kind == "integer":
        return type(value) is int or (type(value) is float and value.is_integer())
    return type(value) is {
        "object": dict, "array": list, "string": str,
        "boolean": bool, "null": type(None),
    }[kind]


def _stdlib_error(value, schema, path, home, registry):
    """Return the first instance error for the vocabulary used by these contracts."""
    if type(schema) is bool:
        return None if schema else (path, "Disallowed by schema")
    if "$ref" in schema:
        target, uri = _resolve_ref(schema["$ref"], home, registry)
        error = _stdlib_error(value, target, path, uri, registry)
        if error:
            return error
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, kind) for kind in types):
            return path, "Expected type: " + " or ".join(types)
    if "const" in schema and _json_key(value) != _json_key(schema["const"]):
        return path, "Value does not match the required constant"
    if "enum" in schema and _json_key(value) not in {_json_key(item) for item in schema["enum"]}:
        return path, "Value does not match an allowed choice"
    for subschema in schema.get("allOf", []):
        error = _stdlib_error(value, subschema, path, home, registry)
        if error:
            return error
    for key in ("anyOf", "oneOf"):
        if key in schema:
            matches = sum(_stdlib_error(value, part, path, home, registry) is None
                          for part in schema[key])
            if not matches or (key == "oneOf" and matches != 1):
                return path, "Value fails " + key
    if "not" in schema and _stdlib_error(value, schema["not"], path, home, registry) is None:
        return path, "Value matches forbidden schema"
    if "if" in schema:
        matches = _stdlib_error(value, schema["if"], path, home, registry) is None
        error = _stdlib_error(value, schema.get("then" if matches else "else", True),
                              path, home, registry)
        if error:
            return error
    if type(value) is dict:
        missing = set(schema.get("required", [])) - value.keys()
        if missing:
            return path, "Missing required properties: " + ", ".join(sorted(missing))
        properties = schema.get("properties", {})
        for key, item in value.items():
            subschema = properties.get(key, schema.get("additionalProperties", True))
            key_path = path + "/" + key.replace("~", "~0").replace("/", "~1")
            error = _stdlib_error(item, subschema, key_path, home, registry)
            if error:
                return error
    elif type(value) is list:
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            return path, "Array size exceeds a declared bound"
        if schema.get("uniqueItems") and len({_json_key(item) for item in value}) != len(value):
            return path, "Array items must be unique"
        if "items" in schema:
            for index, item in enumerate(value):
                error = _stdlib_error(item, schema["items"], f"{path}/{index}", home, registry)
                if error:
                    return error
    elif type(value) is str:
        if len(value) < schema.get("minLength", 0):
            return path, "String is shorter than minLength"
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            return path, "String does not match the declared pattern"
        if schema.get("format") == "date-time" and not _date_time(value):
            return path, "String is not a valid date-time"
    elif type(value) in (int, float):
        if value < schema.get("minimum", -math.inf) or value <= schema.get("exclusiveMinimum", -math.inf):
            return path, "Number is below its declared bound"
    return None


def _check_policy(policy, schemas):
    if policy["schema"] != "wishcad.cognition-carrier-key-policy.v1":
        raise ValueError("Unexpected carrier policy version")
    carriers = policy["carriers"]
    if carriers.keys() != PROJECTION_SCHEMAS.keys():
        raise ValueError("Carrier policy does not cover the public projections")
    for kind, schema_name in PROJECTION_SCHEMAS.items():
        carrier = carriers[kind]
        allowed, projection = carrier["allowed_keys"], carrier["projection_keys"]
        properties = schemas[schema_name]["properties"]
        version_key = "cognition_schema" if kind == "scene" else "schema"
        if (not _strings(allowed) or not _strings(projection)
                or not set(projection).issubset(allowed)
                or set(projection) != properties.keys()
                or carrier["version"] != properties[version_key]["const"]):
            raise ValueError("Carrier policy does not match schema: " + kind)
    identity = policy["identity_paths"]
    removed, nulled = identity["top_level_remove"], identity["top_level_null"]
    if (not _strings(removed) or nulled != ["/author_session"]
            or set(removed) & set(nulled)
            or any(re.fullmatch(r"/[a-zA-Z_][a-zA-Z0-9_]*", path) is None for path in removed)):
        raise ValueError("Invalid top-level identity paths")


@lru_cache(maxsize=1)
def _runtime():
    try:
        schemas = {name: read_json(CONTRACTS / (name + ".schema.json"))
                   for name in COGNITION_SCHEMAS}
        schemas.update({
            name: read_json(CONTRACTS.parent / "requirements" / (name + ".schema.json"))
            for name in REQUIREMENTS_SCHEMAS
        })
        ids = [schema["$id"] for schema in schemas.values()]
        if (len(set(ids)) != len(ids) or any(not uri.startswith("urn:") or "#" in uri for uri in ids)
                or any(schema["$schema"] != _DRAFT for schema in schemas.values())):
            raise ValueError("Bundled schemas require Draft 2020-12 and unique local URNs")
        registry = dict(zip(ids, schemas.values()))
        for uri, schema in registry.items():
            _check_definition(schema, uri, registry)
        policy = read_json(CONTRACTS / "carrier-and-anonymization-policy.json")
        _check_policy(policy, schemas)
        return schemas, registry, policy
    except (AttributeError, KeyError, ValueError, TypeError, IndexError, re.error, RecursionError) as exc:
        raise InputError("COGNITION_SCHEMA_RUNTIME", str(exc)) from exc


def read_anonymization_policy():
    """Return a copy of the same validated policy used by projection checks."""
    _, _, policy = _runtime()
    return copy.deepcopy(policy)


def validate_schema(name, value):
    """Validate a named bundled schema, raising InputError on refusal."""
    json_value(value)
    schemas, registry, _ = _runtime()
    if name not in schemas:
        raise InputError("COGNITION_SCHEMA_NAME", "Unknown bundled schema: " + str(name))
    try:
        schema = schemas[name]
        error = _stdlib_error(value, schema, "$", schema["$id"], registry)
    except (KeyError, ValueError, TypeError, RecursionError) as exc:
        raise InputError("COGNITION_SCHEMA_RUNTIME", str(exc)) from exc
    if error:
        path, detail = error
        raise InputError("COGNITION_SCHEMA_INVALID", detail, name + ":" + path)
    return {"schema_name": name, "schema_valid": True, "scope": "named_schema_only"}


def validate_projection(kind, carrier):
    """Reject undeclared top-level keys, then validate the exact K01 projection."""
    json_value(carrier)
    _, _, policy = _runtime()
    if kind not in PROJECTION_SCHEMAS:
        raise InputError("COGNITION_CARRIER_KIND", "Unknown carrier: " + str(kind))
    if type(carrier) is not dict:
        raise InputError("COGNITION_CARRIER_TYPE", "Carrier must be an object", kind)
    carrier_policy = policy["carriers"][kind]
    extra = set(carrier) - set(carrier_policy["allowed_keys"])
    if extra:
        raise InputError("COGNITION_UNKNOWN_KEY", "Undeclared full-carrier keys: " + ", ".join(sorted(extra)), kind)
    projection = {key: carrier[key] for key in carrier_policy["projection_keys"] if key in carrier}
    validate_schema(PROJECTION_SCHEMAS[kind], projection)
    return projection
