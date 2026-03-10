# ifc-fm-checker

**IFC Facility Management Readiness Checker**

A Python CLI tool that analyzes an IFC model and produces a scored readiness report for CAFM/CMMS import. Built for BIM Coordinators and Information Managers who need to verify model quality before handing over to the FM team.

[![CI](https://github.com/fabio-sbriglio/ifc-fm-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/fabio-sbriglio/ifc-fm-checker/actions)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## What it does

Runs 5 automated checks on any IFC file (IFC2x3 / IFC4) and produces a weighted score (0–100) with an HTML or JSON report:

| Check | Weight | What it checks |
|---|---|---|
| **Spatial Structure** | 15% | Site → Building → Storey → Space hierarchy; element containment |
| **Pset Completeness** | 25% | Required PropertySets and properties per element type (ISO 19650) |
| **Asset Data** | 30% | CAFM-critical fields: AssetTag, Manufacturer, Model, InstallDate, Warranty |
| **COBie Readiness** | 20% | Minimum data for COBie 2.4 Facility/Floor/Space/Type/Component sheets |
| **File Naming** | 10% | ISO 19650-2 / Italian DM 312-2021 naming convention |

Each issue includes a **recommended fix** with authoring-tool-specific guidance (Revit, Archicad).

---

## Quick start

```bash
pip install ifc-fm-checker
ifc-fm-checker my_building.ifc
```

Output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IFC FM Readiness Checker  v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  File   : hospital_block_A.ifc

  Check Results
  ────────────────────────────────────────────────────────
  Spatial Structure    (15%)          88/100  [██████████░░] ✓ OK
  Pset Completeness   (25%)           72/100  [████████░░░░]  3 issue(s)
  Asset Data          (30%)           45/100  [█████░░░░░░░]  5 issue(s)
  COBie Readiness     (20%)           61/100  [███████░░░░░]  2 issue(s)
  File Naming ISO 19650(10%)         100/100  [████████████] ✓ OK
  ────────────────────────────────────────────────────────

  Overall Score  : 66/100
  FM Readiness   : NEEDS WORK

  Report saved to: hospital_block_A_fm_report.html
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Installation

### From PyPI (recommended)
```bash
pip install ifc-fm-checker
```

### From source
```bash
git clone https://github.com/fabio-sbriglio/ifc-fm-checker.git
cd ifc-fm-checker
pip install -e .
```

**Requirements:** Python 3.9+ — `ifcopenshell` is the only dependency.

---

## Usage

### Basic — HTML report (default)
```bash
ifc-fm-checker path/to/model.ifc
```

### JSON report
```bash
ifc-fm-checker model.ifc --format json
```

### Both formats + custom output directory
```bash
ifc-fm-checker model.ifc --format both --output-dir ./reports/
```

### Also validate file naming in a project folder
```bash
ifc-fm-checker model.ifc --folder ./project_files/ --verbose
```

### All options
```
usage: ifc-fm-checker [-h] [--folder FOLDER_PATH] [--output-dir OUTPUT_DIR]
                      [--format {html,json,both}] [--verbose] [--version]
                      ifc_file

positional arguments:
  ifc_file              Path to the IFC file to check

options:
  --folder, -f          Also validate ISO 19650 file naming in this folder
  --output-dir, -o      Output directory (default: same as IFC file)
  --format              html (default) | json | both
  --verbose, -v         Show detailed progress
  --version             Show version
```

---

## Score interpretation

| Score | Rating | Meaning |
|---|---|---|
| 85–100 | **FM READY** ✅ | Model can be imported into CAFM with minor or no fixes |
| 70–84 | **MOSTLY READY** ⚠️ | Some data gaps; FM team can work with the model but will need manual enrichment |
| 50–69 | **NEEDS WORK** 🔶 | Significant issues; CAFM import will require substantial manual work |
| 0–49 | **NOT READY** ❌ | Major structural or data problems; model is not suitable for FM use |

### Exit codes (useful for CI/CD pipelines)
- `0` — Score ≥ 70 (FM READY or MOSTLY READY)
- `1` — Score < 70 (NEEDS WORK or NOT READY)

---

## Check details

### 1. Spatial Structure (15%)
Verifies the IFC spatial hierarchy is complete and all elements are assigned to a floor.

**Checks:**
- IfcSite, IfcBuilding, IfcBuildingStorey present
- IfcSpace entities present with names
- All physical elements (walls, slabs, MEP, etc.) contained in IfcBuildingStorey
- Spaces have GrossFloorArea in Pset_SpaceCommon

### 2. Pset Completeness (25%)
Checks that required PropertySets are present and filled for each element type.

**Checked Psets:**
- `Pset_WallCommon`: Reference, IsExternal, LoadBearing, FireRating
- `Pset_SlabCommon`: Reference, IsExternal, LoadBearing, FireRating
- `Pset_SpaceCommon`: Reference, IsExternal, GrossFloorArea
- `Pset_DoorCommon`: Reference, IsExternal, FireRating
- `Pset_ManufacturerTypeInformation`: Manufacturer, ModelReference, ModelLabel (MEP)

### 3. Asset Data (30%)
Checks CAFM-critical fields on all maintainable equipment.

**Checked fields (with aliases):**
- `asset_code`: AssetTag, AssetCode, TagNumber, Mark
- `manufacturer`: Manufacturer, Produttore
- `model`: ModelReference, ModelLabel, ArticleNumber
- `install_date`: InstallationDate, ManufactureDate
- `warranty`: WarrantyDuration, WarrantyPeriod, Garanzia

Checks both instance Psets and IfcTypeObject Psets.

### 4. COBie Readiness (20%)
Validates minimum data for a valid COBie export.

**Sheets checked:**
- **Facility**: IfcProject Name and Description
- **Floor**: Storey names and elevations
- **Space**: Space names, descriptions, areas
- **Type**: IfcTypeObject Manufacturer and ModelReference
- **Component**: Unique Tag values on equipment instances

### 5. File Naming — ISO 19650 / DM 312-2021 (10%)
Validates filenames against the Italian BIM naming convention.

**Expected format:**
```
{Project}-{Originator}-{Volume/System}-{Level/Location}-{Type}-{Role}-{Classifier}_{Revision}.ext
```
Example: `PROJ01-ARCH01-B00-00-M3-AR-ARCMODEL_S01.ifc`

**Checks:**
- Minimum 6 hyphen-separated fields
- Revision suffix present (e.g. `_P01`, `_S01`, `_C01`)
- Document type is a recognized ISO 19650 type code (M3, DR, SP, CA, etc.)
- No spaces or invalid characters

---

## Python API

```python
from ifc_fm_checker.runner import run_all_checks

result = run_all_checks(
    ifc_path="model.ifc",
    output_dir="./reports",
    output_format="both",  # "html", "json", "both"
    verbose=True,
)

print(result["overall_score"])  # e.g. 74
print(result["rating"])         # e.g. "MOSTLY READY"

for check in result["results"]:
    print(f"{check['name']}: {check['score']}/100")
    for issue in check["issues"]:
        print(f"  [{issue['severity'].upper()}] {issue['message']}")
        print(f"  Fix: {issue['fix']}")
```

### Running individual checks

```python
import ifcopenshell
from ifc_fm_checker.checks import check_spatial, check_assets

ifc = ifcopenshell.open("model.ifc")

spatial = check_spatial.run(ifc)
print(spatial["score"], spatial["stats"])

assets = check_assets.run(ifc)
for issue in assets["issues"]:
    print(issue["message"])
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

19 tests covering: config validation, utils, all 5 checks, runner integration, HTML/JSON output.

---

## Standards reference

- **ISO 19650-1/2:2018** — Information management using BIM
- **ISO 19650-3:2020** — Information management in the operational phase
- **COBie 2.4** — Construction Operations Building information exchange
- **Italian DM 312/2021** — BIM obligations for Italian public works
- **buildingSMART IDS 1.0 (2024)** — Information Delivery Specification (future check planned)

---

## Roadmap

- [ ] IDS validation (buildingSMART IDS 1.0) — check against .ids XML requirement files
- [ ] Clash detection summary
- [ ] XLSX report format
- [ ] Revit-specific Pset mapping improvements
- [ ] Classification system check (Uniclass 2015, UNI 8290)
- [ ] Custom Pset config via YAML file

---

## Author

**Fabio Sbriglio** — BIM Coordinator | Information Manager | Digital Twin Specialist

Certified BIM Specialist MEP — CEPAS Bureau Veritas  
BIM Coordinator — ICMQ/Harpaceas  
Examiner OdV — CEPAS Bureau Veritas

[LinkedIn](https://linkedin.com/in/fabio-sbriglio) · [GitHub](https://github.com/fabio-sbriglio)

---

## License

MIT — see [LICENSE](LICENSE)
