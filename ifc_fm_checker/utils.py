"""
Utility helpers for IFC property extraction.
Handles all IfcValue types: SingleValue, EnumeratedValue, BoundedValue,
ListValue, TableValue, ReferenceValue, ComplexProperty.
"""

import ifcopenshell
from typing import Any, Dict, List, Optional, Set


def get_psets(element) -> Dict[str, Dict[str, Any]]:
    """
    Return all property sets for an element as:
    { "PsetName": { "PropName": value, ... }, ... }
    Handles all IfcPropertyValue types.
    """
    result = {}
    for rel in getattr(element, "IsDefinedBy", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet"):
                pset_name = pdef.Name or ""
                props = {}
                for prop in pdef.HasProperties:
                    props[prop.Name] = _extract_value(prop)
                result[pset_name] = props
    return result


def _extract_value(prop) -> Any:
    """Extract value from any IFC property type."""
    if prop.is_a("IfcPropertySingleValue"):
        v = prop.NominalValue
        return v.wrappedValue if v else None

    elif prop.is_a("IfcPropertyEnumeratedValue"):
        return [v.wrappedValue for v in prop.EnumerationValues or []]

    elif prop.is_a("IfcPropertyBoundedValue"):
        lower = prop.LowerBoundValue
        upper = prop.UpperBoundValue
        return {
            "lower": lower.wrappedValue if lower else None,
            "upper": upper.wrappedValue if upper else None,
        }

    elif prop.is_a("IfcPropertyListValue"):
        return [v.wrappedValue for v in prop.ListValues or []]

    elif prop.is_a("IfcPropertyTableValue"):
        keys = [v.wrappedValue for v in (prop.DefiningValues or [])]
        vals = [v.wrappedValue for v in (prop.DefinedValues or [])]
        return dict(zip(keys, vals))

    elif prop.is_a("IfcPropertyReferenceValue"):
        ref = prop.PropertyReference
        if ref:
            return str(ref)
        return None

    elif prop.is_a("IfcComplexProperty"):
        sub = {}
        for sub_prop in prop.HasProperties:
            sub[sub_prop.Name] = _extract_value(sub_prop)
        return sub

    return None


def get_all_pset_props(element) -> Dict[str, Any]:
    """
    Flatten all Pset properties into a single dict { PropName: value }.
    Used for asset property search across all Psets.
    """
    flat = {}
    for pset_name, props in get_psets(element).items():
        for k, v in props.items():
            flat[k] = v
    return flat


def get_type_psets(element) -> Dict[str, Dict[str, Any]]:
    """Get Psets from the element's associated IfcTypeObject (if any)."""
    result = {}
    for rel in getattr(element, "IsTypedBy", []):
        type_obj = rel.RelatingType
        if type_obj:
            for rel2 in getattr(type_obj, "HasPropertySets", []):
                if rel2.is_a("IfcPropertySet"):
                    pset_name = rel2.Name or ""
                    props = {}
                    for prop in rel2.HasProperties:
                        props[prop.Name] = _extract_value(prop)
                    result[pset_name] = props
    return result


def get_all_props_including_type(element) -> Dict[str, Any]:
    """Merge instance + type Pset props into one flat dict."""
    flat = get_all_pset_props(element)
    # Type props as fallback
    for pset_name, props in get_type_psets(element).items():
        for k, v in props.items():
            if k not in flat:
                flat[k] = v
    return flat


def get_parent_storey(element) -> Optional[str]:
    """Return the BuildingStorey name containing this element (if any)."""
    for rel in getattr(element, "ContainedInStructure", []):
        container = rel.RelatingStructure
        if container.is_a("IfcBuildingStorey"):
            return container.Name
        if container.is_a("IfcBuilding"):
            return "Building"
        if container.is_a("IfcSite"):
            return "Site"
    return None


def get_containing_space(element) -> Optional[str]:
    """Return the IfcSpace name containing this element (if any)."""
    for rel in getattr(element, "ContainedInStructure", []):
        container = rel.RelatingStructure
        if container.is_a("IfcSpace"):
            return container.Name
    return None


def prop_is_filled(value: Any) -> bool:
    """Check if a property value is considered 'filled' (non-empty, non-None)."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() in ("", "N/A", "n/a", "-", "None", "undefined"):
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def get_entity_label(element) -> str:
    """Return a human-readable label for an IFC element.
    Format: 'IfcType #id (Name)' or 'IfcType #id' if no name.
    Example: 'IfcWall #42 (Muro perimetrale)'
    """
    try:
        ifc_type = element.is_a()
        eid = element.id()
        name = getattr(element, "Name", None) or getattr(element, "LongName", None) or None
        if name:
            return f"{ifc_type} #{eid} ({name})"
        return f"{ifc_type} #{eid}"
    except Exception:
        return f"{element.is_a()} #{element.id()}"


def is_a_subtype(element, base_types: List[str]) -> bool:
    """Check if element is an instance of any base_type or its subtypes."""
    return any(element.is_a(bt) for bt in base_types)


def get_authoring_tool(ifc_file) -> str:
    """Extract authoring tool name from FILE_NAME STEP header."""
    try:
        header = ifc_file.header
        file_name = header.file_name
        if file_name and file_name.originating_system:
            return file_name.originating_system
        if file_name and file_name.preprocessor_version:
            return file_name.preprocessor_version
    except Exception:
        pass
    return "Unknown"


def get_schema(ifc_file) -> str:
    """Return IFC schema version string (e.g. IFC2X3, IFC4)."""
    try:
        return ifc_file.schema
    except Exception:
        return "Unknown"
