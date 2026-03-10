# HANDOFF — ifc-fm-checker development

## Chi sono
Fabio Sbriglio, 29 anni, BIM Expert a Roma. Certificazione BIM Specialist MEP (CEPAS Bureau Veritas), BIM Coordinator in corso (esame ICMQ 25/03/2026). Background tecnico: Python intermedio, Revit/Archicad, IFC, ISO 19650, DM 312/2021, COBie.

## Cosa abbiamo costruito
Un tool Python CLI open source chiamato `ifc-fm-checker` che analizza un file IFC e produce un report di FM Readiness (punteggio 0-100) in HTML e/o JSON. 19 test passati, CI GitHub Actions configurato.

**Obiettivo finale**: pubblicare su GitHub come progetto portfolio professionale, poi eventualmente su PyPI. Il tool è già funzionante e testato — si tratta di estenderlo con feature aggiuntive.

---

## Struttura del repo

```
ifc-fm-checker/
├── ifc_fm_checker/
│   ├── __init__.py
│   ├── config.py          ← pesi, soglie, Pset richiesti, ASSET_TYPES
│   ├── utils.py           ← parser IFC (tutti 8 tipi IfcPropertyValue)
│   ├── runner.py          ← orchestratore: carica IFC, esegue checks, scrive output
│   ├── cli.py             ← entry point CLI con output ANSI colorato
│   ├── checks/
│   │   ├── check_spatial.py    ← Check 1: gerarchia Site>Building>Storey>Space + contenimento
│   │   ├── check_psets.py      ← Check 2: Pset_WallCommon, Pset_SpaceCommon, ecc.
│   │   ├── check_assets.py     ← Check 3: AssetTag, Manufacturer, Model, InstallDate, Warranty
│   │   ├── check_cobie.py      ← Check 4: COBie 2.4 Facility/Floor/Space/Type/Component
│   │   └── check_naming.py     ← Check 5: ISO 19650 / DM 312-2021 naming convention
│   └── report/
│       └── html_report.py      ← report HTML auto-contenuto, no dipendenze esterne
├── tests/
│   └── test_checker.py    ← 19 test (pytest), usa IFC sintetico in-memory
├── .github/workflows/ci.yml   ← CI multi-Python 3.9-3.12
├── pyproject.toml
├── requirements.txt       ← solo ifcopenshell
└── README.md
```

---

## Scoring attuale

| Check | Peso | Cosa controlla |
|---|---|---|
| spatial_structure | 15% | Gerarchia + contenimento elementi in storey |
| pset_completeness | 25% | Pset richiesti presenti e compilati |
| asset_data | 30% | Campi CAFM critici su equipment MEP |
| cobie_readiness | 20% | COBie 2.4 Facility/Floor/Space/Type/Component |
| file_naming | 10% | Naming ISO 19650 / DM 312-2021 |

Rating: FM READY (≥85), MOSTLY READY (≥70), NEEDS WORK (≥50), NOT READY (<50)

---

## Dipendenze

```
ifcopenshell>=0.7.0   (unica dipendenza runtime)
pytest                (solo dev)
```

Funziona su IFC2X3 e IFC4. Per IFC2X3 i tipi IFC4-only (IfcElectricAppliance, IfcSanitaryTerminal, ecc.) sono gestiti con try/except RuntimeError.

---

## Dettagli tecnici importanti

**Ogni check restituisce sempre questo dict:**
```python
{
    "name": str,
    "check_key": str,        # aggiunto dal runner
    "score": int,            # 0-100
    "issues": [
        {
            "severity": "error" | "warning" | "info",
            "element": str,
            "message": str,
            "fix": str,      # istruzione specifica (Revit/Archicad)
        }
    ],
    "stats": dict,           # contatori per il report
    "description": str,
}
```

**utils.py — funzioni chiave:**
- `get_psets(element)` → dict {PsetName: {PropName: value}} — gestisce tutti 8 tipi IfcProperty
- `get_all_props_including_type(element)` → flat dict instance+type Psets
- `prop_is_filled(value)` → False per None, "", "N/A", "-", "None", liste vuote
- `get_parent_storey(element)` → nome storey o None
- `get_authoring_tool(ifc_file)` → da STEP header
- `get_schema(ifc_file)` → "IFC2X3" | "IFC4"

**config.py — strutture principali:**
- `REQUIRED_PSETS` = {IfcType: {PsetName: [props]}}
- `ASSET_TYPES` = lista tipi IFC per equipment (IFC2X3 + IFC4)
- `ASSET_CRITICAL_PROPS` = {field_key: [aliases]} con alias italiani inclusi
- `SCORING_WEIGHTS` = deve sempre sommare a 1.0

---

## Roadmap — feature da sviluppare (in ordine di priorità)

### PRIORITÀ 1 — IDS Validation (buildingSMART IDS 1.0)
Aggiungere `check_ids.py` che:
- Accetta un file `.ids` XML in input (parametro `--ids path/to/file.ids`)
- Parsa le `<specification>` con `<applicability>` + `<requirements>`
- Per ogni elemento IFC che soddisfa l'applicability, verifica i requirements
- Output: pass/fail per specifica, con lista elementi non conformi
- Libreria di riferimento: `ifctester` (parte di ifcopenshell) oppure parsing manuale con `xml.etree`
- Aggiungere al runner come check opzionale (skip se --ids non fornito)
- Peso suggerito: 0% nel punteggio base, report separato

### PRIORITÀ 2 — Output XLSX
Aggiungere `--format xlsx` che produce un Excel con:
- Foglio "Summary": punteggi per check + overall
- Foglio per ogni check: tabella issues con colonne Severity/Element/Message/Fix
- Foglio "Asset Register": lista tutti gli asset con campi trovati/mancanti
- Usare `openpyxl` (aggiungere a requirements opzionali)

### PRIORITÀ 3 — Custom Pset config via YAML
Permettere `--config my_psets.yaml` per sovrascrivere REQUIRED_PSETS:
```yaml
IfcWall:
  Pset_WallCommon:
    - Reference
    - FireRating
  Pset_Custom_ProjectA:
    - ProjectCode
    - CostCenter
```
Merge con config di default o sostituzione completa (flag `--config-mode merge|replace`)

### PRIORITÀ 4 — Classification check
Aggiungere `check_classification.py`:
- Verificare presenza IfcClassificationReference su elementi
- Sistemi supportati: Uniclass 2015, OmniClass, UNI 8290, NBS
- Check che il valore sia nel sistema dichiarato (validazione formato codice)

### PRIORITÀ 5 — Watch mode
`ifc-fm-checker model.ifc --watch` che monitora il file con `watchdog` e rilancia il check ad ogni modifica (utile durante la modellazione in Revit con IFC export automatico)

---

## Come aggiungere un nuovo check

1. Creare `ifc_fm_checker/checks/check_NOME.py` con funzione `run(ifc_file, **kwargs) -> dict`
2. Importarlo in `ifc_fm_checker/checks/__init__.py`
3. Aggiungerlo alla lista `checks` in `runner.py`
4. Aggiungere la chiave e il peso in `config.py → SCORING_WEIGHTS` (ribilanciare i pesi esistenti)
5. Aggiungere test in `tests/test_checker.py`

---

## Come installare in locale (Windows)

```bash
# Prerequisiti: Python 3.9+, pip
pip install ifcopenshell

# Clonare/estrarre il repo, poi:
cd ifc-fm-checker
pip install -e .

# Test
pip install pytest
pytest tests/ -v

# Uso
ifc-fm-checker C:\Projects\edificio.ifc
ifc-fm-checker C:\Projects\edificio.ifc --format both --output-dir C:\Reports\
```

---

## Codice completo

### ifc_fm_checker/__init__.py
```python
"""
ifc-fm-checker — IFC Facility Management Readiness Checker
Check if an IFC model is ready to be imported into a CAFM/CMMS system.

Author: Fabio Sbriglio
License: MIT
"""

__version__ = "1.0.0"
__author__ = "Fabio Sbriglio"
```

### ifc_fm_checker/config.py
```python
"""
FM Readiness Configuration
Defines required Psets, properties, and thresholds for each IFC element type.
Based on ISO 19650, COBie, and Italian DM 312/2021 requirements.
"""

REQUIRED_PSETS = {
    "IfcSpace": {
        "Pset_SpaceCommon": ["Reference", "IsExternal", "GrossFloorArea"],
    },
    "IfcWall": {
        "Pset_WallCommon": ["Reference", "IsExternal", "LoadBearing", "FireRating"],
    },
    "IfcSlab": {
        "Pset_SlabCommon": ["Reference", "IsExternal", "LoadBearing", "FireRating"],
    },
    "IfcColumn": {
        "Pset_ColumnCommon": ["Reference", "LoadBearing", "FireRating"],
    },
    "IfcBeam": {
        "Pset_BeamCommon": ["Reference", "LoadBearing", "FireRating"],
    },
    "IfcDoor": {
        "Pset_DoorCommon": ["Reference", "IsExternal", "FireRating"],
    },
    "IfcWindow": {
        "Pset_WindowCommon": ["Reference", "IsExternal", "FireRating"],
    },
    "IfcFlowTerminal": {
        "Pset_ManufacturerTypeInformation": ["Manufacturer", "ModelReference", "ModelLabel"],
    },
    "IfcFlowSegment": {
        "Pset_ManufacturerTypeInformation": ["Manufacturer"],
    },
    "IfcDistributionControlElement": {
        "Pset_ManufacturerTypeInformation": ["Manufacturer", "ModelReference"],
    },
    "IfcMechanicalFastener": {
        "Pset_ManufacturerTypeInformation": ["Manufacturer"],
    },
    "IfcBuildingElementProxy": {
        "Pset_ManufacturerTypeInformation": ["Manufacturer"],
    },
}

ASSET_TYPES = [
    "IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting",
    "IfcDistributionControlElement", "IfcElectricAppliance",
    "IfcSanitaryTerminal", "IfcAirTerminal", "IfcPump", "IfcBoiler",
    "IfcChiller", "IfcCooledBeam", "IfcUnitaryEquipment",
    "IfcMedicalDevice", "IfcCommunicationsAppliance", "IfcFireSuppressionTerminal",
]

ASSET_CRITICAL_PROPS = {
    "asset_code":   ["AssetTag", "AssetCode", "TagNumber", "Mark"],
    "manufacturer": ["Manufacturer", "Produttore"],
    "model":        ["ModelReference", "ModelLabel", "ArticleNumber", "Modello"],
    "install_date": ["InstallationDate", "ManufactureDate", "DataInstallazione"],
    "warranty":     ["WarrantyDuration", "Garanzia", "WarrantyPeriod"],
}

COBIE_FACILITY_PROPS = ["ProjectName", "SiteName"]
COBIE_SPACE_PROPS    = ["GrossFloorArea", "NetFloorArea"]
COBIE_COMPONENT_PROPS = ["Manufacturer", "ModelReference", "ModelLabel"]
COBIE_TYPE_PROPS     = ["Manufacturer", "ModelReference", "ReplacementCost"]

ISO19650_FILE_NAMING = {
    "description": "Italian DM 312/2021 + ISO 19650 naming: {Project}-{Originator}-{Volume/System}-{Level/Location}-{Type}-{Role}-{Classifier}_{Revision}.{ext}",
    "separators": ["-", "_"],
    "min_fields": 6,
    "allowed_types": [
        "M3","M2","DR","CA","CO","CP","CR","FI","HS","IE","MI","MS",
        "PP","PR","RD","RI","RO","RS","SA","SH","SK","SP","SU",
    ],
}

SCORING_WEIGHTS = {
    "spatial_structure": 0.15,
    "pset_completeness":  0.25,
    "asset_data":         0.30,
    "cobie_readiness":    0.20,
    "file_naming":        0.10,
}

RATING_THRESHOLDS = {"excellent": 85, "good": 70, "fair": 50, "poor": 0}
RATING_COLORS     = {"excellent": "#2e7d32", "good": "#f9a825", "fair": "#e65100", "poor": "#b71c1c"}
RATING_LABELS     = {"excellent": "FM READY", "good": "MOSTLY READY", "fair": "NEEDS WORK", "poor": "NOT READY"}
```

### ifc_fm_checker/utils.py
```python
"""
Utility helpers for IFC property extraction.
Handles all IfcValue types: SingleValue, EnumeratedValue, BoundedValue,
ListValue, TableValue, ReferenceValue, ComplexProperty.
"""

import ifcopenshell
from typing import Any, Dict, List, Optional, Set


def get_psets(element) -> Dict[str, Dict[str, Any]]:
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
    if prop.is_a("IfcPropertySingleValue"):
        v = prop.NominalValue
        return v.wrappedValue if v else None
    elif prop.is_a("IfcPropertyEnumeratedValue"):
        return [v.wrappedValue for v in prop.EnumerationValues or []]
    elif prop.is_a("IfcPropertyBoundedValue"):
        lower = prop.LowerBoundValue
        upper = prop.UpperBoundValue
        return {"lower": lower.wrappedValue if lower else None, "upper": upper.wrappedValue if upper else None}
    elif prop.is_a("IfcPropertyListValue"):
        return [v.wrappedValue for v in prop.ListValues or []]
    elif prop.is_a("IfcPropertyTableValue"):
        keys = [v.wrappedValue for v in (prop.DefiningValues or [])]
        vals = [v.wrappedValue for v in (prop.DefinedValues or [])]
        return dict(zip(keys, vals))
    elif prop.is_a("IfcPropertyReferenceValue"):
        ref = prop.PropertyReference
        return str(ref) if ref else None
    elif prop.is_a("IfcComplexProperty"):
        return {sp.Name: _extract_value(sp) for sp in prop.HasProperties}
    return None


def get_all_pset_props(element) -> Dict[str, Any]:
    flat = {}
    for pset_name, props in get_psets(element).items():
        for k, v in props.items():
            flat[k] = v
    return flat


def get_type_psets(element) -> Dict[str, Dict[str, Any]]:
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
    flat = get_all_pset_props(element)
    for pset_name, props in get_type_psets(element).items():
        for k, v in props.items():
            if k not in flat:
                flat[k] = v
    return flat


def get_parent_storey(element) -> Optional[str]:
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
    for rel in getattr(element, "ContainedInStructure", []):
        container = rel.RelatingStructure
        if container.is_a("IfcSpace"):
            return container.Name
    return None


def prop_is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() in ("", "N/A", "n/a", "-", "None", "undefined"):
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def get_entity_label(element) -> str:
    name = getattr(element, "Name", None) or ""
    tag  = getattr(element, "Tag",  None) or ""
    guid = getattr(element, "GlobalId", "?")
    return f"{element.is_a()} [{name or tag or guid}]"


def is_a_subtype(element, base_types: List[str]) -> bool:
    return any(element.is_a(bt) for bt in base_types)


def get_authoring_tool(ifc_file) -> str:
    try:
        fn = ifc_file.header.file_name
        if fn and fn.originating_system:
            return fn.originating_system
        if fn and fn.preprocessor_version:
            return fn.preprocessor_version
    except Exception:
        pass
    return "Unknown"


def get_schema(ifc_file) -> str:
    try:
        return ifc_file.schema
    except Exception:
        return "Unknown"
```

### ifc_fm_checker/checks/check_spatial.py
```python
"""
Check 1: Spatial Structure
Site > Building > BuildingStorey > Space hierarchy + element containment.
"""

import ifcopenshell
from typing import Dict, Any
from ifc_fm_checker.utils import get_parent_storey, get_entity_label


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}

    sites     = ifc_file.by_type("IfcSite")
    buildings = ifc_file.by_type("IfcBuilding")
    storeys   = ifc_file.by_type("IfcBuildingStorey")
    spaces    = ifc_file.by_type("IfcSpace")

    stats.update({"sites": len(sites), "buildings": len(buildings),
                  "storeys": len(storeys), "spaces": len(spaces)})

    hierarchy_score = 100
    if not sites:
        issues.append({"severity": "warning", "element": "Model",
                       "message": "No IfcSite found — spatial hierarchy incomplete",
                       "fix": "Add a site entity as root of the spatial structure"})
        hierarchy_score -= 15
    if not buildings:
        issues.append({"severity": "error", "element": "Model",
                       "message": "No IfcBuilding found — spatial hierarchy incomplete",
                       "fix": "Add at least one IfcBuilding under IfcSite"})
        hierarchy_score -= 20
    if not storeys:
        issues.append({"severity": "error", "element": "Model",
                       "message": "No IfcBuildingStorey found — cannot assign elements to floors",
                       "fix": "Add IfcBuildingStorey entities (one per level)"})
        hierarchy_score -= 30
    if not spaces:
        issues.append({"severity": "warning", "element": "Model",
                       "message": "No IfcSpace found — FM space assignment not possible",
                       "fix": "Add IfcSpace entities for each room/zone. Required for CAFM area management."})
        hierarchy_score -= 20

    element_types_to_check = [
        "IfcWall", "IfcSlab", "IfcColumn", "IfcBeam", "IfcDoor", "IfcWindow",
        "IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting",
        "IfcDistributionControlElement", "IfcBuildingElementProxy",
    ]
    total_elements = 0
    uncontained = []
    for etype in element_types_to_check:
        for el in ifc_file.by_type(etype):
            total_elements += 1
            if get_parent_storey(el) is None:
                uncontained.append(get_entity_label(el))

    stats["total_physical_elements"] = total_elements
    stats["uncontained_elements"] = len(uncontained)

    containment_score = 100
    if total_elements > 0:
        pct = len(uncontained) / total_elements * 100
        containment_score = max(0, 100 - int(pct * 1.5))
        if uncontained:
            sample = uncontained[:20]
            more = len(uncontained) - 20 if len(uncontained) > 20 else 0
            msg = f"{len(uncontained)} element(s) not contained in any IfcBuildingStorey ({pct:.1f}%)"
            if more:
                msg += f" — showing first 20, {more} more"
            issues.append({"severity": "warning", "element": ", ".join(sample), "message": msg,
                           "fix": "In Revit: use 'Room Bounding' on all elements. Ensure elements are placed within a storey level."})

    unnamed_spaces = [getattr(s, "GlobalId", "?") for s in spaces
                      if not (getattr(s, "Name", None) or "").strip()]
    stats["unnamed_spaces"] = len(unnamed_spaces)
    if unnamed_spaces:
        issues.append({"severity": "warning", "element": f"{len(unnamed_spaces)} IfcSpace(s)",
                       "message": f"{len(unnamed_spaces)} spaces have no Name — CAFM cannot identify them",
                       "fix": "Assign a meaningful name to every IfcSpace (room number or functional label)"})

    spaces_no_area = []
    for space in spaces:
        has_area = False
        for rel in getattr(space, "IsDefinedBy", []):
            if rel.is_a("IfcRelDefinesByProperties"):
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet"):
                    for prop in pdef.HasProperties:
                        if prop.Name in ("GrossFloorArea", "NetFloorArea") and \
                                hasattr(prop, "NominalValue") and prop.NominalValue and prop.NominalValue.wrappedValue:
                            has_area = True
        if not has_area:
            spaces_no_area.append(getattr(space, "Name", getattr(space, "GlobalId", "?")))

    stats["spaces_without_area"] = len(spaces_no_area)
    if spaces_no_area:
        pct = len(spaces_no_area) / max(len(spaces), 1) * 100
        issues.append({"severity": "info", "element": f"{len(spaces_no_area)} IfcSpace(s)",
                       "message": f"{len(spaces_no_area)} spaces ({pct:.0f}%) have no GrossFloorArea in Pset_SpaceCommon",
                       "fix": "Compute areas in the authoring tool and export to IFC with Pset_SpaceCommon.GrossFloorArea"})

    if total_elements == 0 and len(spaces) == 0:
        final_score = max(0, hierarchy_score)
    else:
        final_score = max(0, int((hierarchy_score * 0.4) + (containment_score * 0.6)))

    return {"name": "Spatial Structure", "score": final_score, "issues": issues, "stats": stats,
            "description": "Verifies Site > Building > Storey > Space hierarchy and that all physical elements are assigned to a storey."}
```

### ifc_fm_checker/checks/check_psets.py
```python
"""
Check 2: Pset Completeness
Required PropertySets per element type (ISO 19650).
"""

import ifcopenshell
from typing import Dict, Any
from ifc_fm_checker.config import REQUIRED_PSETS
from ifc_fm_checker.utils import get_psets, prop_is_filled, get_entity_label


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}
    type_scores = {}
    total_checks = passed_checks = 0

    for ifc_type, pset_requirements in REQUIRED_PSETS.items():
        elements = ifc_file.by_type(ifc_type)
        if not elements:
            continue
        type_pass = type_total = 0
        type_issues = []

        for element in elements:
            psets = get_psets(element)
            for pset_name, required_props in pset_requirements.items():
                actual_pset = psets.get(pset_name, {})
                for prop in required_props:
                    type_total += 1
                    total_checks += 1
                    value = actual_pset.get(prop, None)
                    if pset_name not in psets:
                        type_issues.append({"severity": "error", "element": get_entity_label(element),
                            "message": f"Pset '{pset_name}' not found — property '{prop}' missing",
                            "fix": f"In Revit: assign '{pset_name}' to the type/instance. In IFC export: ensure Pset_Common export is enabled."})
                    elif prop not in actual_pset:
                        type_issues.append({"severity": "error", "element": get_entity_label(element),
                            "message": f"'{pset_name}.{prop}' property not found",
                            "fix": f"Add property '{prop}' to '{pset_name}'. Check IFC export settings."})
                    elif not prop_is_filled(value):
                        type_issues.append({"severity": "warning", "element": get_entity_label(element),
                            "message": f"'{pset_name}.{prop}' is empty or null",
                            "fix": f"Fill in '{prop}' value for this element in the authoring tool."})
                    else:
                        type_pass += 1
                        passed_checks += 1

        issues.extend(_deduplicate_issues(type_issues))
        score = int(type_pass / type_total * 100) if type_total > 0 else 100
        type_scores[ifc_type] = {"score": score, "total_elements": len(elements),
                                  "checks_passed": type_pass, "checks_total": type_total}
        stats[ifc_type] = type_scores[ifc_type]

    overall_score = int(passed_checks / total_checks * 100) if total_checks > 0 else 100
    return {"name": "Pset Completeness", "score": overall_score, "issues": issues,
            "stats": {"total_checks": total_checks, "passed_checks": passed_checks, "by_type": type_scores},
            "description": "Checks that required Property Sets are present and filled according to ISO 19650 requirements."}


def _deduplicate_issues(issues):
    seen = {}
    for issue in issues:
        key = issue["message"]
        if key not in seen:
            seen[key] = {**issue, "count": 1, "elements": [issue["element"]]}
        else:
            seen[key]["count"] += 1
            if len(seen[key]["elements"]) < 5:
                seen[key]["elements"].append(issue["element"])
    result = []
    for key, item in seen.items():
        if item["count"] > 1:
            item["element"] = f"{item['elements'][0]} and {item['count'] - 1} more"
            item["message"] = f"[×{item['count']}] {item['message']}"
        del item["elements"]
        del item["count"]
        result.append(item)
    return result
```

### ifc_fm_checker/checks/check_assets.py
```python
"""
Check 3: Asset Data
CAFM-critical fields on maintainable equipment.
"""

import ifcopenshell
from typing import Dict, Any, List
from ifc_fm_checker.config import ASSET_TYPES, ASSET_CRITICAL_PROPS
from ifc_fm_checker.utils import get_all_props_including_type, prop_is_filled, get_entity_label, get_parent_storey


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}
    asset_elements = []
    for asset_type in ASSET_TYPES:
        try:
            asset_elements.extend(ifc_file.by_type(asset_type))
        except RuntimeError:
            pass  # type not in this schema version

    if not asset_elements:
        return {"name": "Asset Data", "score": 100,
                "issues": [{"severity": "info", "element": "Model",
                             "message": "No maintainable asset types found in this model",
                             "fix": "If this is an architectural-only model, this check may not apply."}],
                "stats": {"total_assets": 0},
                "description": "Checks CAFM-critical properties on maintainable equipment."}

    stats["total_assets"] = len(asset_elements)
    field_results = {f: {"present": 0, "missing": 0} for f in ASSET_CRITICAL_PROPS}
    missing_by_field = {f: [] for f in ASSET_CRITICAL_PROPS}
    per_element_scores = []

    for element in asset_elements:
        all_props = get_all_props_including_type(element)
        label = get_entity_label(element)
        storey = get_parent_storey(element) or "Unknown"
        element_pass = 0
        for field_key, aliases in ASSET_CRITICAL_PROPS.items():
            found = any(prop_is_filled(all_props.get(alias)) for alias in aliases)
            if found:
                field_results[field_key]["present"] += 1
                element_pass += 1
            else:
                field_results[field_key]["missing"] += 1
                missing_by_field[field_key].append({"label": label, "storey": storey})
        per_element_scores.append(element_pass / len(ASSET_CRITICAL_PROPS))

    for field_key, missing_list in missing_by_field.items():
        if not missing_list:
            continue
        aliases = ASSET_CRITICAL_PROPS[field_key]
        pct = len(missing_list) / len(asset_elements) * 100
        severity = "error" if pct > 50 else "warning"
        sample = [m["label"] for m in missing_list[:3]]
        more = len(missing_list) - 3 if len(missing_list) > 3 else 0
        issues.append({"severity": severity,
                       "element": ", ".join(sample) + (f" and {more} more" if more else ""),
                       "message": f"[×{len(missing_list)}] Asset field '{field_key}' missing ({pct:.0f}% of {len(asset_elements)} assets) — expected in: {', '.join(aliases)}",
                       "fix": _get_fix(field_key)})

    avg_score = int(sum(per_element_scores) / len(per_element_scores) * 100) if per_element_scores else 100
    stats["field_coverage"] = {
        f: {"present": field_results[f]["present"], "missing": field_results[f]["missing"],
            "pct_complete": round(field_results[f]["present"] / len(asset_elements) * 100, 1)}
        for f in ASSET_CRITICAL_PROPS}

    return {"name": "Asset Data", "score": avg_score, "issues": issues, "stats": stats,
            "description": "Verifies that maintainable equipment has CAFM-critical fields: AssetTag/Mark, Manufacturer, ModelReference, InstallationDate, WarrantyDuration."}


def _get_fix(field_key):
    fixes = {
        "asset_code":   "In Revit: add an 'AssetTag' or 'Mark' shared parameter to the family. Fill values before IFC export.",
        "manufacturer": "In Revit: fill 'Manufacturer' in the Type Properties of each family.",
        "model":        "In Revit: fill 'Model' in Type Properties. Ensure IFC export maps it to Pset_ManufacturerTypeInformation.ModelReference.",
        "install_date": "Add an 'InstallationDate' shared parameter to MEP families.",
        "warranty":     "Add a 'WarrantyDuration' parameter (in months) to equipment families.",
    }
    return fixes.get(field_key, "Fill in the required field in the authoring tool.")
```

### ifc_fm_checker/checks/check_cobie.py
```python
"""
Check 4: COBie Readiness (COBie 2.4 / ISO 19650-3)
Facility, Floor, Space, Type, Component sheets.
"""

import ifcopenshell
from typing import Dict, Any
from ifc_fm_checker.utils import get_psets, get_all_props_including_type, prop_is_filled


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}
    sheet_scores = {}

    # FACILITY
    projects = ifc_file.by_type("IfcProject")
    facility_score = 100
    for proj in projects:
        if not (getattr(proj, "Name", None) or "").strip():
            issues.append({"severity": "warning", "element": "IfcProject",
                           "message": "IfcProject has no Name — COBie Facility.Name will be empty",
                           "fix": "Set a project name in the authoring tool's project settings."})
            facility_score -= 40
        if not getattr(proj, "Description", None):
            issues.append({"severity": "info", "element": "IfcProject",
                           "message": "IfcProject has no Description — COBie Facility.Description will be empty",
                           "fix": "Add a project description in the authoring tool settings."})
            facility_score -= 10
    sheet_scores["Facility"] = max(0, facility_score)
    stats["projects"] = len(projects)

    # FLOOR
    storeys = ifc_file.by_type("IfcBuildingStorey")
    storey_issues = 0
    for storey in storeys:
        name = getattr(storey, "Name", None)
        if not name or not name.strip():
            storey_issues += 1
            issues.append({"severity": "warning", "element": f"IfcBuildingStorey #{getattr(storey, 'GlobalId', '?')}",
                           "message": "Storey has no Name — COBie Floor.Name will be empty",
                           "fix": "Assign a name to every storey (e.g. 'Ground Floor', 'Level 01')."})
        if getattr(storey, "Elevation", None) is None:
            issues.append({"severity": "info", "element": f"Storey '{name or '?'}'",
                           "message": "Storey elevation not set — COBie Floor.Elevation will be missing",
                           "fix": "Set storey elevation in the authoring tool."})
    sheet_scores["Floor"] = max(0, int(100 - (storey_issues / max(len(storeys), 1) * 100)))
    stats["storeys"] = len(storeys)

    # SPACE
    spaces = ifc_file.by_type("IfcSpace")
    space_issues = sum(2 if not getattr(s, "Name", None) else
                       (1 if not (getattr(s, "Description", None) or getattr(s, "LongName", None)) else 0)
                       for s in spaces)
    sheet_scores["Space"] = max(0, int(100 - (space_issues / max(len(spaces) * 2, 1) * 100)))
    stats["spaces"] = len(spaces)
    if len(spaces) == 0:
        issues.append({"severity": "error", "element": "Model",
                       "message": "No IfcSpace found — COBie Space sheet will be empty",
                       "fix": "Add IfcSpace entities for each room/zone."})
        sheet_scores["Space"] = 0

    # TYPE
    type_objects = ifc_file.by_type("IfcTypeObject")
    type_issues = 0
    for type_obj in type_objects:
        props = {}
        for pset in getattr(type_obj, "HasPropertySets", []):
            if pset.is_a("IfcPropertySet"):
                for prop in pset.HasProperties:
                    if hasattr(prop, "NominalValue") and prop.NominalValue:
                        props[prop.Name] = prop.NominalValue.wrappedValue
        if not prop_is_filled(props.get("Manufacturer") or props.get("Produttore")):
            type_issues += 1
        if not prop_is_filled(props.get("ModelReference") or props.get("ModelLabel")):
            type_issues += 1
    sheet_scores["Type"] = max(0, int(100 - (type_issues / max(len(type_objects) * 2, 1) * 100)))
    stats["type_objects"] = len(type_objects)
    if type_objects and type_issues > 0:
        pct = type_issues / (len(type_objects) * 2) * 100
        issues.append({"severity": "warning", "element": f"{len(type_objects)} IfcTypeObject(s)",
                       "message": f"Type objects missing Manufacturer/ModelReference data ({pct:.0f}% of fields empty) — COBie Type sheet will be incomplete",
                       "fix": "Fill Manufacturer and ModelReference in Type Properties of each family/type."})

    # COMPONENT
    components = []
    for ct in ["IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting", "IfcDistributionControlElement",
               "IfcElectricAppliance", "IfcSanitaryTerminal", "IfcAirTerminal"]:
        try:
            components.extend(ifc_file.by_type(ct))
        except RuntimeError:
            pass
    tags = set()
    duplicate_tags = []
    no_tag = 0
    for comp in components:
        tag = getattr(comp, "Tag", None) or getattr(comp, "Name", None)
        if not tag or not str(tag).strip():
            no_tag += 1
        else:
            tag_str = str(tag).strip()
            if tag_str in tags:
                duplicate_tags.append(tag_str)
            tags.add(tag_str)
    component_score = 100
    if components:
        if no_tag > 0:
            pct = no_tag / len(components) * 100
            component_score -= int(pct * 0.8)
            issues.append({"severity": "warning", "element": f"{no_tag} component(s)",
                           "message": f"{no_tag} components ({pct:.0f}%) have no Tag — COBie Component.TagNumber will be empty",
                           "fix": "Assign unique Tag/Mark values to all equipment instances."})
        if duplicate_tags:
            component_score -= 15
            issues.append({"severity": "warning", "element": f"{len(duplicate_tags)} duplicate tag(s)",
                           "message": f"Duplicate Tag values found: {', '.join(set(duplicate_tags[:5]))} — COBie requires unique component identifiers",
                           "fix": "Ensure each equipment instance has a unique Tag/Mark value."})
    sheet_scores["Component"] = max(0, component_score)
    stats["components"] = len(components)
    stats["sheet_scores"] = sheet_scores

    weights = {"Facility": 0.15, "Floor": 0.15, "Space": 0.25, "Type": 0.25, "Component": 0.20}
    overall = sum(sheet_scores.get(k, 100) * w for k, w in weights.items())
    return {"name": "COBie Readiness", "score": int(overall), "issues": issues, "stats": stats,
            "description": "Checks minimum data for a valid COBie export: Facility, Floor, Space, Type, Component sheets. Based on COBie 2.4 and UK BIM Framework."}
```

### ifc_fm_checker/checks/check_naming.py
```python
"""
Check 5: ISO 19650 / DM 312-2021 File Naming
"""

import os, re
from pathlib import Path
from typing import Dict, Any, List, Optional
from ifc_fm_checker.config import ISO19650_FILE_NAMING

ALLOWED_TYPES    = set(ISO19650_FILE_NAMING["allowed_types"])
REVISION_PATTERN = re.compile(r"^[A-Z]\d{1,3}$")
FIELD_PATTERN    = re.compile(r"^[A-Za-z0-9]+$")


def run(ifc_file, file_path=None, folder_path=None) -> Dict[str, Any]:
    issues = []
    stats = {}
    files_checked = []
    stats["ifc_project_name"] = _get_project_name(ifc_file)

    if file_path:
        filename = Path(file_path).name
        fr = _check_filename(filename)
        fr["source"] = "IFC file"
        files_checked.append(fr)
        for err in fr["errors"]:
            issues.append({"severity": "warning", "element": filename, "message": err, "fix": _get_naming_fix(err)})

    if folder_path and os.path.isdir(folder_path):
        for fname in os.listdir(folder_path):
            if fname.startswith(".") or fname.startswith("~"):
                continue
            if os.path.isfile(os.path.join(folder_path, fname)):
                fr = _check_filename(fname)
                fr["source"] = "folder"
                files_checked.append(fr)
                if not fr["valid"]:
                    for err in fr["errors"]:
                        issues.append({"severity": "info", "element": fname, "message": err, "fix": _get_naming_fix(err)})

    stats.update({"files_checked": len(files_checked),
                  "files_valid": sum(1 for f in files_checked if f["valid"]),
                  "files_invalid": sum(1 for f in files_checked if not f["valid"])})

    if not files_checked:
        header_filename = _get_header_filename(ifc_file)
        if header_filename:
            fr = _check_filename(header_filename)
            files_checked.append(fr)
            if not fr["valid"]:
                for err in fr["errors"]:
                    issues.append({"severity": "info", "element": f"Header: {header_filename}", "message": err, "fix": _get_naming_fix(err)})
        else:
            issues.append({"severity": "info", "element": "File naming",
                           "message": "No file path provided — cannot validate ISO 19650 naming convention",
                           "fix": "Run with --file or --folder to validate file naming."})
            return {"name": "File Naming (ISO 19650 / DM 312-2021)", "score": 100,
                    "issues": issues, "stats": stats,
                    "description": "Validates ISO 19650 / Italian DM 312-2021 file naming convention."}

    score = int(stats.get("files_valid", 0) / max(stats.get("files_checked", 1), 1) * 100)
    return {"name": "File Naming (ISO 19650 / DM 312-2021)", "score": score, "issues": issues,
            "stats": stats, "files_checked": files_checked,
            "description": "Validates that file names follow the ISO 19650-2 / Italian DM 312-2021 convention."}


def _check_filename(filename):
    errors, warnings, parsed = [], [], {}
    name = Path(filename).stem
    ext  = Path(filename).suffix.lower()
    if ext not in {".ifc",".rvt",".dwg",".dxf",".pdf",".xlsx",".docx",".nwd",".nwc",".pln"}:
        warnings.append(f"Unusual file extension: '{ext}'")
    if " " in name:
        errors.append("Filename contains spaces — use hyphens as separators")
    parts_rev = name.rsplit("_", 1)
    if len(parts_rev) == 2:
        body, revision = parts_rev
        parsed["revision"] = revision
        if not REVISION_PATTERN.match(revision):
            errors.append(f"Revision '{revision}' does not match pattern [A-Z]dd (e.g. P01, S01, C01)")
    else:
        body = name
        errors.append("No revision suffix found (e.g. _P01 for preliminary, _S01 for shared)")
        parsed["revision"] = None
    fields = body.split("-")
    parsed["fields"] = fields
    min_fields = ISO19650_FILE_NAMING["min_fields"]
    if len(fields) < min_fields:
        errors.append(f"Only {len(fields)} fields found — minimum {min_fields} required (Project-Originator-Volume-Level-Type-Role)")
    else:
        if len(fields) > 4:
            doc_type = fields[4].upper()
            if doc_type not in ALLOWED_TYPES:
                warnings.append(f"Document type '{doc_type}' not in standard list.")
            else:
                parsed["doc_type"] = doc_type
        for i, field in enumerate(fields):
            if not FIELD_PATTERN.match(field) and field:
                errors.append(f"Field {i+1} '{field}' contains invalid characters — only alphanumeric allowed")
    return {"filename": filename, "valid": len(errors) == 0, "errors": errors, "warnings": warnings, "parsed": parsed}


def _get_project_name(ifc_file):
    try:
        projects = ifc_file.by_type("IfcProject")
        if projects:
            return projects[0].Name or "Unknown"
    except Exception:
        pass
    return "Unknown"


def _get_header_filename(ifc_file):
    try:
        fn = ifc_file.header.file_name
        if fn and fn.name:
            return os.path.basename(fn.name)
    except Exception:
        pass
    return None


def _get_naming_fix(error_msg):
    if "spaces" in error_msg:
        return "Replace spaces with hyphens. Example: ProjectA-OrigB-B00-00-M3-AR-0001_P01.ifc"
    if "revision" in error_msg.lower():
        return "Add revision suffix: _P01 (preliminary), _S01 (shared/issued), _D01 (for information), _A01 (approved)"
    if "fields" in error_msg:
        return "Use format: {Project}-{Originator}-{Volume}-{Level}-{Type}-{Role}-{Classifier}_{Rev}.ext\nExample: PROJ01-ARCH01-B00-00-M3-AR-MODELS_S01.ifc"
    if "document type" in error_msg.lower():
        return "Use standard document types: M3 (3D model), DR (drawing), SP (spec), CA (calc)"
    if "invalid characters" in error_msg:
        return "Use only letters and numbers in each field."
    return "Check ISO 19650-2 Annex A for the complete naming convention rules."
```

### ifc_fm_checker/runner.py
```python
"""
Core runner — orchestrates all checks and produces the final report.
"""

import json, os
from pathlib import Path
from typing import Dict, Any, Optional
import ifcopenshell

from ifc_fm_checker.config import SCORING_WEIGHTS
from ifc_fm_checker.utils import get_authoring_tool, get_schema
from ifc_fm_checker.checks import check_spatial, check_psets, check_assets, check_cobie, check_naming
from ifc_fm_checker.report import html_report


def run_all_checks(ifc_path, folder_path=None, output_dir=None, output_format="html", verbose=False):
    ifc_path = str(ifc_path)
    if not os.path.exists(ifc_path):
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")
    if verbose:
        print(f"  Loading {os.path.basename(ifc_path)}...")
    ifc_file = ifcopenshell.open(ifc_path)
    model_info = _get_model_info(ifc_file, ifc_path)
    if verbose:
        print(f"  Schema: {model_info['schema']} | Tool: {model_info['authoring_tool']}")

    results = []
    checks = [
        ("spatial_structure", check_spatial.run, [ifc_file], {}),
        ("pset_completeness",  check_psets.run,   [ifc_file], {}),
        ("asset_data",         check_assets.run,  [ifc_file], {}),
        ("cobie_readiness",    check_cobie.run,   [ifc_file], {}),
        ("file_naming",        check_naming.run,  [ifc_file], {"file_path": ifc_path, "folder_path": folder_path}),
    ]
    for check_key, check_fn, args, kwargs in checks:
        if verbose:
            print(f"  Running: {check_key}...")
        try:
            result = check_fn(*args, **kwargs)
            result["check_key"] = check_key
            results.append(result)
        except Exception as e:
            results.append({"name": check_key, "check_key": check_key, "score": 0,
                             "issues": [{"severity": "error", "element": "Runner",
                                         "message": f"Check failed: {e}",
                                         "fix": "Report this issue on GitHub."}],
                             "stats": {}, "description": f"Check '{check_key}' could not be completed."})

    from ifc_fm_checker.config import RATING_THRESHOLDS
    overall_score = int(sum(r["score"] * SCORING_WEIGHTS.get(r.get("check_key", ""), 0) for r in results))
    if overall_score >= RATING_THRESHOLDS["excellent"]:   rating = "FM READY"
    elif overall_score >= RATING_THRESHOLDS["good"]:      rating = "MOSTLY READY"
    elif overall_score >= RATING_THRESHOLDS["fair"]:      rating = "NEEDS WORK"
    else:                                                  rating = "NOT READY"

    if output_dir is None:
        output_dir = os.path.dirname(ifc_path) or "."
    stem = Path(ifc_path).stem
    output_file = None

    if output_format in ("html", "both"):
        html_path = os.path.join(output_dir, f"{stem}_fm_report.html")
        html_report.render(results, overall_score, model_info, html_path)
        output_file = html_path
        if verbose: print(f"  HTML report: {html_path}")

    if output_format in ("json", "both"):
        json_path = os.path.join(output_dir, f"{stem}_fm_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"overall_score": overall_score, "rating": rating,
                       "model_info": model_info, "checks": results}, f, indent=2, default=str)
        if output_file is None: output_file = json_path
        if verbose: print(f"  JSON report: {json_path}")

    return {"overall_score": overall_score, "rating": rating, "model_info": model_info,
            "results": results, "output_file": output_file}


def _get_model_info(ifc_file, ifc_path):
    schema = get_schema(ifc_file)
    tool   = get_authoring_tool(ifc_file)
    element_counts = {}
    for etype in ["IfcWall","IfcSlab","IfcColumn","IfcBeam","IfcDoor","IfcWindow",
                  "IfcSpace","IfcBuildingStorey","IfcFlowTerminal","IfcFlowSegment"]:
        n = len(ifc_file.by_type(etype))
        if n > 0: element_counts[etype] = n
    total = len(ifc_file.by_type("IfcProduct"))
    project_name = "Unknown"
    try:
        projects = ifc_file.by_type("IfcProject")
        if projects: project_name = projects[0].Name or "Unknown"
    except Exception: pass
    return {"filename": os.path.basename(ifc_path), "file_path": ifc_path, "schema": schema,
            "authoring_tool": tool, "project_name": project_name, "total_elements": total,
            "element_summary": ", ".join(f"{v} {k[3:]}" for k, v in element_counts.items())}
```

### pyproject.toml
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ifc-fm-checker"
version = "1.0.0"
description = "IFC Facility Management Readiness Checker — verify if an IFC model is ready for CAFM/CMMS import"
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "Fabio Sbriglio" }]
keywords = ["BIM", "IFC", "ISO 19650", "Facility Management", "CAFM", "COBie", "Digital Twin"]
requires-python = ">=3.9"
dependencies = ["ifcopenshell>=0.7.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov"]

[project.scripts]
ifc-fm-checker = "ifc_fm_checker.cli:main"

[project.urls]
Homepage = "https://github.com/fabio-sbriglio/ifc-fm-checker"

[tool.setuptools.packages.find]
where = ["."]
include = ["ifc_fm_checker*"]
```

---

## Stato attuale dei test

```
19 passed in 0.82s — pytest tests/ -v
```

Test coperti: config validation, utils (tutti 8 tipi IfcProperty), check_spatial, check_psets, check_assets, check_cobie, check_naming (valido/invalido/no_revision), runner HTML, runner JSON, runner checks presenti, runner file mancante, runner model_info.

---

## Prossima sessione — cosa fare

Puoi partire da qualsiasi punto della roadmap. Suggerisco:

1. **IDS Validation** — la feature con più valore professionale. Inizia con: "Aggiungi il check IDS usando `ifctester` (parte di ifcopenshell). Il check deve accettare un file .ids in input, parsare le specification, e produrre pass/fail per elemento con gli stessi pattern già usati negli altri check."

2. **Output XLSX** — più veloce da implementare. Inizia con: "Aggiungi `--format xlsx` usando openpyxl. Fogli: Summary, uno per ogni check, Asset Register."

3. **Pubblicazione GitHub** — se vuoi prima pubblicare il repo com'è e poi sviluppare. Condividi il file ZIP che hai già.
