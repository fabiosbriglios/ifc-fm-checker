"""
Check IDS: buildingSMART IDS 1.0 / 0.9.x Validation
Validates an IFC model against an Information Delivery Specification (.ids) file.

Activated only when --ids path/to/file.ids is provided.
Does NOT contribute to the FM Readiness score (weight 0%).

Supports:
  - IDS namespaces: 1.0, 0.9.7, 0.9.6
  - Applicability facets: entity, attribute, property
  - Requirement facets: entity, attribute, property
  - Value constraints: simpleValue, xs:enumeration, xs:pattern (regex)
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from ifc_fm_checker.utils import get_psets, prop_is_filled, get_entity_label

# Known IDS XML namespaces across versions
_IDS_NAMESPACES = [
    "http://standards.buildingsmart.org/IDS",
    "http://standards.buildingsmart.org/IDS/0.9.7",
    "http://standards.buildingsmart.org/IDS/0.9.6",
    "http://www.buildingsmart.org/ids/version_0.9",
]
_XS_NS = "http://www.w3.org/2001/XMLSchema"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(ifc_file, ids_path: str = None) -> Dict[str, Any]:
    """Run IDS validation. Returns a standard check result dict."""

    if not ids_path:
        return _skipped_result()

    try:
        tree = ET.parse(ids_path)
    except ET.ParseError as exc:
        return _error_result(f"IDS file is not valid XML: {exc}")
    except FileNotFoundError:
        return _error_result(f"IDS file not found: {ids_path}")
    except OSError as exc:
        return _error_result(f"Cannot open IDS file: {exc}")

    root = tree.getroot()
    ns = _detect_namespace(root)

    specifications = _parse_specifications(root, ns)
    if not specifications:
        return {
            "name": "IDS Validation",
            "score": 100,
            "issues": [{
                "severity": "warning",
                "element": Path(ids_path).name,
                "message": "No <specification> elements found in the IDS file",
                "fix": "Verify the IDS file contains <specifications><specification> elements.",
            }],
            "stats": {"ids_file": Path(ids_path).name, "specifications": 0},
            "description": _description(ids_path),
        }

    issues: List[Dict] = []
    spec_results: List[Dict] = []
    total_checks = 0
    passed_checks = 0

    for spec in specifications:
        spec_name = spec.get("name", "Unnamed Specification")
        min_occurs = _int_attr(spec, "minOccurs", 0)

        applicable = _find_applicable_elements(ifc_file, spec, ns)

        if min_occurs > 0 and len(applicable) == 0:
            issues.append({
                "severity": "error",
                "element": f"Specification: {spec_name}",
                "message": (
                    f"No applicable elements found — '{spec_name}' "
                    f"requires at least {min_occurs} matching element(s)"
                ),
                "fix": (
                    "Ensure the model contains elements that match the "
                    f"applicability criteria of specification '{spec_name}'."
                ),
            })
            spec_results.append({
                "name": spec_name,
                "applicable": 0,
                "passed": 0,
                "failed": 1,
                "score": 0,
            })
            total_checks += 1
            continue

        spec_passed = 0
        spec_failed = 0
        spec_issues: List[Dict] = []

        for element in applicable:
            elem_issues = _check_requirements(element, spec, ns, spec_name)
            if elem_issues:
                spec_issues.extend(elem_issues)
                spec_failed += 1
            else:
                spec_passed += 1

        total = spec_passed + spec_failed
        total_checks += total
        passed_checks += spec_passed

        spec_score = int(spec_passed / total * 100) if total > 0 else 100
        spec_results.append({
            "name": spec_name,
            "applicable": len(applicable),
            "passed": spec_passed,
            "failed": spec_failed,
            "score": spec_score,
        })

        # Summary issue per specification
        if spec_failed == 0 and len(applicable) > 0:
            issues.append({
                "severity": "info",
                "element": f"Specification: {spec_name}",
                "message": f"PASS — {spec_passed}/{total} element(s) compliant",
                "fix": "",
            })
        elif spec_issues:
            # Cap per-spec element issues to keep the report readable
            issues.extend(spec_issues[:25])
            remaining = len(spec_issues) - 25
            if remaining > 0:
                issues.append({
                    "severity": "warning",
                    "element": f"Specification: {spec_name}",
                    "message": f"… and {remaining} more element(s) failing this specification",
                    "fix": "Fix the issues above; the same requirement applies to all listed elements.",
                })

    overall_score = (
        int(passed_checks / total_checks * 100) if total_checks > 0 else 100
    )

    return {
        "name": "IDS Validation",
        "score": overall_score,
        "issues": issues,
        "stats": {
            "ids_file": Path(ids_path).name,
            "specifications": len(specifications),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
        },
        "description": _description(ids_path),
    }


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------

def _detect_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith("{"):
        return tag[1:tag.index("}")]
    return ""


def _q(tag: str, ns: str) -> str:
    """Return a qualified tag name."""
    return f"{{{ns}}}{tag}" if ns else tag


# ---------------------------------------------------------------------------
# IDS parsing
# ---------------------------------------------------------------------------

def _parse_specifications(root: ET.Element, ns: str) -> List[ET.Element]:
    specs_container = root.find(_q("specifications", ns))
    if specs_container is None:
        return []
    return specs_container.findall(_q("specification", ns))


def _extract_constraint(elem: Optional[ET.Element], ns: str) -> Optional[str]:
    """
    Extract a value constraint from an IDS value element.
    Returns:
      - the string value for <simpleValue>
      - "v1|v2|v3" for xs:enumeration
      - the regex string for xs:pattern
      - None if no constraint (presence-only check)
    """
    if elem is None:
        return None

    # <simpleValue>TEXT</simpleValue>
    sv = elem.find(_q("simpleValue", ns))
    if sv is not None and sv.text:
        return sv.text.strip()

    # <xs:restriction>
    restriction = elem.find(f"{{{_XS_NS}}}restriction")
    if restriction is not None:
        enums = restriction.findall(f"{{{_XS_NS}}}enumeration")
        if enums:
            return "|".join(e.get("value", "") for e in enums)
        pattern_elem = restriction.find(f"{{{_XS_NS}}}pattern")
        if pattern_elem is not None:
            return pattern_elem.get("value")

    return None


def _matches(actual: Any, constraint: Optional[str]) -> bool:
    """Return True when *actual* satisfies *constraint*."""
    if constraint is None:
        # Presence-only: value must be filled
        return prop_is_filled(actual)

    if actual is None:
        return False

    actual_str = str(actual).strip()

    # Enumeration list
    if "|" in constraint:
        allowed = {v.strip().upper() for v in constraint.split("|")}
        return actual_str.upper() in allowed

    # Regex / pattern (xs:pattern anchors the whole string)
    if any(c in constraint for c in ["^", "$", ".*", ".+", "\\", "[", "("]):
        try:
            return bool(re.fullmatch(constraint, actual_str, re.IGNORECASE))
        except re.error:
            pass  # fall through to simple compare

    # Plain string equality (case-insensitive)
    return actual_str.upper() == constraint.strip().upper()


# ---------------------------------------------------------------------------
# Applicability
# ---------------------------------------------------------------------------

def _find_applicable_elements(ifc_file, spec: ET.Element, ns: str) -> List:
    applicability = spec.find(_q("applicability", ns))
    if applicability is None:
        return []

    # 1. Seed the set from the entity facet
    candidates = _apply_entity_facet(
        ifc_file, applicability.find(_q("entity", ns)), ns
    )

    # 2. Filter by attribute facets
    for facet in applicability.findall(_q("attribute", ns)):
        candidates = _filter_by_attribute(candidates, facet, ns)

    # 3. Filter by property facets
    for facet in applicability.findall(_q("property", ns)):
        candidates = _filter_by_property(candidates, facet, ns)

    return candidates


def _apply_entity_facet(ifc_file, facet: Optional[ET.Element], ns: str) -> List:
    if facet is None:
        return list(ifc_file.by_type("IfcProduct"))

    name_elem = facet.find(_q("name", ns))
    ifc_type = _extract_constraint(name_elem, ns)
    if not ifc_type:
        return list(ifc_file.by_type("IfcProduct"))

    try:
        return list(ifc_file.by_type(ifc_type))
    except RuntimeError:
        return []


def _filter_by_attribute(elements: List, facet: ET.Element, ns: str) -> List:
    name_elem = facet.find(_q("name", ns))
    value_elem = facet.find(_q("value", ns))
    attr_name = _extract_constraint(name_elem, ns)
    constraint = _extract_constraint(value_elem, ns)

    if not attr_name:
        return elements

    return [
        e for e in elements
        if _matches(getattr(e, attr_name, None), constraint)
    ]


def _filter_by_property(elements: List, facet: ET.Element, ns: str) -> List:
    pset_name, prop_name, constraint = _read_property_facet(facet, ns)
    if not pset_name or not prop_name:
        return elements

    return [
        e for e in elements
        if _element_property_matches(e, pset_name, prop_name, constraint)
    ]


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

def _check_requirements(
    element, spec: ET.Element, ns: str, spec_name: str
) -> List[Dict]:
    requirements = spec.find(_q("requirements", ns))
    if requirements is None:
        return []

    issues: List[Dict] = []
    label = get_entity_label(element)

    # Entity requirement (usually just presence of a certain type — already satisfied
    # by applicability, but the spec may require a *different* entity type)
    for facet in requirements.findall(_q("entity", ns)):
        name_elem = facet.find(_q("name", ns))
        req_type = _extract_constraint(name_elem, ns)
        if req_type and not element.is_a(req_type):
            issues.append({
                "severity": "error",
                "element": label,
                "message": (
                    f"[IDS:{spec_name}] Entity type must be '{req_type}' "
                    f"but is '{element.is_a()}'"
                ),
                "fix": (
                    f"Change the element type to '{req_type}' in the authoring tool "
                    f"to satisfy IDS requirement '{spec_name}'."
                ),
            })

    # Attribute requirements
    for facet in requirements.findall(_q("attribute", ns)):
        name_elem = facet.find(_q("name", ns))
        value_elem = facet.find(_q("value", ns))
        attr_name = _extract_constraint(name_elem, ns)
        constraint = _extract_constraint(value_elem, ns)

        if not attr_name:
            continue

        actual = getattr(element, attr_name, None)
        if not _matches(actual, constraint):
            desc = f" = '{constraint}'" if constraint else " (must be filled)"
            issues.append({
                "severity": "error",
                "element": label,
                "message": (
                    f"[IDS:{spec_name}] Attribute '{attr_name}'{desc} "
                    f"— found: '{actual}'"
                ),
                "fix": (
                    f"Set '{attr_name}' on this element to satisfy "
                    f"IDS requirement '{spec_name}'."
                ),
            })

    # Property requirements
    for facet in requirements.findall(_q("property", ns)):
        pset_name, prop_name, constraint = _read_property_facet(facet, ns)
        if not pset_name or not prop_name:
            continue

        psets = get_psets(element)
        pset = psets.get(pset_name, {})
        actual = pset.get(prop_name)

        if not _matches(actual, constraint):
            desc = f" = '{constraint}'" if constraint else " (must be filled)"
            issues.append({
                "severity": "error",
                "element": label,
                "message": (
                    f"[IDS:{spec_name}] '{pset_name}.{prop_name}'{desc} "
                    f"— found: '{actual}'"
                ),
                "fix": (
                    f"Fill '{pset_name}.{prop_name}' in the authoring tool "
                    f"to satisfy IDS requirement '{spec_name}'."
                ),
            })

    return issues


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _read_property_facet(
    facet: ET.Element, ns: str
) -> tuple:
    """Return (pset_name, prop_name, value_constraint) from a property facet."""
    pset_elem = facet.find(_q("propertySet", ns))
    # IDS 1.0 uses <baseName>, 0.9.x sometimes uses <name>
    prop_name_elem = facet.find(_q("baseName", ns))
    if prop_name_elem is None:
        prop_name_elem = facet.find(_q("name", ns))
    value_elem = facet.find(_q("value", ns))

    return (
        _extract_constraint(pset_elem, ns),
        _extract_constraint(prop_name_elem, ns),
        _extract_constraint(value_elem, ns),
    )


def _element_property_matches(
    element, pset_name: str, prop_name: str, constraint: Optional[str]
) -> bool:
    psets = get_psets(element)
    value = psets.get(pset_name, {}).get(prop_name)
    return _matches(value, constraint)


def _int_attr(elem: ET.Element, attr: str, default: int) -> int:
    val = elem.get(attr, str(default))
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _description(ids_path: str) -> str:
    return (
        f"Validates the model against IDS file: {Path(ids_path).name}. "
        "Based on buildingSMART IDS 1.0 standard. "
        "This check does not affect the FM Readiness score."
    )


def _skipped_result() -> Dict[str, Any]:
    return {
        "name": "IDS Validation",
        "score": 100,
        "issues": [{
            "severity": "info",
            "element": "IDS",
            "message": "No IDS file provided — IDS validation skipped",
            "fix": "Run with --ids path/to/file.ids to enable IDS validation.",
        }],
        "stats": {"specifications": 0, "skipped": True},
        "description": (
            "Optional buildingSMART IDS 1.0 validation. "
            "Activate with --ids path/to/file.ids."
        ),
    }


def _error_result(message: str) -> Dict[str, Any]:
    return {
        "name": "IDS Validation",
        "score": 0,
        "issues": [{
            "severity": "error",
            "element": "IDS",
            "message": message,
            "fix": "Check that the IDS file exists and is valid XML.",
        }],
        "stats": {"specifications": 0},
        "description": "buildingSMART IDS 1.0 validation.",
    }
