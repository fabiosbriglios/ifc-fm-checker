"""
Check 5: ISO 19650 / DM 312-2021 File Naming
Validates that filenames follow the Italian BIM naming convention.
Can be run on the IFC file itself and/or a list of files in a folder.

Convention: {Project}-{Originator}-{Volume/System}-{Level/Location}
            -{Type}-{Role}-{Classifier}_{Revision}.{ext}

Reference: ISO 19650-2, Annex A + Italian DM 312/2021.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from ifc_fm_checker.config import ISO19650_FILE_NAMING


# Allowed document types (from ISO 19650-2 Annex A)
ALLOWED_TYPES = set(ISO19650_FILE_NAMING["allowed_types"])

# Revision patterns: P01, S01, C01, A01...
REVISION_PATTERN = re.compile(r"^[A-Z]\d{1,3}$")

# Valid field character set (alphanumeric only, no spaces or special chars)
FIELD_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


def run(ifc_file, file_path: Optional[str] = None, folder_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Parameters:
        ifc_file: the loaded IFC model (used to extract project/originator from header)
        file_path: path to the IFC file being checked
        folder_path: optional folder path to check all files in the directory
    """
    issues = []
    stats = {}
    files_checked = []

    # --- Extract expected project/originator from IFC header ---
    ifc_project_name = _get_project_name(ifc_file)
    stats["ifc_project_name"] = ifc_project_name

    # --- Check the IFC file itself ---
    if file_path:
        filename = Path(file_path).name
        file_result = _check_filename(filename)
        file_result["source"] = "IFC file"
        files_checked.append(file_result)
        if not file_result["valid"]:
            for err in file_result["errors"]:
                issues.append({
                    "severity": "warning",
                    "element": filename,
                    "message": err,
                    "fix": _get_naming_fix(err),
                })

    # --- Check all files in folder (if provided) ---
    if folder_path and os.path.isdir(folder_path):
        for fname in os.listdir(folder_path):
            if fname.startswith(".") or fname.startswith("~"):
                continue
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                file_result = _check_filename(fname)
                file_result["source"] = "folder"
                files_checked.append(file_result)
                if not file_result["valid"]:
                    for err in file_result["errors"]:
                        issues.append({
                            "severity": "info",
                            "element": fname,
                            "message": err,
                            "fix": _get_naming_fix(err),
                        })

    stats["files_checked"] = len(files_checked)
    stats["files_valid"] = sum(1 for f in files_checked if f["valid"])
    stats["files_invalid"] = sum(1 for f in files_checked if not f["valid"])

    if not files_checked:
        # No file path provided — check IFC internal file name from header
        header_filename = _get_header_filename(ifc_file)
        if header_filename:
            file_result = _check_filename(header_filename)
            files_checked.append(file_result)
            if not file_result["valid"]:
                for err in file_result["errors"]:
                    issues.append({
                        "severity": "info",
                        "element": f"Header filename: {header_filename}",
                        "message": err,
                        "fix": _get_naming_fix(err),
                    })
        else:
            issues.append({
                "severity": "info",
                "element": "File naming",
                "message": "No file path provided — cannot validate ISO 19650 naming convention",
                "fix": "Run with --file or --folder to validate file naming.",
            })
            return {
                "name": "File Naming (ISO 19650 / DM 312-2021)",
                "score": 100,
                "issues": issues,
                "stats": stats,
                "description": "Validates ISO 19650 / Italian DM 312-2021 file naming convention.",
            }

    score = int(stats.get("files_valid", 0) / max(stats.get("files_checked", 1), 1) * 100)

    return {
        "name": "File Naming (ISO 19650 / DM 312-2021)",
        "score": score,
        "issues": issues,
        "stats": stats,
        "files_checked": files_checked,
        "description": (
            "Validates that file names follow the ISO 19650-2 / Italian DM 312-2021 "
            "convention: {Project}-{Originator}-{Volume}-{Level}-{Type}-{Role}-{Classifier}_{Rev}.ext"
        ),
    }


def _check_filename(filename: str) -> Dict[str, Any]:
    """Validate a single filename against ISO 19650 convention."""
    errors = []
    warnings = []
    parsed = {}

    # Remove extension
    name = Path(filename).stem
    ext = Path(filename).suffix.lower()

    # Check extension
    allowed_exts = {".ifc", ".rvt", ".dwg", ".dxf", ".pdf", ".xlsx", ".docx", ".nwd", ".nwc", ".pln"}
    if ext not in allowed_exts:
        warnings.append(f"Unusual file extension: '{ext}'")

    # Check spaces / forbidden chars
    if " " in name:
        errors.append("Filename contains spaces — use hyphens as separators")

    # Split on last underscore to separate body from revision
    parts_rev = name.rsplit("_", 1)
    if len(parts_rev) == 2:
        body, revision = parts_rev
        parsed["revision"] = revision
        if not REVISION_PATTERN.match(revision):
            errors.append(
                f"Revision '{revision}' does not match pattern [A-Z]dd (e.g. P01, S01, C01)"
            )
    else:
        body = name
        errors.append("No revision suffix found (e.g. _P01 for preliminary, _S01 for shared)")
        parsed["revision"] = None

    # Split body by hyphens
    fields = body.split("-")
    parsed["fields"] = fields

    min_fields = ISO19650_FILE_NAMING["min_fields"]
    if len(fields) < min_fields:
        errors.append(
            f"Only {len(fields)} fields found — minimum {min_fields} required "
            f"(Project-Originator-Volume-Level-Type-Role)"
        )
    else:
        # Validate document type field (index 4 in standard)
        if len(fields) > 4:
            doc_type = fields[4].upper()
            if doc_type not in ALLOWED_TYPES:
                warnings.append(
                    f"Document type '{doc_type}' not in standard list. "
                    f"Common types: M3 (3D model), DR (drawing), SP (specification)"
                )
            else:
                parsed["doc_type"] = doc_type

        # Check each field for valid characters
        for i, field in enumerate(fields):
            if not FIELD_PATTERN.match(field) and field:
                errors.append(
                    f"Field {i+1} '{field}' contains invalid characters — "
                    "only alphanumeric characters allowed (no spaces, underscores, or special chars)"
                )

    return {
        "filename": filename,
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "parsed": parsed,
    }


def _get_project_name(ifc_file) -> str:
    try:
        projects = ifc_file.by_type("IfcProject")
        if projects:
            return projects[0].Name or "Unknown"
    except Exception:
        pass
    return "Unknown"


def _get_header_filename(ifc_file) -> Optional[str]:
    try:
        header = ifc_file.header
        file_name = header.file_name
        if file_name and file_name.name:
            return os.path.basename(file_name.name)
    except Exception:
        pass
    return None


def _get_naming_fix(error_msg: str) -> str:
    if "spaces" in error_msg:
        return "Replace spaces with hyphens. Example: ProjectA-OrigB-B00-00-M3-AR-0001_P01.ifc"
    if "revision" in error_msg.lower():
        return (
            "Add revision suffix: _P01 (preliminary), _S01 (shared/issued), "
            "_D01 (for information), _A01 (approved)"
        )
    if "fields" in error_msg:
        return (
            "Use format: {Project}-{Originator}-{Volume/System}-{Level/Location}"
            "-{Type}-{Role}-{Classifier}_{Revision}.ext\n"
            "Example: PROJ01-ARCH01-B00-00-M3-AR-MODELS_S01.ifc"
        )
    if "document type" in error_msg.lower():
        return "Use standard document types: M3 (3D model), DR (drawing), SP (spec), CA (calc)"
    if "invalid characters" in error_msg:
        return "Use only letters and numbers in each field. No underscores inside fields (only before revision)."
    return "Check ISO 19650-2 Annex A for the complete naming convention rules."
