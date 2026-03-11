"""
FM Readiness Configuration
Defines required Psets, properties, and thresholds for each IFC element type.
Based on ISO 19650, COBie, and Italian DM 312/2021 requirements.
"""

# ---------------------------------------------------------------------------
# REQUIRED PSETS & PROPERTIES PER ELEMENT TYPE
# Format: { IFC_TYPE: { PSET_NAME: [required_props] } }
# ---------------------------------------------------------------------------
REQUIRED_PSETS = {
    "IfcSpace": {
        "Pset_SpaceCommon": [
            "Reference",
            "IsExternal",
            "GrossFloorArea",
        ],
    },
    "IfcWall": {
        "Pset_WallCommon": [
            "Reference",
            "IsExternal",
            "LoadBearing",
            "FireRating",
        ],
    },
    "IfcSlab": {
        "Pset_SlabCommon": [
            "Reference",
            "IsExternal",
            "LoadBearing",
            "FireRating",
        ],
    },
    "IfcColumn": {
        "Pset_ColumnCommon": [
            "Reference",
            "LoadBearing",
            "FireRating",
        ],
    },
    "IfcBeam": {
        "Pset_BeamCommon": [
            "Reference",
            "LoadBearing",
            "FireRating",
        ],
    },
    "IfcDoor": {
        "Pset_DoorCommon": [
            "Reference",
            "IsExternal",
            "FireRating",
        ],
    },
    "IfcWindow": {
        "Pset_WindowCommon": [
            "Reference",
            "IsExternal",
            "FireRating",
        ],
    },
    "IfcFlowTerminal": {
        "Pset_ManufacturerTypeInformation": [
            "Manufacturer",
            "ModelReference",
            "ModelLabel",
        ],
    },
    "IfcFlowSegment": {
        "Pset_ManufacturerTypeInformation": [
            "Manufacturer",
        ],
    },
    "IfcDistributionControlElement": {
        "Pset_ManufacturerTypeInformation": [
            "Manufacturer",
            "ModelReference",
        ],
    },
    "IfcMechanicalFastener": {
        "Pset_ManufacturerTypeInformation": [
            "Manufacturer",
        ],
    },
    "IfcBuildingElementProxy": {
        "Pset_ManufacturerTypeInformation": [
            "Manufacturer",
        ],
    },
}

# ---------------------------------------------------------------------------
# ASSET DATA PROPERTIES (critical for CAFM import)
# These are custom/shared parameters expected on all MEP/equipment elements
# ---------------------------------------------------------------------------
ASSET_TYPES = [
    "IfcFlowTerminal",
    "IfcFlowSegment",
    "IfcFlowFitting",
    "IfcDistributionControlElement",
    "IfcElectricAppliance",
    "IfcSanitaryTerminal",
    "IfcAirTerminal",
    "IfcPump",
    "IfcBoiler",
    "IfcChiller",
    "IfcCooledBeam",
    "IfcUnitaryEquipment",
    "IfcMedicalDevice",
    "IfcCommunicationsAppliance",
    "IfcFireSuppressionTerminal",
]

# Properties expected in any Pset on maintainable assets
ASSET_CRITICAL_PROPS = {
    "asset_code": ["AssetTag", "AssetCode", "TagNumber", "Mark"],
    "manufacturer": ["Manufacturer", "Produttore"],
    "model": ["ModelReference", "ModelLabel", "ArticleNumber", "Modello"],
    "install_date": ["InstallationDate", "ManufactureDate", "DataInstallazione"],
    "warranty": ["WarrantyDuration", "Garanzia", "WarrantyPeriod"],
}

# ---------------------------------------------------------------------------
# COBIE MINIMUM FIELDS
# Reference: COBie 2.4 / UK BIM Framework
# ---------------------------------------------------------------------------
COBIE_FACILITY_PROPS = ["ProjectName", "SiteName"]

COBIE_SPACE_PROPS = [
    "GrossFloorArea",
    "NetFloorArea",
]

COBIE_COMPONENT_PROPS = [
    "Manufacturer",
    "ModelReference",
    "ModelLabel",
]

COBIE_TYPE_PROPS = [
    "Manufacturer",
    "ModelReference",
    "ReplacementCost",
]

# ---------------------------------------------------------------------------
# ISO 19650 / DM 312-2021 FILE NAMING CONVENTION (Italian)
# Format: PPPP-AAAA-ZZ-XX-M3-SS-LLLL_n.ext
# ---------------------------------------------------------------------------
ISO19650_FILE_NAMING = {
    "description": (
        "Italian DM 312/2021 + ISO 19650 naming: "
        "{Project}-{Originator}-{Volume/System}-{Level/Location}"
        "-{Type}-{Role}-{Classifier}_{Revision}.{ext}"
    ),
    "separators": ["-", "_"],
    "min_fields": 6,
    "allowed_types": [
        "M3",  # 3D model
        "M2",  # 2D drawing
        "DR",  # Drawing
        "CA",  # Calculation
        "CO",  # Correspondence
        "CP",  # Contract particulars
        "CR",  # Clash report
        "FI",  # File information
        "HS",  # Health & safety
        "IE",  # Information exchange
        "MI",  # Minutes
        "MS",  # Method statement
        "PP",  # Project plan
        "PR",  # Programme
        "RD",  # Reference document
        "RI",  # Request for information
        "RO",  # Record
        "RS",  # Response
        "SA",  # Schedule of accommodation
        "SH",  # Submittal
        "SK",  # Sketch
        "SP",  # Specification
        "SU",  # Survey
    ],
}

# ---------------------------------------------------------------------------
# SCORING WEIGHTS (must sum to 1.0)
# ---------------------------------------------------------------------------
SCORING_WEIGHTS = {
    "spatial_structure": 0.15,
    "pset_completeness": 0.25,
    "asset_data": 0.30,
    "cobie_readiness": 0.20,
    "file_naming": 0.10,
    # system_assignment: informational in v1.1 — weight will be raised in v1.2
    # once market adoption of IfcSystem in Italian IFC exports is verified.
    # Kept at 0.0 so it never affects the FM Readiness score.
    "system_assignment": 0.0,
    # clash_detection: informational only — does not affect FM Readiness score.
    "clash_detection": 0.0,
}

# Thresholds for traffic-light rating
RATING_THRESHOLDS = {
    "excellent": 85,
    "good": 70,
    "fair": 50,
    "poor": 0,
}

RATING_COLORS = {
    "excellent": "#2e7d32",
    "good": "#f9a825",
    "fair": "#e65100",
    "poor": "#b71c1c",
}

RATING_LABELS = {
    "excellent": "FM READY",
    "good": "MOSTLY READY",
    "fair": "NEEDS WORK",
    "poor": "NOT READY",
}
