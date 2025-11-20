import json, re
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Tuple, Optional


# ---------- Rules loading & preparation ----------

def _prep_rules(rules_path: str) -> tuple[Dict, List[str], str]:
    """
    Load rules once. Return (rules_with_precompiled_regex, unique_constraints, unique_mode).
    All column names are treated case-insensitively (lowercased).
    """
    with open(rules_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    rules_raw: Dict = cfg.get("columns", {})
    unique_constraints = [c.lower() for c in cfg.get("unique_constraints", [])]
    unique_mode = cfg.get("unique_mode", "ignore").lower()

    # Precompile regex for speed
    rules = {}
    for field, rule in rules_raw.items():
        r = dict(rule)
        if "regex" in r and r["regex"]:
            r["_regex_compiled"] = re.compile(r["regex"])
        rules[field.lower()] = r
    return rules, unique_constraints, unique_mode


# ---------- Duplicate map (global, one pass) ----------

def build_duplicate_index(
    records: List[Dict],
    unique_constraints: List[str]
) -> Dict[Tuple, Tuple[int, int]]:
    """
    Build a map: key_tuple -> (count, first_row_index)
    row indices are 1-based (for human-friendly messages if needed).
    """
    if not unique_constraints:
        return {}

    dup_map: Dict[Tuple, Tuple[int, int]] = {}
    first_seen: Dict[Tuple, int] = {}
    counts: Dict[Tuple, int] = {}

    for idx, row in enumerate(records, start=1):
        key = tuple(row.get(col) for col in unique_constraints)
        counts[key] = counts.get(key, 0) + 1
        if key not in first_seen:
            first_seen[key] = idx

    for k, cnt in counts.items():
        dup_map[k] = (cnt, first_seen[k])
    return dup_map


# ---------- Per row validation ----------

def _validate_row(
    row: Dict,
    row_index: int,
    rules: Dict,
    dup_index: Dict[Tuple, Tuple[int, int]],
    unique_constraints: List[str],
    unique_mode: str
) -> Dict:
    """
    Return a new dict with Valid and Remarks fields added.
    Keeps existing keys (assumed already lower-cased by readers).
    """
    errors: List[str] = []
    normalized = {k.lower(): v for k, v in row.items()}

    # Field-level rules
    for field, rule in rules.items():
        value = normalized.get(field)
        if rule.get("required") and (value is None or str(value).strip() == ""):
            errors.append(f"{field} is required")
            continue

        if value is None or value == "":
            continue

        typ = rule.get("type")
        try:
            if typ == "int":
                int(value)
            elif typ == "float":
                float(value)
            elif typ == "decimal":
                Decimal(str(value))
            elif typ == "date":
                if not isinstance(value, (datetime, date)):
                    # Expect ISO yyyy-mm-dd or Excel-converted string
                    datetime.fromisoformat(str(value))
            elif typ == "str":
                str(value)
        except Exception:
            errors.append(f"{field} invalid {typ}")
            # continue to next field
            continue

        rc = rule.get("_regex_compiled")
        if rc and not rc.match(str(value)):
            errors.append(f"{field} does not match pattern")

    # Duplicate policy
    if unique_constraints and unique_mode != "ignore":
        key = tuple(normalized.get(c) for c in unique_constraints)
        cnt, first_idx = dup_index.get(key, (1, row_index))
        if cnt > 1:
            if unique_mode == "fail_all":
                errors.append(f"Duplicate based on {', '.join(unique_constraints)}")
            elif unique_mode == "keep_first":
                if row_index != first_idx:
                    errors.append(f"Duplicate based on {', '.join(unique_constraints)}")

    normalized["Valid"] = "Success" if not errors else "Fail"
    normalized["Remarks"] = ", ".join(errors) if errors else "Validated Successfully"
    return normalized


# ---------- Chunk API (used by the pipeline) ----------

def validate_chunk(
    records_slice: List[Dict],
    start_index: int,
    rules: Dict,
    dup_index: Dict[Tuple, Tuple[int, int]],
    unique_constraints: List[str],
    unique_mode: str
) -> tuple[List[Dict], int, int]:
    """
    Validate a slice synchronously. Returns (validated_rows, success_count, failure_count).
    """
    validated: List[Dict] = []
    success = 0
    failure = 0
    idx = start_index
    for row in records_slice:
        vr = _validate_row(row, idx, rules, dup_index, unique_constraints, unique_mode)
        validated.append(vr)
        if vr["Valid"] == "Success":
            success += 1
        else:
            failure += 1
        idx += 1
    return validated, success, failure


# Public entry for pipeline to load rules once
def load_rules_for_pipeline(rules_path: str):
    return _prep_rules(rules_path)

def prep_rules_from_dict(cfg: dict):
    """
    Accepts a dict (the DB-stored rules JSON).
    Returns (rules_with_precompiled_regex, unique_constraints, unique_mode).
    """
    import re
    rules_raw = cfg.get("columns", {})
    unique_constraints = [c.lower() for c in cfg.get("unique_constraints", [])]
    unique_mode = cfg.get("unique_mode", "ignore").lower()

    rules = {}
    for field, rule in rules_raw.items():
        r = dict(rule)
        if "regex" in r and r["regex"]:
            r["_regex_compiled"] = re.compile(r["regex"])
        rules[field.lower()] = r
    return rules, unique_constraints, unique_mode
