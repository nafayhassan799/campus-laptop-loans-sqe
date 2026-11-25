"""Generate API test cases from the laptop-loan OpenAPI contract.

Standard library only; needs no Docker and no running application, so spec-change
examples can run by themselves:

    python -B tests/team/usman/api/generate_cases.py --out output/usman/api/cases.json

Techniques
  BVA  three-point boundary values (limit-1, limit, limit+1) for every numeric
       minimum/maximum and every minLength/maxLength found in the spec.
  EP   equivalence partitions: one representative per valid class and one
       invalid class per case (wrong type, bad enum, bad format, impossible date,
       omitted required field, null in a non-nullable field).

Every negative case changes exactly one input. Fields with no ordered boundary
(enums, booleans, free text, calendar dates) carry the spec's x-boundary-note into
the case notes so the reason is recorded next to the generated values.

Values written as '@name' are runtime fixtures resolved by run_api_tests.py.
"""

import argparse
import copy
import json
from pathlib import Path
import re

OPERATION_KEYS = {"checkoutLaptopToStudent": "CO", "checkinLaptopFromStudent": "CI"}
ENUM_WRONG_TYPE = 123
MISSING = object()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def resolve(spec, node):
    """Follow a local $ref."""
    while isinstance(node, dict) and "$ref" in node:
        target = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node = target
    return node


class Builder:
    def __init__(self, spec):
        self.spec = spec

    def operations(self):
        for path, item in self.spec["paths"].items():
            shared = [resolve(self.spec, p) for p in item.get("parameters", [])]
            post = item.get("post")
            if post and post["operationId"] in OPERATION_KEYS:
                yield path, post, shared

    def generate(self):
        cases = []
        for path, op, shared in self.operations():
            cases.extend(self.operation_cases(path, op, shared))
        return sorted(cases, key=lambda c: c["id"])

    # ---------------------------------------------------------------- one operation
    def operation_cases(self, path, op, shared):
        key = OPERATION_KEYS[op["operationId"]]
        body_schema = resolve(self.spec, op["requestBody"]["content"]["application/json"]["schema"])
        props = {n: resolve(self.spec, p) for n, p in body_schema.get("properties", {}).items()}
        required = body_schema.get("required", [])
        base_body = {n: self.example(props[n]) for n in required}
        context = {
            "operation": op["operationId"], "method": "POST", "path": path, "key": key,
            "precondition": op["x-precondition"], "base_body": base_body,
            "operation_requirements": op.get("x-requirement", []), "operation_risks": op.get("x-risk", []),
        }
        out = []
        out.append(self.case(context, "baseline", "EP", None, "valid baseline request", dict(base_body), "accept",
                             props_note="All required fields set to their valid example, optional fields omitted.",
                             requirements=op["x-requirement"][:1], risks=op.get("x-risk", [])))
        for param in shared:
            out.extend(self.path_cases(context, param))
        for name, prop in props.items():
            out.extend(self.field_cases(context, name, prop, name in required))
        return out

    # -------------------------------------------------------------------- path id
    def path_cases(self, ctx, param):
        schema = param["schema"]
        minimum = schema["minimum"]
        note = param.get("x-boundary-note", "")
        out = []
        for label, value, outcome in (
            (f"below-minimum ({minimum - 1})", minimum - 1, "reject"),
            (f"negative ({-minimum})", -minimum, "reject"),
            ("non-numeric text", "abc", "reject"),
            ("decimal number", "1.5", "reject"),
            ("id that matches no asset", 2147483647, "reject"),
        ):
            out.append(self.case(ctx, "asset_id", "BVA" if "minimum" in label else "EP", "asset_id", label, dict(ctx["base_body"]),
                                 outcome, asset_id=value, props_note=note,
                                 requirements=self.reqs(ctx, "asset_id"), risks=["R-A3"]))
        return out

    # ---------------------------------------------------------------------- fields
    def field_cases(self, ctx, name, prop, is_required):
        out = []
        typ = prop.get("type")
        nullable = prop.get("nullable", False)
        example = self.example(prop)
        note = prop.get("x-boundary-note", "")
        reqs = prop.get("x-requirement") or ctx["operation_requirements"][:1]
        risks = prop.get("x-risk") or ctx["operation_risks"]
        reference = prop.get("x-reference")

        def add(label, technique, value, outcome, oracle=None):
            body = dict(ctx["base_body"])
            if value is not MISSING:
                body[name] = value
            else:
                body.pop(name, None)
            out.append(self.case(ctx, name, technique, name, label, body, outcome, oracle=oracle,
                                 props_note=note or prop.get("x-server-note", ""), requirements=reqs, risks=risks))

        # one valid representative
        if example is not None and not (name in ctx["base_body"] and ctx["base_body"][name] == example):
            add(f"valid value ({example})", "EP", example, "accept")

        # omission and null
        if is_required:
            expected = "accept" if prop.get("x-server-infers") else "reject"
            label = "required field omitted" + (" (server infers it)" if prop.get("x-server-infers") else "")
            add(label, "EP", MISSING, expected)
        elif nullable:
            add("explicit null", "EP", None, "accept")
        if is_required and not nullable:
            add("required field is null", "EP", None, "accept" if prop.get("x-server-infers") else "reject")
        if is_required and nullable:
            add("nullable required field is null", "EP", None, "accept")

        if "enum" in prop:
            for value in prop["enum"]:
                if value != example:
                    add(f"valid enum value ({value})", "EP", value, "accept")
            add("value outside the enumeration", "EP", "invalid-enum", "reject")
            add("enumeration value with changed case", "EP", str(prop["enum"][0]).upper() + "x", "reject")
            add("wrong type (number)", "EP", ENUM_WRONG_TYPE, "reject")
        elif typ == "integer":
            self.integer_cases(add, prop, reference)
        elif typ == "string" and prop.get("format") == "date":
            add("valid leap day (2028-02-29)", "EP", "2028-02-29", "accept")
            add("impossible calendar date (2027-02-29)", "EP", "2027-02-29", "reject")
            add("month out of range (2027-13-01)", "EP", "2027-13-01", "reject")
            add("text that is not a date", "EP", "not-a-date", "reject")
            add("wrong type (boolean)", "EP", True, "reject")
        elif typ == "string":
            self.string_cases(add, prop)
        elif typ == "boolean":
            for value in (True, False):
                if value != example:
                    add(f"valid boolean ({str(value).lower()})", "EP", value, "accept")
            add("text that is not a boolean", "EP", "not-a-boolean", "reject")
            add("number outside 0/1", "EP", 2, "reject")
        return out

    def integer_cases(self, add, prop, reference):
        minimum, maximum = prop.get("minimum"), prop.get("maximum")
        if minimum is not None:
            oracle = f"reference:{reference}" if reference else None
            add(f"below minimum ({minimum - 1})", "BVA", minimum - 1, "reject")
            add(f"at minimum ({minimum})", "BVA", minimum, "accept" if not reference else "depends", oracle)
            add(f"above minimum ({minimum + 1})", "BVA", minimum + 1, "accept" if not reference else "depends", oracle)
        if maximum is not None:
            add(f"below maximum ({maximum - 1})", "BVA", maximum - 1, "accept")
            add(f"at maximum ({maximum})", "BVA", maximum, "accept")
            add(f"above maximum ({maximum + 1})", "BVA", maximum + 1, "reject")
        if reference:
            add("well-formed id that matches no row (2147483647)", "EP", 2147483647, "reject")
        add("wrong type (text)", "EP", "abc", "reject")
        add("wrong type (decimal)", "EP", 1.5, "reject")
        add("wrong type (boolean)", "EP", True, "reject")

    def string_cases(self, add, prop):
        longest = prop.get("maxLength")
        shortest = prop.get("minLength")
        if longest is not None:
            for delta, outcome in ((-1, "accept"), (0, "accept"), (1, "reject")):
                length = longest + delta
                add(f"length {length} ({'below' if delta < 0 else 'at' if delta == 0 else 'above'} maximum)", "BVA",
                    "L" * length, outcome)
        if shortest:
            for delta, outcome in ((-1, "reject"), (0, "accept"), (1, "accept")):
                add(f"length {shortest + delta}", "BVA", "L" * (shortest + delta), outcome)
        add("wrong type (number)", "EP", 12345, "reject" if longest is not None else "accept")

    # --------------------------------------------------------------------- helpers
    @staticmethod
    def example(prop):
        if "x-valid-example" in prop:
            return prop["x-valid-example"]
        return prop["enum"][0] if "enum" in prop else None

    def reqs(self, ctx, field):
        return ctx["operation_requirements"][:1]

    def case(self, ctx, group, technique, field, label, body, outcome, asset_id="@asset", oracle=None,
             props_note="", requirements=None, risks=None):
        slug_label = slug(label)
        return {
            "id": f"{ctx['key']}.{slug(group)}.{slug_label}",
            "operation": ctx["operation"], "method": ctx["method"], "path": ctx["path"],
            "technique": technique, "field": field, "partition": label,
            "requirements": requirements or [], "risks": risks or [],
            "precondition": ctx["precondition"],
            "asset_id": asset_id, "body": body,
            "expect": {"outcome": outcome, **({"oracle": oracle} if oracle else {})},
            "note": props_note,
        }


def generate(spec):
    return Builder(copy.deepcopy(spec)).generate()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    default_spec = Path(__file__).resolve().parents[2] / "hardware-loans.openapi.json"
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=str(default_spec))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    spec = load(args.spec)
    cases = generate(spec)
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate case ids: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    document = {"spec": str(Path(args.spec).name), "specVersion": spec["info"]["version"], "count": len(cases), "cases": cases}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    techniques = {t: sum(1 for c in cases if c["technique"] == t) for t in ("BVA", "EP")}
    print(f"Generated {len(cases)} cases from {Path(args.spec).name} -> {out} ({techniques['BVA']} BVA, {techniques['EP']} EP)")


if __name__ == "__main__":
    main()
