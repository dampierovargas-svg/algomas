#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_knowledge_base.py - Portable forensic validator for cad_knowledge_base.
Works on Windows, Linux, macOS without PYTHONUTF8=1.
Uses encoding='utf-8-sig' for all reads to handle BOM and non-BOM UTF-8.

Performs FOUR separate validations:
1. structural_validation - schema, syntax, IDs, references
2. semantic_validation - real content (no generic formulas/geometries/symbols)
3. normative_validation - source verification (PARTIAL allowed for paid sources)
4. render_validation - symbols have valid primitives, drawings have all deps

Exit code 0 only if structural, semantic, and render validations all PASS.
"""
import csv, json, os, re, sys, hashlib
from collections import defaultdict

# Portable path detection
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(SCRIPT_DIR) == "tools":
    BASE = os.path.dirname(SCRIPT_DIR)
else:
    BASE = SCRIPT_DIR

TECHS = ["01_pv_ground","02_pv_roof_carport","03_pv_floating","04_wind_onshore","05_wind_offshore",
         "06_hydro","07_biomass","08_biogas","09_geothermal","10_solar_thermal_csp",
         "11_marine","12_bess","13_hydrogen","14_hybrid_microgrid"]

# Canonical schemas
CANONICAL_SCHEMAS = {
    "A_input_fields.csv": ["field_id","category","name_es","description","data_type","unit","allowed_values","min_value","max_value","precision","requirement_class","required_from_stage","conditional_expression","prohibited_default","expected_source_document","extraction_hints","used_by_calculation_ids","used_by_drawing_ids","blocking_if_missing","review_role","source_ids"],
    "E_drawing_catalog.csv": ["drawing_id","technology","discipline","title_es","purpose","applicability_expression","minimum_project_stage","required_field_ids","required_calculation_ids","required_geometry_rule_ids","required_views","required_tables","required_symbol_ids","preferred_sheet_formats","preferred_scales","required_layers","mandatory_annotations","cross_references","qa_rule_ids","release_blockers","source_ids"],
    "G_extraction_dictionary.csv": ["field_id","language","synonyms","abbreviations","expected_units","document_types","section_names","table_header_patterns","regex_candidates","positive_context","negative_context","normalization_rule","plausibility_rule","requires_ocr","requires_vision","requires_llm","human_review_condition"],
    "03_common_layers.csv": ["layer_id","discipline","technology_scope","name_template","description","aci_color","rgb_color","lineweight_mm","linetype","plot_behavior","visible_scales","entity_types","source_ids"],
    "00_source_register.csv": ["source_id","authority","document_code","title","edition_year","revision","official_url","access_date","primary_or_secondary","accessible_full_text","covered_topics","jurisdictions","notes"],
    "01_common_project_inputs.csv": ["field_id","category","name_es","description","data_type","unit","allowed_values","min_value","max_value","precision","requirement_class","required_from_stage","conditional_expression","prohibited_default","expected_source_document","extraction_hints","used_by_calculation_ids","used_by_drawing_ids","blocking_if_missing","review_role","source_ids"],
    "06_common_drawing_catalog.csv": ["drawing_id","technology","discipline","title_es","purpose","applicability_expression","minimum_project_stage","required_field_ids","required_calculation_ids","required_geometry_rule_ids","required_views","required_tables","required_symbol_ids","preferred_sheet_formats","preferred_scales","required_layers","mandatory_annotations","cross_references","qa_rule_ids","release_blockers","source_ids"],
}

CANONICAL_JSON_KEYS = {
    "C_formulas.json": ["calculation_id","name_es","purpose","applicability_expression","input_field_ids","derived_input_ids","equations_ascii","equations_latex","variables","unit_equations","numerical_method","iteration_limits","validity_limits","outputs","acceptance_rules","failure_modes","drawing_impacts","source_ids"],
    "D_geometry_rules.json": ["geometry_rule_id","name_es","applicability_expression","required_field_ids","required_calculation_ids","coordinate_space","algorithm","algorithm_pseudocode","generated_entity_types","clearances","collision_rules","routing_costs","tolerances","failure_conditions","source_ids"],
    "F_qa_rules.json": ["rule_id","name_es","category","applicability_expression","assertion_expression","severity","message_template","required_evidence","affected_fields","affected_drawings","override_allowed","override_role","source_ids"],
    "H_missing_data_policy.json": ["field_id","missing_action","allowed_until_stage","safe_to_derive","derivation_rule_id","required_document","responsible_role","blocked_calculations","blocked_drawings"],
    "B_equipment_schema.json": ["equipment_type_id","name_es","subsystem","properties","ports","geometric_envelope","operating_limits","datasheet_requirements","required_certificates","drawing_representations","validation_rules","source_ids"],
    "05_common_calculations.json": ["calculation_id","name_es","purpose","applicability_expression","input_field_ids","derived_input_ids","equations_ascii","equations_latex","variables","unit_equations","numerical_method","iteration_limits","validity_limits","outputs","acceptance_rules","failure_modes","drawing_impacts","source_ids"],
    "07_common_geometry_rules.json": ["geometry_rule_id","name_es","applicability_expression","required_field_ids","required_calculation_ids","coordinate_space","algorithm","algorithm_pseudocode","generated_entity_types","clearances","collision_rules","routing_costs","tolerances","failure_conditions","source_ids"],
    "08_common_qa_rules.json": ["rule_id","name_es","category","applicability_expression","assertion_expression","severity","message_template","required_evidence","affected_fields","affected_drawings","override_allowed","override_role","source_ids"],
    "02_common_cad_standard.json": ["rule_id","applies_to","parameters","conditional_expression","validation_expression","severity","source_ids"],
    "04_common_symbols.json": ["symbol_id","technology","discipline","name_es","standard_reference","view_types","bounding_box","anchor","ports","parameters","vector_primitives","layers","labels","lod_rules","source_ids"],
    "jurisdiction_peru.json": ["jurisdiction_rule_id","authority","document_code","edition_year","topic","applies_to","project_stage","requirement_expression","parameters","evidence_required","affected_calculations","affected_drawings","source_ids"],
    "jurisdiction_international.json": ["jurisdiction_rule_id","authority","document_code","edition_year","topic","applies_to","project_stage","requirement_expression","parameters","evidence_required","affected_calculations","affected_drawings","source_ids"],
}

PLACEHOLDER_PATTERNS = [r"\.\.\.", r"\bTBD\b", r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"\bplaceholder\b", r"lorem ipsum"]
VALID_PRIMITIVES = {"line","polyline","polygon","circle","arc","ellipse","rectangle","text","hatch","path"}
VALID_SEVERITIES = {"INFO","WARNING","HUMAN_REVIEW","BLOCKED"}

# Generic patterns to REJECT in semantic validation
GENERIC_FORMULA_PATTERNS = [
    re.compile(r"^\s*y\s*=\s*f\s*\(\s*x\s*\)\s*$", re.IGNORECASE),
    re.compile(r"^\s*result\s*=\s*calculate?\s*\(", re.IGNORECASE),
    re.compile(r"^\s*result\s*=\s*f\s*\(", re.IGNORECASE),
    re.compile(r"^\s*output\s*=\s*f\s*\(", re.IGNORECASE),
    re.compile(r"^\s*output\s*=\s*function\s*\(", re.IGNORECASE),
]
GENERIC_GEOMETRY_ALGORITHMS = {"deterministic_layout_placement","layout_grid","layout_box",
                               "layout_stack","layout_pipe","layout_drain","layout_fence",
                               "layout_pipe_loop","layout_zone","layout_vent","layout_conveyor",
                               "layout_pedestal","layout_duct","layout_storage","layout_flare"}
GENERIC_ACCEPTANCE = {"output within plausible range","inputs within valid ranges","match design","value in valid range"}
GENERIC_FAILURE = {"invalid inputs","invalid input"}
GENERIC_OUTPUT_NAME = "result"
GENERIC_OUTPUT_UNIT = "dimensionless"

ROLE_NAMES = {"PROJECT_MANAGER","PROCESS_ENGINEER","SAFETY_ENGINEER","ELECTRICAL_ENGINEER",
              "MECHANICAL_ENGINEER","CIVIL_ENGINEER","STRUCTURAL_ENGINEER","CONTROL_ENGINEER",
              "GEOTECH_ENGINEER","HYDROLOGIST","METEOROLOGIST","ENVIRONMENTAL_LEAD",
              "LOGISTICS_LEAD","CAD_MANAGER","GEODESIST","LEAD_ENGINEER_CIVIL",
              "LEAD_ENGINEER_ELECTRICAL","LEAD_ENGINEER_DISCIPLINE","PROJECT_SPONSOR",
              "OPERATOR","CIP","INDECI","SERNANP","SERFOR","ANA","INGEMMET","CORPAC",
              "MTPE","SUNASS","DGE","DREM","GORE","BOMBEROS","SUNAT","MIMP","DNEP","SUNASA"}

# Reports
report = {
    "files": [],
    "record_counts": {},
    "schema_validation": {},
    "broken_references": [],
    "duplicate_ids": [],
    "placeholder_count": 0,
    "unknown_source_ids": [],
    "missing_symbol_ids": [],
    "missing_layer_ids": [],
    "missing_data_policy_gaps": [],
    "drawing_dependency_resolution": {},
    "structural_validation": {"status": "FAIL", "completion_percent": 0},
    "semantic_validation": {"status": "FAIL", "completion_percent": 0, "errors": []},
    "normative_validation": {"status": "FAIL", "verified_primary_sources": 0, "unverified_required_sources": [], "completion_percent": 0},
    "render_validation": {"status": "FAIL", "completion_percent": 0, "errors": []},
    "release_recommendation": "NOT_READY"
}

errors = []
semantic_errors = []
render_errors = []
files_discovered = 0
files_read = 0
bytes_read = 0
file_hashes = {}

# ============ File walk and hashing ============
for root, dirs, files in os.walk(BASE):
    for fname in files:
        fpath = os.path.join(root, fname)
        if not os.path.isfile(fpath): continue
        files_discovered += 1
        try:
            with open(fpath, "rb") as f:
                content_bytes = f.read()
            bytes_read += len(content_bytes)
            files_read += 1
            sha = hashlib.sha256(content_bytes).hexdigest()
            rel = os.path.relpath(fpath, BASE)
            file_hashes[rel] = sha
        except Exception as e:
            errors.append(f"read_error: {fpath}: {e}")

# ============ Load source register ============
src_ids = set()
unverified_sources = []
src_path = f"{BASE}/00_source_register.csv"
if os.path.exists(src_path):
    try:
        with open(src_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                src_ids.add(row["source_id"])
                if row.get("accessible_full_text") == "false" and row.get("primary_or_secondary") == "primary":
                    unverified_sources.append(row["source_id"])
    except Exception as e:
        errors.append(f"source_register: {e}")

report["record_counts"]["00_source_register"] = len(src_ids)
report["normative_validation"]["unverified_required_sources"] = unverified_sources
report["normative_validation"]["verified_primary_sources"] = len(src_ids) - len(unverified_sources)

# ============ Build global ID registries ============
def load_csv_dict(path):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_json_list(path):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

common_layers = {}
for row in load_csv_dict(f"{BASE}/03_common_layers.csv"):
    common_layers[row["layer_id"]] = row
    common_layers[row["name_template"]] = row

common_symbols = {}
for s in load_json_list(f"{BASE}/04_common_symbols.json"):
    common_symbols[s["symbol_id"]] = s

common_fields = set(r["field_id"] for r in load_csv_dict(f"{BASE}/01_common_project_inputs.csv"))
common_calcs = set(c["calculation_id"] for c in load_json_list(f"{BASE}/05_common_calculations.json"))
common_geoms = set(g["geometry_rule_id"] for g in load_json_list(f"{BASE}/07_common_geometry_rules.json"))
common_qa = set(q["rule_id"] for q in load_json_list(f"{BASE}/08_common_qa_rules.json"))
common_drawings = set(r["drawing_id"] for r in load_csv_dict(f"{BASE}/06_common_drawing_catalog.csv"))

all_field_ids = set(common_fields)
all_calc_ids = set(common_calcs)
all_geom_ids = set(common_geoms)
all_qa_ids = set(common_qa)
all_symbol_ids = set(common_symbols.keys())
all_layer_ids = set(common_layers.keys())
all_drawing_ids = set(common_drawings)
all_equipment_ids = set()

# Tech-specific
tech_data = {}
for tech in TECHS:
    tech_data[tech] = {"fields":set(),"calcs":set(),"geoms":set(),"drawings":set(),"qa":set(),"equipment":set(),"drawing_deps":{},"formulas":[],"geoms_data":[],"qa_data":[]}
    
    for row in load_csv_dict(f"{BASE}/technologies/{tech}/A_input_fields.csv"):
        tech_data[tech]["fields"].add(row["field_id"])
        all_field_ids.add(row["field_id"])
    
    for item in load_json_list(f"{BASE}/technologies/{tech}/B_equipment_schema.json"):
        if "equipment_type_id" in item:
            eid = item["equipment_type_id"]
            tech_data[tech]["equipment"].add(eid)
            if eid in all_equipment_ids:
                report["duplicate_ids"].append({"type":"equipment","id":eid})
            all_equipment_ids.add(eid)
    
    c_data = load_json_list(f"{BASE}/technologies/{tech}/C_formulas.json")
    tech_data[tech]["formulas"] = c_data
    for item in c_data:
        if "calculation_id" in item:
            cid = item["calculation_id"]
            tech_data[tech]["calcs"].add(cid)
            all_calc_ids.add(cid)
    
    d_data = load_json_list(f"{BASE}/technologies/{tech}/D_geometry_rules.json")
    tech_data[tech]["geoms_data"] = d_data
    for item in d_data:
        if "geometry_rule_id" in item:
            gid = item["geometry_rule_id"]
            tech_data[tech]["geoms"].add(gid)
            all_geom_ids.add(gid)
    
    for row in load_csv_dict(f"{BASE}/technologies/{tech}/E_drawing_catalog.csv"):
        did = row["drawing_id"]
        tech_data[tech]["drawings"].add(did)
        all_drawing_ids.add(did)
        tech_data[tech]["drawing_deps"][did] = row
    
    f_data = load_json_list(f"{BASE}/technologies/{tech}/F_qa_rules.json")
    tech_data[tech]["qa_data"] = f_data
    for item in f_data:
        if "rule_id" in item:
            qid = item["rule_id"]
            tech_data[tech]["qa"].add(qid)
            all_qa_ids.add(qid)

# ============ STRUCTURAL VALIDATION ============
def split_refs(val):
    if not val or not isinstance(val, str): return []
    val = val.replace("|", ";").replace(",", ";")
    parts = re.split(r"[;\s]+", val)
    return [p.strip() for p in parts if p.strip() and p.strip() != "-" and p.strip() != "[]"]

# Check all E drawings (common + tech) for dependency resolution
all_drawings_checked = 0
all_drawings_resolved = 0

# Common drawings
for row in load_csv_dict(f"{BASE}/06_common_drawing_catalog.csv"):
    did = row["drawing_id"]
    all_drawings_checked += 1
    deps_ok = True
    for col, id_set in [("required_field_ids",all_field_ids),("required_calculation_ids",all_calc_ids),
                        ("required_geometry_rule_ids",all_geom_ids),("required_symbol_ids",all_symbol_ids),
                        ("required_layers",all_layer_ids),("qa_rule_ids",all_qa_ids),
                        ("cross_references",all_drawing_ids),("source_ids",src_ids)]:
        for r in split_refs(row.get(col,"")):
            if r in ROLE_NAMES:
                report["broken_references"].append({"type":"role_in_source","ref":r,"consumer":f"common_E:{did}"})
                deps_ok = False
            elif r not in id_set:
                report["broken_references"].append({"type":col,"ref":r,"consumer":f"common_E:{did}"})
                deps_ok = False
    report["drawing_dependency_resolution"][f"common/{did}"] = {"resolved":deps_ok}
    if deps_ok: all_drawings_resolved += 1

# Tech drawings
for tech in TECHS:
    for did, row in tech_data[tech]["drawing_deps"].items():
        all_drawings_checked += 1
        deps_ok = True
        for col, id_set in [("required_field_ids",all_field_ids),("required_calculation_ids",all_calc_ids),
                            ("required_geometry_rule_ids",all_geom_ids),("required_symbol_ids",all_symbol_ids),
                            ("required_layers",all_layer_ids),("qa_rule_ids",all_qa_ids),
                            ("cross_references",all_drawing_ids),("source_ids",src_ids)]:
            for r in split_refs(row.get(col,"")):
                if r in ROLE_NAMES:
                    report["broken_references"].append({"type":"role_in_source","ref":r,"consumer":f"{tech}/E:{did}"})
                    deps_ok = False
                elif r not in id_set:
                    report["broken_references"].append({"type":col,"ref":r,"consumer":f"{tech}/E:{did}"})
                    deps_ok = False
        report["drawing_dependency_resolution"][f"{tech}/{did}"] = {"resolved":deps_ok}
        if deps_ok: all_drawings_resolved += 1

# Check CSV schemas
for root, dirs, files in os.walk(BASE):
    for fname in files:
        if fname.endswith(".csv"):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    n = sum(1 for _ in reader)
                rel = os.path.relpath(fpath, BASE)
                canonical = CANONICAL_SCHEMAS.get(fname)
                if canonical and header != canonical:
                    errors.append(f"csv_schema_mismatch: {rel}: cols={len(header)}, expected={len(canonical)}")
                report["record_counts"][rel] = n
                report["schema_validation"][rel] = "PASS" if (not canonical or header == canonical) else "FAIL"
            except Exception as e:
                rel = os.path.relpath(fpath, BASE)
                errors.append(f"csv_read_error: {rel}: {e}")

# Check JSON schemas
for root, dirs, files in os.walk(BASE):
    for fname in files:
        if fname.endswith(".json") and fname not in {"audit_before_forensic_v2.json","audit_after_forensic_v2.json","correction_manifest_v2.json","validation_report.json","test_results.json"} and fname not in {"audit_before_correction.json","audit_after_correction.json","correction_manifest.json"}:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, BASE)
            # Skip tests directory and tools
            if rel.startswith("tests/") or rel.startswith("tools/"): continue
            try:
                with open(fpath, encoding="utf-8-sig") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    errors.append(f"json_not_list: {rel}")
                    report["schema_validation"][rel] = "FAIL"
                    continue
                canonical_keys = CANONICAL_JSON_KEYS.get(fname)
                if canonical_keys:
                    for item in data:
                        if isinstance(item, dict):
                            for k in canonical_keys:
                                if k not in item:
                                    errors.append(f"json_missing_key: {rel}: missing {k}")
                                    break
                report["record_counts"][rel] = len(data)
                report["schema_validation"][rel] = "PASS"
            except Exception as e:
                errors.append(f"json_read_error: {rel}: {e}")
                report["schema_validation"][rel] = "FAIL"

# Check missing data policy coverage
for tech in TECHS:
    a_path = f"{BASE}/technologies/{tech}/A_input_fields.csv"
    h_path = f"{BASE}/technologies/{tech}/H_missing_data_policy.json"
    if not os.path.exists(a_path) or not os.path.exists(h_path): continue
    mandatory = set()
    for row in load_csv_dict(a_path):
        if row["requirement_class"] in ["PROJECT_MANDATORY","TECHNOLOGY_MANDATORY","CONDITIONAL","PROHIBITED_TO_ASSUME"]:
            mandatory.add(row["field_id"])
    covered = set(p["field_id"] for p in load_json_list(h_path) if isinstance(p, dict) and "field_id" in p)
    for fid in mandatory - covered:
        report["missing_data_policy_gaps"].append({"tech":tech,"field_id":fid})
        errors.append(f"policy_gap: {tech}: {fid}")

# Check placeholders
for root, dirs, files in os.walk(BASE):
    for fname in files:
        if fname.endswith(('.csv','.json')) and not fname.startswith("audit") and fname not in {"validation_report.json","test_results.json","correction_manifest.json","correction_manifest_v2.json"}:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8-sig") as f:
                    content = f.read()
                for p in PLACEHOLDER_PATTERNS:
                    matches = re.findall(p, content, re.IGNORECASE)
                    report["placeholder_count"] += len(matches)
                    if matches:
                        rel = os.path.relpath(fpath, BASE)
                        errors.append(f"placeholder: {p!r} in {rel}: {len(matches)}")
            except: pass

# ============ SEMANTIC VALIDATION ============
# Reject generic formulas, geometries, symbols

def check_formula_semantic(cid, item, location):
    eqs = item.get("equations_ascii", [])
    if not eqs:
        semantic_errors.append(f"{location}:{cid}: no equations")
    for eq in eqs:
        for pat in GENERIC_FORMULA_PATTERNS:
            if pat.match(eq):
                semantic_errors.append(f"{location}:{cid}: generic formula '{eq}'")
                break
    
    # Check input_field_ids exist
    for fid in item.get("input_field_ids", []):
        if isinstance(fid, str):
            if fid.endswith("-INPUT") or fid.endswith("_INPUT") or fid.startswith("GENERIC_") or fid == "UNKNOWN_FIELD" or "INPUT" in fid.upper():
                semantic_errors.append(f"{location}:{cid}: fake input ID '{fid}'")
            elif fid not in all_field_ids:
                semantic_errors.append(f"{location}:{cid}: nonexistent input field '{fid}'")
    
    # Variables must have unit (not generic dimensionless)
    for v in item.get("variables", []):
        if isinstance(v, dict):
            unit = v.get("unit","")
            if not unit or unit == GENERIC_OUTPUT_UNIT:
                semantic_errors.append(f"{location}:{cid}: variable '{v.get('name','?')}' without unit or with dimensionless")
    
    # Outputs - reject generic
    for o in item.get("outputs", []):
        if isinstance(o, dict):
            if o.get("name") == GENERIC_OUTPUT_NAME:
                semantic_errors.append(f"{location}:{cid}: generic output name 'result'")
            if o.get("unit") == GENERIC_OUTPUT_UNIT:
                semantic_errors.append(f"{location}:{cid}: generic output unit 'dimensionless'")
    
    # Acceptance rules
    for ar in item.get("acceptance_rules", []):
        if isinstance(ar, str) and ar in GENERIC_ACCEPTANCE:
            semantic_errors.append(f"{location}:{cid}: generic acceptance '{ar}'")
    
    # Failure modes
    for fm in item.get("failure_modes", []):
        if isinstance(fm, str) and fm in GENERIC_FAILURE:
            semantic_errors.append(f"{location}:{cid}: generic failure '{fm}'")

# Common calcs
for c in load_json_list(f"{BASE}/05_common_calculations.json"):
    check_formula_semantic(c.get("calculation_id","?"), c, "05_common_calculations.json")

# Tech formulas
for tech in TECHS:
    for item in tech_data[tech]["formulas"]:
        check_formula_semantic(item.get("calculation_id","?"), item, f"{tech}/C_formulas.json")

# Geometry rules
def check_geometry_semantic(gid, item, location):
    algo = item.get("algorithm","")
    if not algo or algo in GENERIC_GEOMETRY_ALGORITHMS:
        semantic_errors.append(f"{location}:{gid}: generic/empty algorithm '{algo}'")
    
    if not item.get("generated_entity_types"):
        semantic_errors.append(f"{location}:{gid}: no generated entities")
    
    if not item.get("required_field_ids"):
        semantic_errors.append(f"{location}:{gid}: no required fields")
    
    if not item.get("coordinate_space"):
        semantic_errors.append(f"{location}:{gid}: no coordinate_space")
    
    if not item.get("algorithm_pseudocode"):
        semantic_errors.append(f"{location}:{gid}: no pseudocode")
    
    if not item.get("tolerances"):
        semantic_errors.append(f"{location}:{gid}: no tolerances")
    
    if not item.get("failure_conditions"):
        semantic_errors.append(f"{location}:{gid}: no failure_conditions")
    
    for sid in item.get("source_ids", []):
        if isinstance(sid, str) and sid in ROLE_NAMES:
            semantic_errors.append(f"{location}:{gid}: role name '{sid}' in source_ids")

# Common geoms
for g in load_json_list(f"{BASE}/07_common_geometry_rules.json"):
    check_geometry_semantic(g.get("geometry_rule_id","?"), g, "07_common_geometry_rules.json")

# Tech geoms
for tech in TECHS:
    for item in tech_data[tech]["geoms_data"]:
        check_geometry_semantic(item.get("geometry_rule_id","?"), item, f"{tech}/D_geometry_rules.json")

# ============ RENDER VALIDATION ============
# Check symbols have valid primitives and graphics
for sid, sym in common_symbols.items():
    # Compound IDs
    if sid and ("|" in sid or ";" in sid or "," in sid):
        render_errors.append(f"04_common_symbols.json:{sid}: compound ID")
    
    # ALL_SYMBOLS wildcard
    if sid in ("ALL_SYMBOLS","*","ALL","?"):
        render_errors.append(f"04_common_symbols.json:{sid}: wildcard symbol ID")
    
    # No primitives
    primitives = sym.get("vector_primitives", [])
    if not primitives:
        render_errors.append(f"04_common_symbols.json:{sid}: no primitives")
    else:
        # Check valid primitive types
        for p in primitives:
            if isinstance(p, dict) and "type" in p:
                if p["type"] not in VALID_PRIMITIVES:
                    render_errors.append(f"04_common_symbols.json:{sid}: invalid primitive '{p['type']}'")
    
    # Rectangle + ID text (generic fill)
    if len(primitives) <= 2:
        types = [p.get("type","") for p in primitives if isinstance(p, dict)]
        if "rectangle" in types and ("text" in types or len(types) == 1):
            for p in primitives:
                if isinstance(p, dict) and p.get("type") == "text":
                    txt = p.get("text","")
                    if txt and (sid in txt or sid.replace("SYM-","") in txt):
                        render_errors.append(f"04_common_symbols.json:{sid}: rectangle+ID text")
                        break
    
    # Universal P1/P2 PROCESS ports
    ports = sym.get("ports", [])
    if ports and all(isinstance(p, dict) and p.get("id","") in ("P1","P2") and p.get("type") == "PROCESS" for p in ports):
        render_errors.append(f"04_common_symbols.json:{sid}: universal P1/P2 PROCESS ports")
    
    # GEN-ALL-BORDER as only layer
    layers = sym.get("layers", [])
    if layers and len(layers) == 1 and layers[0] == "GEN-ALL-BORDER":
        render_errors.append(f"04_common_symbols.json:{sid}: only GEN-ALL-BORDER layer")
    
    # Layers exist
    for layer in layers:
        if layer and layer not in all_layer_ids:
            render_errors.append(f"04_common_symbols.json:{sid}: nonexistent layer '{layer}'")

# QA rules - check assertion/message/evidence
def check_qa_render(qid, item, location):
    if not item.get("assertion_expression"):
        render_errors.append(f"{location}:{qid}: no assertion")
    if not item.get("message_template"):
        render_errors.append(f"{location}:{qid}: no message")
    if not item.get("required_evidence"):
        render_errors.append(f"{location}:{qid}: no evidence")
    # Calc IDs in affected_fields
    for fid in item.get("affected_fields", []):
        if isinstance(fid, str) and fid in all_calc_ids:
            render_errors.append(f"{location}:{qid}: calc_id '{fid}' in affected_fields")
    # Severity
    sev = item.get("severity","INFO").upper()
    if sev not in VALID_SEVERITIES:
        render_errors.append(f"{location}:{qid}: invalid severity '{sev}'")
    # BLOCKED without evidence
    if sev == "BLOCKED" and not item.get("required_evidence"):
        render_errors.append(f"{location}:{qid}: BLOCKED without evidence")

for q in load_json_list(f"{BASE}/08_common_qa_rules.json"):
    check_qa_render(q.get("rule_id","?"), q, "08_common_qa_rules.json")

for tech in TECHS:
    for item in tech_data[tech]["qa_data"]:
        check_qa_render(item.get("rule_id","?"), item, f"{tech}/F_qa_rules.json")

# ============ Compute final validation results ============
structural_pass = (len(errors) == 0 and len(report["broken_references"]) == 0 and len(report["duplicate_ids"]) == 0 and report["placeholder_count"] == 0)
semantic_pass = len(semantic_errors) == 0
render_pass = len(render_errors) == 0
normative_pass = len(unverified_sources) == 0

report["structural_validation"]["status"] = "PASS" if structural_pass else "FAIL"
total_structural_checks = len(errors) + len(report["broken_references"]) + len(report["duplicate_ids"]) + report["placeholder_count"]
report["structural_validation"]["completion_percent"] = 100 if structural_pass else round(100 * max(0, 1 - total_structural_checks/1000), 2)

report["semantic_validation"]["status"] = "PASS" if semantic_pass else "FAIL"
report["semantic_validation"]["errors"] = semantic_errors[:50]  # First 50 for brevity
report["semantic_validation"]["completion_percent"] = 100 if semantic_pass else round(100 * max(0, 1 - len(semantic_errors)/1000), 2)

report["render_validation"]["status"] = "PASS" if render_pass else "FAIL"
report["render_validation"]["errors"] = render_errors[:50]
report["render_validation"]["completion_percent"] = 100 if render_pass else round(100 * max(0, 1 - len(render_errors)/1000), 2)

report["normative_validation"]["status"] = "PASS" if normative_pass else "PARTIAL"
report["normative_validation"]["completion_percent"] = round(100 * (len(src_ids) - len(unverified_sources)) / max(1, len(src_ids)), 2)

if structural_pass and semantic_pass and render_pass and normative_pass:
    report["release_recommendation"] = "READY"
elif structural_pass and semantic_pass and render_pass:
    report["release_recommendation"] = "CONDITIONAL"
else:
    report["release_recommendation"] = "NOT_READY"

# Add summary
report["files_discovered"] = files_discovered
report["files_read"] = files_read
report["bytes_read"] = bytes_read
report["all_drawings_checked"] = all_drawings_checked
report["all_drawings_resolved"] = all_drawings_resolved

# Save report
out_path = f"{BASE}/validation_report.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# Print summary
print("=" * 70)
print("VALIDACIÓN FORENSE v2 - cad_knowledge_base")
print("=" * 70)
print(f"Files discovered: {files_discovered}")
print(f"Files read: {files_read}")
print(f"Bytes read: {bytes_read}")
print(f"All drawings checked: {all_drawings_checked}")
print(f"All drawings resolved: {all_drawings_resolved}")
print()
print(f"Structural: {report['structural_validation']['status']} ({report['structural_validation']['completion_percent']}%)")
print(f"  Errors: {len(errors)}")
print(f"  Broken refs: {len(report['broken_references'])}")
print(f"  Duplicate IDs: {len(report['duplicate_ids'])}")
print(f"  Placeholders: {report['placeholder_count']}")
print(f"  Policy gaps: {len(report['missing_data_policy_gaps'])}")
print()
print(f"Semantic: {report['semantic_validation']['status']} ({report['semantic_validation']['completion_percent']}%)")
print(f"  Semantic errors: {len(semantic_errors)}")
print()
print(f"Render: {report['render_validation']['status']} ({report['render_validation']['completion_percent']}%)")
print(f"  Render errors: {len(render_errors)}")
print()
print(f"Normative: {report['normative_validation']['status']} ({report['normative_validation']['completion_percent']}%)")
print(f"  Verified primary: {report['normative_validation']['verified_primary_sources']}")
print(f"  Unverified required: {len(unverified_sources)}")
print()
print(f"Release recommendation: {report['release_recommendation']}")

if errors:
    print(f"\nFirst 20 structural errors:")
    for e in errors[:20]:
        print(f"  - {e}")
if semantic_errors:
    print(f"\nFirst 20 semantic errors:")
    for e in semantic_errors[:20]:
        print(f"  - {e}")
if render_errors:
    print(f"\nFirst 20 render errors:")
    for e in render_errors[:20]:
        print(f"  - {e}")

# Exit code: 0 only if structural, semantic, render all PASS
exit_code = 0 if (structural_pass and semantic_pass and render_pass) else 1
sys.exit(exit_code)
