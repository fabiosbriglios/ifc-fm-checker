"""
Test suite for ifc-fm-checker.
Tests run against a minimal synthetic IFC model built in-memory using ifcopenshell.
"""

import pytest
import ifcopenshell
import ifcopenshell.api
import os
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_minimal_ifc() -> ifcopenshell.file:
    """Create a minimal valid IFC2x3 file in memory for testing."""
    f = ifcopenshell.file(schema="IFC2X3")

    # Project
    project = f.create_entity("IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="TestProject",
        Description="Test project for ifc-fm-checker",
    )

    # Units
    unit = f.create_entity("IfcSIUnit",
        UnitType="LENGTHUNIT",
        Prefix="MILLI",
        Name="METRE",
    )
    unit_assignment = f.create_entity("IfcUnitAssignment", Units=[unit])
    project.UnitsInContext = unit_assignment

    # Geometric context
    ctx = f.create_entity("IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=f.create_entity("IfcAxis2Placement3D",
            Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
        ),
    )
    project.RepresentationContexts = [ctx]

    # Site > Building > Storey
    site = f.create_entity("IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Test Site",
        CompositionType="ELEMENT",
    )
    building = f.create_entity("IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Test Building",
        CompositionType="ELEMENT",
    )
    storey = f.create_entity("IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="Ground Floor",
        Elevation=0.0,
        CompositionType="ELEMENT",
    )

    # Spatial relationships
    f.create_entity("IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=project,
        RelatedObjects=[site],
    )
    f.create_entity("IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=site,
        RelatedObjects=[building],
    )
    f.create_entity("IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=building,
        RelatedObjects=[storey],
    )

    # IfcSpace
    space = f.create_entity("IfcSpace",
        GlobalId=ifcopenshell.guid.new(),
        Name="Room 001",
        Description="Office",
        CompositionType="ELEMENT",
    )
    f.create_entity("IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=[space],
    )

    # IfcWall with Pset_WallCommon
    wall = f.create_entity("IfcWall",
        GlobalId=ifcopenshell.guid.new(),
        Name="Wall-001",
        Tag="W01",
    )
    f.create_entity("IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=[wall],
    )

    pset_wall = f.create_entity("IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        Name="Pset_WallCommon",
        HasProperties=[
            f.create_entity("IfcPropertySingleValue",
                Name="Reference",
                NominalValue=f.create_entity("IfcText", wrappedValue="EXT-WALL-200"),
            ),
            f.create_entity("IfcPropertySingleValue",
                Name="IsExternal",
                NominalValue=f.create_entity("IfcBoolean", wrappedValue=True),
            ),
            f.create_entity("IfcPropertySingleValue",
                Name="LoadBearing",
                NominalValue=f.create_entity("IfcBoolean", wrappedValue=True),
            ),
            f.create_entity("IfcPropertySingleValue",
                Name="FireRating",
                NominalValue=f.create_entity("IfcText", wrappedValue="REI120"),
            ),
        ],
    )
    f.create_entity("IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatingPropertyDefinition=pset_wall,
        RelatedObjects=[wall],
    )

    return f


@pytest.fixture
def minimal_ifc(tmp_path):
    """Write minimal IFC to disk and return path."""
    f = make_minimal_ifc()
    ifc_path = tmp_path / "test_model_P01.ifc"
    f.write(str(ifc_path))
    return str(ifc_path)


@pytest.fixture
def minimal_ifc_file():
    """Return minimal IFC file object (in-memory)."""
    return make_minimal_ifc()


# ---------------------------------------------------------------------------
# Tests: config
# ---------------------------------------------------------------------------

def test_scoring_weights_sum_to_one():
    from ifc_fm_checker.config import SCORING_WEIGHTS
    total = sum(SCORING_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, f"Scoring weights sum to {total}, expected 1.0"


def test_required_psets_not_empty():
    from ifc_fm_checker.config import REQUIRED_PSETS
    assert len(REQUIRED_PSETS) > 0
    for ifc_type, psets in REQUIRED_PSETS.items():
        assert isinstance(psets, dict)
        for pset_name, props in psets.items():
            assert isinstance(props, list)
            assert len(props) > 0


def test_asset_critical_props():
    from ifc_fm_checker.config import ASSET_CRITICAL_PROPS
    required_fields = ["asset_code", "manufacturer", "model"]
    for field in required_fields:
        assert field in ASSET_CRITICAL_PROPS, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Tests: utils
# ---------------------------------------------------------------------------

def test_get_psets_returns_dict(minimal_ifc_file):
    from ifc_fm_checker.utils import get_psets
    walls = minimal_ifc_file.by_type("IfcWall")
    assert walls
    psets = get_psets(walls[0])
    assert isinstance(psets, dict)
    assert "Pset_WallCommon" in psets


def test_get_psets_all_types(minimal_ifc_file):
    from ifc_fm_checker.utils import get_psets
    walls = minimal_ifc_file.by_type("IfcWall")
    psets = get_psets(walls[0])
    wall_common = psets.get("Pset_WallCommon", {})
    assert wall_common.get("IsExternal") is True
    assert wall_common.get("LoadBearing") is True
    assert wall_common.get("FireRating") == "REI120"


def test_prop_is_filled():
    from ifc_fm_checker.utils import prop_is_filled
    assert prop_is_filled("value") is True
    assert prop_is_filled(0) is True
    assert prop_is_filled(False) is True
    assert prop_is_filled(None) is False
    assert prop_is_filled("") is False
    assert prop_is_filled("N/A") is False
    assert prop_is_filled([]) is False


def test_get_schema(minimal_ifc_file):
    from ifc_fm_checker.utils import get_schema
    schema = get_schema(minimal_ifc_file)
    assert "IFC" in schema.upper()


def test_get_entity_label_with_name(minimal_ifc_file):
    from ifc_fm_checker.utils import get_entity_label
    walls = minimal_ifc_file.by_type("IfcWall")
    wall = walls[0]  # Name="Wall-001"
    label = get_entity_label(wall)
    assert label.startswith("IfcWall #")
    assert "(Wall-001)" in label


def test_get_entity_label_no_name(minimal_ifc_file):
    from ifc_fm_checker.utils import get_entity_label
    wall_no_name = minimal_ifc_file.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new())
    label = get_entity_label(wall_no_name)
    assert label.startswith("IfcWall #")
    assert "(" not in label


# ---------------------------------------------------------------------------
# Tests: checks
# ---------------------------------------------------------------------------

def test_check_spatial_runs(minimal_ifc_file):
    from ifc_fm_checker.checks.check_spatial import run
    result = run(minimal_ifc_file)
    assert "score" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert "issues" in result
    assert result["stats"]["storeys"] >= 1
    assert result["stats"]["spaces"] >= 1


def test_check_psets_runs(minimal_ifc_file):
    from ifc_fm_checker.checks.check_psets import run
    result = run(minimal_ifc_file)
    assert "score" in result
    assert 0 <= result["score"] <= 100
    # Wall with full Pset should get a good score
    assert result["score"] >= 50  # minimal model has only one wall; space psets missing


def test_check_assets_runs(minimal_ifc_file):
    from ifc_fm_checker.checks.check_assets import run
    result = run(minimal_ifc_file)
    assert "score" in result
    assert 0 <= result["score"] <= 100
    # Minimal model has no asset types — should return 100 with info message
    assert result["score"] == 100 or "total_assets" in result["stats"]


def test_check_cobie_runs(minimal_ifc_file):
    from ifc_fm_checker.checks.check_cobie import run
    result = run(minimal_ifc_file)
    assert "score" in result
    assert 0 <= result["score"] <= 100
    assert result["stats"]["projects"] >= 1


def test_check_naming_valid_file(minimal_ifc_file, tmp_path):
    from ifc_fm_checker.checks.check_naming import run
    valid_path = str(tmp_path / "PROJ01-ARCH01-B00-00-M3-AR-MODEL_S01.ifc")
    result = run(minimal_ifc_file, file_path=valid_path)
    assert "score" in result
    assert result["score"] == 100


def test_check_naming_invalid_file(minimal_ifc_file, tmp_path):
    from ifc_fm_checker.checks.check_naming import run
    bad_path = str(tmp_path / "my model.ifc")
    result = run(minimal_ifc_file, file_path=bad_path)
    assert result["score"] < 100
    assert any("spaces" in i["message"] for i in result["issues"])


def test_check_naming_no_revision(minimal_ifc_file, tmp_path):
    from ifc_fm_checker.checks.check_naming import run
    bad_path = str(tmp_path / "PROJ01-ARCH01-B00-00-M3-AR-MODEL.ifc")
    result = run(minimal_ifc_file, file_path=bad_path)
    assert result["score"] < 100


# ---------------------------------------------------------------------------
# Tests: runner (integration)
# ---------------------------------------------------------------------------

def test_runner_produces_html(minimal_ifc, tmp_path):
    from ifc_fm_checker.runner import run_all_checks
    result = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="html",
        verbose=False,
    )
    assert "overall_score" in result
    assert 0 <= result["overall_score"] <= 100
    assert result["output_file"] is not None
    assert os.path.exists(result["output_file"])
    # Check HTML is non-trivial
    with open(result["output_file"], encoding="utf-8") as f:
        content = f.read()
    assert "FM Readiness Report" in content
    assert str(result["overall_score"]) in content


def test_runner_produces_json(minimal_ifc, tmp_path):
    from ifc_fm_checker.runner import run_all_checks
    import json
    result = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="json",
        verbose=False,
    )
    assert os.path.exists(result["output_file"])
    with open(result["output_file"], encoding="utf-8") as f:
        data = json.load(f)
    assert "overall_score" in data
    assert "checks" in data
    assert len(data["checks"]) == 8  # 5 FM checks + IDS + system_assignment + clash_detection


def test_runner_all_checks_present(minimal_ifc, tmp_path):
    from ifc_fm_checker.runner import run_all_checks
    result = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="html",
    )
    check_keys = {c["check_key"] for c in result["results"]}
    expected = {
        "spatial_structure", "pset_completeness", "asset_data",
        "cobie_readiness", "file_naming", "ids_validation", "system_assignment",
        "clash_detection",
    }
    assert expected == check_keys


def test_runner_missing_file():
    from ifc_fm_checker.runner import run_all_checks
    with pytest.raises(FileNotFoundError):
        run_all_checks(ifc_path="/nonexistent/file.ifc")


def test_runner_model_info(minimal_ifc, tmp_path):
    from ifc_fm_checker.runner import run_all_checks
    result = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="json",
    )
    info = result["model_info"]
    assert "schema" in info
    assert "total_elements" in info
    assert info["project_name"] == "TestProject"


# ---------------------------------------------------------------------------
# Tests: check_ids
# ---------------------------------------------------------------------------

IDS_WALL_FIRE_RATING = """\
<?xml version="1.0" encoding="UTF-8"?>
<ids xmlns="http://standards.buildingsmart.org/IDS"
     xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <info><title>Test IDS — Wall FireRating</title></info>
  <specifications>
    <specification name="Wall must have FireRating" minOccurs="1">
      <applicability>
        <entity>
          <name><simpleValue>IfcWall</simpleValue></name>
        </entity>
      </applicability>
      <requirements>
        <property dataType="IfcLabel">
          <propertySet><simpleValue>Pset_WallCommon</simpleValue></propertySet>
          <baseName><simpleValue>FireRating</simpleValue></baseName>
        </property>
      </requirements>
    </specification>
  </specifications>
</ids>
"""

IDS_WALL_FIRE_RATING_CONSTRAINED = """\
<?xml version="1.0" encoding="UTF-8"?>
<ids xmlns="http://standards.buildingsmart.org/IDS"
     xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <info><title>Test IDS — FireRating must be REI60</title></info>
  <specifications>
    <specification name="Wall FireRating must be REI60" minOccurs="1">
      <applicability>
        <entity>
          <name><simpleValue>IfcWall</simpleValue></name>
        </entity>
      </applicability>
      <requirements>
        <property dataType="IfcLabel">
          <propertySet><simpleValue>Pset_WallCommon</simpleValue></propertySet>
          <baseName><simpleValue>FireRating</simpleValue></baseName>
          <value><simpleValue>REI60</simpleValue></value>
        </property>
      </requirements>
    </specification>
  </specifications>
</ids>
"""

IDS_NO_SPECIFICATIONS = """\
<?xml version="1.0" encoding="UTF-8"?>
<ids xmlns="http://standards.buildingsmart.org/IDS">
  <info><title>Empty IDS</title></info>
  <specifications></specifications>
</ids>
"""


def _write_ids(tmp_path, content: str, name: str = "test.ids") -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_check_ids_no_path(minimal_ifc_file):
    from ifc_fm_checker.checks.check_ids import run
    result = run(minimal_ifc_file, ids_path=None)
    assert result["score"] == 100
    assert result["stats"].get("skipped") is True
    assert any("skipped" in i["message"].lower() for i in result["issues"])


def test_check_ids_missing_file(minimal_ifc_file):
    from ifc_fm_checker.checks.check_ids import run
    result = run(minimal_ifc_file, ids_path="/nonexistent/file.ids")
    assert result["score"] == 0
    assert any(i["severity"] == "error" for i in result["issues"])


def test_check_ids_invalid_xml(minimal_ifc_file, tmp_path):
    from ifc_fm_checker.checks.check_ids import run
    bad_ids = _write_ids(tmp_path, "this is not xml", "bad.ids")
    result = run(minimal_ifc_file, ids_path=bad_ids)
    assert result["score"] == 0
    assert any("not valid XML" in i["message"] for i in result["issues"])


def test_check_ids_empty_specifications(minimal_ifc_file, tmp_path):
    from ifc_fm_checker.checks.check_ids import run
    ids_path = _write_ids(tmp_path, IDS_NO_SPECIFICATIONS)
    result = run(minimal_ifc_file, ids_path=ids_path)
    assert result["score"] == 100
    assert result["stats"]["specifications"] == 0


def test_check_ids_wall_passes(minimal_ifc_file, tmp_path):
    """Minimal IFC has a wall with FireRating=REI120 — presence check should pass."""
    from ifc_fm_checker.checks.check_ids import run
    ids_path = _write_ids(tmp_path, IDS_WALL_FIRE_RATING)
    result = run(minimal_ifc_file, ids_path=ids_path)
    assert result["score"] == 100
    assert result["stats"]["specifications"] == 1
    assert result["stats"]["passed_checks"] == result["stats"]["total_checks"]


def test_check_ids_wall_fails_value_constraint(minimal_ifc_file, tmp_path):
    """Wall has FireRating=REI120, but IDS requires REI60 — should fail."""
    from ifc_fm_checker.checks.check_ids import run
    ids_path = _write_ids(tmp_path, IDS_WALL_FIRE_RATING_CONSTRAINED)
    result = run(minimal_ifc_file, ids_path=ids_path)
    assert result["score"] < 100
    assert any("FireRating" in i["message"] for i in result["issues"])


def test_check_ids_does_not_affect_fm_score(minimal_ifc, tmp_path):
    """IDS check must not change the overall FM Readiness score."""
    from ifc_fm_checker.runner import run_all_checks
    ids_path = _write_ids(tmp_path, IDS_WALL_FIRE_RATING)

    result_without = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="json",
    )
    result_with = run_all_checks(
        ifc_path=minimal_ifc,
        ids_path=ids_path,
        output_dir=str(tmp_path),
        output_format="json",
    )
    assert result_without["overall_score"] == result_with["overall_score"]


# ---------------------------------------------------------------------------
# Tests: check_systems
# ---------------------------------------------------------------------------

def test_check_systems_runs(minimal_ifc_file):
    from ifc_fm_checker.checks.check_systems import run
    result = run(minimal_ifc_file)
    assert "score" in result
    assert "issues" in result
    assert "stats" in result
    assert result["check_key"] if "check_key" in result else True  # key set by runner


def test_check_systems_score_range(minimal_ifc_file):
    from ifc_fm_checker.checks.check_systems import run
    result = run(minimal_ifc_file)
    assert 0 <= result["score"] <= 100


def test_check_systems_no_mep_elements(minimal_ifc_file):
    """Minimal IFC has no MEP elements — should return score=100 with info message."""
    from ifc_fm_checker.checks.check_systems import run
    result = run(minimal_ifc_file)
    assert result["score"] == 100
    assert result["stats"]["total_mep_elements"] == 0
    assert any("skipped" in i["message"].lower() for i in result["issues"])


def test_check_systems_does_not_affect_fm_score(minimal_ifc, tmp_path):
    """system_assignment weight=0.0 must never affect the FM Readiness score."""
    from ifc_fm_checker.runner import run_all_checks
    from ifc_fm_checker.config import SCORING_WEIGHTS

    assert SCORING_WEIGHTS.get("system_assignment", 0.0) == 0.0

    result = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="json",
    )
    # Recompute weighted score — must match runner output regardless of system_assignment score
    manual_score = int(sum(
        r["score"] * SCORING_WEIGHTS.get(r["check_key"], 0.0)
        for r in result["results"]
    ))
    assert manual_score == result["overall_score"]


# ---------------------------------------------------------------------------
# Tests: check_clashes
# ---------------------------------------------------------------------------

def test_check_clashes_runs(minimal_ifc_file):
    from ifc_fm_checker.checks.check_clashes import run
    result = run(minimal_ifc_file)
    assert "score" in result
    assert "issues" in result
    assert "stats" in result
    assert result["stats"]["tolerance_cm"] == 0.0


def test_check_clashes_score_range(minimal_ifc_file):
    from ifc_fm_checker.checks.check_clashes import run
    result = run(minimal_ifc_file)
    assert 0 <= result["score"] <= 100


def test_check_clashes_zero_tolerance(minimal_ifc_file):
    from ifc_fm_checker.checks.check_clashes import run
    result = run(minimal_ifc_file, tolerance_cm=0.0)
    assert result["stats"]["tolerance_cm"] == 0.0
    assert 0 <= result["score"] <= 100


def test_check_clashes_custom_tolerance(minimal_ifc_file):
    from ifc_fm_checker.checks.check_clashes import run
    result = run(minimal_ifc_file, tolerance_cm=5.0)
    assert result["stats"]["tolerance_cm"] == 5.0
    assert 0 <= result["score"] <= 100


def test_check_clashes_does_not_affect_fm_score(minimal_ifc, tmp_path):
    """clash_detection weight=0.0 must never change the FM Readiness score."""
    from ifc_fm_checker.runner import run_all_checks
    from ifc_fm_checker.config import SCORING_WEIGHTS

    assert SCORING_WEIGHTS.get("clash_detection", 0.0) == 0.0

    result = run_all_checks(
        ifc_path=minimal_ifc,
        output_dir=str(tmp_path),
        output_format="json",
    )
    manual_score = int(sum(
        r["score"] * SCORING_WEIGHTS.get(r["check_key"], 0.0)
        for r in result["results"]
    ))
    assert manual_score == result["overall_score"]
