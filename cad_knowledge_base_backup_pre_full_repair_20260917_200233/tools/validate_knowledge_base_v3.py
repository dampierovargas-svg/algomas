#!/usr/bin/env python3
"""
Validador de Base de Conocimiento CAD - Versión 3.0
Valida esquemas, referencias, fórmulas, geometrías, símbolos y QA.
Compatible con Windows sin variables de entorno especiales.
"""

import json
import csv
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime

# Constantes de codificación
ENCODING_READ = "utf-8-sig"
ENCODING_WRITE = "utf-8"

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {
            "files_read": 0,
            "calculations_common": 0,
            "calculations_tech": 0,
            "geometry_rules": 0,
            "qa_rules": 0,
            "symbols": 0,
            "drawings": 0,
            "sources_primary_verified": 0,
            "sources_primary_blocked": 0,
            "formulas_with_generic_content": 0,
            "geometry_with_generic_algorithm": 0,
            "qa_with_constant_assertion": 0,
            "symbols_with_generic_name": 0,
            "symbols_with_generic_discipline": 0,
            "symbols_with_generic_ports": 0,
        }
    
    def add_error(self, code, message, file_path=None, record_id=None):
        self.errors.append({
            "code": code,
            "message": message,
            "file": file_path,
            "id": record_id
        })
    
    def add_warning(self, code, message, file_path=None, record_id=None):
        self.warnings.append({
            "code": code,
            "message": message,
            "file": file_path,
            "id": record_id
        })

def read_json_file(path):
    """Lee archivo JSON con codificación UTF-8."""
    try:
        with open(path, "r", encoding=ENCODING_READ) as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)

def read_csv_file(path):
    """Lee archivo CSV con codificación UTF-8."""
    try:
        with open(path, "r", encoding=ENCODING_READ, newline="") as f:
            reader = csv.DictReader(f)
            return list(reader), None
    except Exception as e:
        return None, str(e)

def validate_formula_structure(formula, file_path):
    """Valida la estructura de una fórmula según contrato v3."""
    errors = []
    warnings = []
    
    calc_id = formula.get("calculation_id", "UNKNOWN")
    name_es = formula.get("name_es", "")
    
    # Verificar claves canónicas requeridas
    required_keys = [
        "calculation_id", "name_es", "purpose", "domain_tags",
        "applicability_expression", "input_field_ids", "derived_input_ids",
        "equations_ascii", "variables", "outputs", "source_ids"
    ]
    
    for key in required_keys:
        if key not in formula:
            errors.append(("E_FORMULA_MISSING_KEY", f"Falta clave '{key}'", calc_id))
    
    # Verificar contenido genérico prohibido
    equations = formula.get("equations_ascii", [])
    for eq in equations:
        generic_patterns = [
            "y = f(x)", "calculate(", "inputs within valid ranges",
            "tech_specific_formula", "generic_formula", "COMPUTE positions"
        ]
        for pattern in generic_patterns:
            if pattern.lower() in eq.lower():
                errors.append(("E_FORMULA_GENERIC", f"Ecuación genérica detectada: {eq[:50]}", calc_id))
    
    # Verificar variables
    variables = formula.get("variables", [])
    for var in variables:
        if var.get("type") == "input" and not var.get("origin_field_id"):
            errors.append(("E_FORMULA_INPUT_NO_ORIGIN", f"Variable input sin origin_field_id: {var.get('name')}", calc_id))
        
        unit = var.get("unit", "")
        if unit in ["various", "various_units", "-"]:
            warnings.append(("W_FORMULA_UNIT_VAGUE", f"Unidad vaga: {unit}", calc_id))
    
    # Verificar outputs
    outputs = formula.get("outputs", [])
    for out in outputs:
        if not out.get("id"):
            errors.append(("E_FORMULA_OUTPUT_NO_ID", "Output sin ID", calc_id))
        if not out.get("unit"):
            errors.append(("E_FORMULA_OUTPUT_NO_UNIT", "Output sin unidad", calc_id))
    
    # Verificar ecuaciones coherentes con el nombre
    purpose = formula.get("purpose", "").lower()
    name_lower = name_es.lower()
    
    # Ejemplo: si es sobre Weibull, la ecuación debe mencionar Weibull o parámetros k,c
    if "weibull" in name_lower or "weibull" in purpose:
        has_weibull_eq = any("weibull" in eq.lower() or "k =" in eq.lower() or "c =" in eq.lower() 
                            for eq in equations)
        if not has_weibull_eq and equations:
            warnings.append(("W_FORMULA_NAME_MISMATCH", "Nombre menciona Weibull pero ecuaciones no", calc_id))
    
    return errors, warnings

def validate_geometry_structure(geometry, file_path):
    """Valida la estructura de una regla geométrica."""
    errors = []
    
    geom_id = geometry.get("geometry_rule_id", "UNKNOWN")
    name_es = geometry.get("name_es", "")
    
    # Verificar algoritmo genérico
    algorithm = geometry.get("layout_algorithm", "")
    pseudocode = geometry.get("pseudocode", "")
    
    generic_algorithms = [
        "tech_specific_layout_algorithm", "deterministic_layout_placement",
        "generic_layout", "place_entities", "calculate_positions",
        "COMPUTE positions based on field values"
    ]
    
    for generic in generic_algorithms:
        if generic.lower() in algorithm.lower() or generic.lower() in pseudocode.lower():
            errors.append(("E_GEOMETRY_GENERIC", f"Algoritmo genérico: {algorithm[:50]}", geom_id))
    
    # Verificar domain_tags
    if not geometry.get("domain_tags"):
        errors.append(("E_GEOMETRY_NO_DOMAIN_TAGS", "Falta domain_tags", geom_id))
    
    return errors

def validate_symbol_structure(symbol, file_path):
    """Valida la estructura de un símbolo."""
    errors = []
    
    sym_id = symbol.get("symbol_id", "UNKNOWN")
    name = symbol.get("name", "")
    discipline = symbol.get("discipline", "")
    ports = symbol.get("ports", [])
    
    # Verificar nombre genérico
    if name.startswith("Símbolo:") or name.startswith("Symbol:"):
        errors.append(("E_SYMBOL_GENERIC_NAME", f"Nombre genérico: {name}", sym_id))
    
    # Verificar disciplina
    if discipline == "GEN":
        # Símbolos que no deberían ser GEN
        non_gen_keywords = ["PLC", "RTU", "CT", "PT", "RELAY", "BREAKER", "MCC"]
        for kw in non_gen_keywords:
            if kw in name.upper() or kw in sym_id.upper():
                errors.append(("E_SYMBOL_WRONG_DISCIPLINE", f"Disciplina GEN incorrecta para {name}", sym_id))
                break
    
    # Verificar puertos genéricos
    for port in ports:
        port_name = port.get("name", "")
        if port_name in ["IN", "OUT", "IN/OUT PROCESS", "PROCESS"]:
            errors.append(("E_SYMBOL_GENERIC_PORT", f"Puerto genérico: {port_name}", sym_id))
    
    return errors

def validate_qa_rule(rule, file_path):
    """Valida una regla QA."""
    errors = []
    
    qa_id = rule.get("qa_rule_id", "UNKNOWN")
    assertion = rule.get("assertion_expression", "")
    message = rule.get("message_template", "")
    
    # Verificar assertion constante
    if assertion.strip().lower() in ["true", "false", "1", "0"]:
        errors.append(("E_QA_CONSTANT_ASSERTION", f"Assertion constante: {assertion}", qa_id))
    
    # Verificar mensaje genérico
    generic_messages = ["verificación fallida", "revisar dependencias", "check dependencies"]
    for gm in generic_messages:
        if gm.lower() in message.lower():
            errors.append(("E_QA_GENERIC_MESSAGE", f"Mensaje genérico: {message[:50]}", qa_id))
    
    # Verificar campos afectados
    affected_fields = rule.get("affected_fields", [])
    if not affected_fields:
        errors.append(("E_QA_NO_AFFECTED_FIELDS", "No tiene affected_fields", qa_id))
    
    # Verificar planos afectados
    affected_drawings = rule.get("affected_drawings", [])
    if not affected_drawings:
        errors.append(("E_QA_NO_AFFECTED_DRAWINGS", "No tiene affected_drawings", qa_id))
    
    return errors

def main():
    result = ValidationResult()
    base_path = Path(__file__).parent.parent
    
    print("=" * 80)
    print("VALIDADOR CAD KNOWLEDGE BASE V3")
    print(f"Fecha: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    # [1] Validar archivos comunes
    print("[1/6] Validando archivos comunes...")
    
    # Common calculations
    calc_path = base_path / "05_common_calculations.json"
    if calc_path.exists():
        data, err = read_json_file(calc_path)
        if data:
            result.stats["calculations_common"] = len(data)
            for item in data:
                errs, warns = validate_formula_structure(item, str(calc_path))
                for e in errs:
                    result.add_error(e[0], e[1], str(calc_path), e[2])
                for w in warns:
                    result.add_warning(w[0], w[1], str(calc_path), w[2])
            print(f"  - 05_common_calculations.json: {len(data)} cálculos, {sum(1 for _ in data)} verificados")
        else:
            result.add_error("E_FILE_READ", err, str(calc_path))
    
    # Common geometry rules
    geom_path = base_path / "07_common_geometry_rules.json"
    if geom_path.exists():
        data, err = read_json_file(geom_path)
        if data:
            result.stats["geometry_rules"] = len(data)
            for item in data:
                errs = validate_geometry_structure(item, str(geom_path))
                for e in errs:
                    result.add_error(e[0], e[1], str(geom_path), e[2])
            print(f"  - 07_common_geometry_rules.json: {len(data)} reglas")
    
    # Common QA rules
    qa_path = base_path / "08_common_qa_rules.json"
    if qa_path.exists():
        data, err = read_json_file(qa_path)
        if data:
            result.stats["qa_rules"] = len(data)
            for item in data:
                errs = validate_qa_rule(item, str(qa_path))
                for e in errs:
                    result.add_error(e[0], e[1], str(qa_path), e[2])
            print(f"  - 08_common_qa_rules.json: {len(data)} reglas")
    
    # Common symbols
    sym_path = base_path / "04_common_symbols.json"
    if sym_path.exists():
        data, err = read_json_file(sym_path)
        if data:
            result.stats["symbols"] = len(data)
            sym_errors = 0
            for item in data:
                errs = validate_symbol_structure(item, str(sym_path))
                for e in errs:
                    result.add_error(e[0], e[1], str(sym_path), e[2])
                    sym_errors += 1
            print(f"  - 04_common_symbols.json: {len(data)} símbolos, {sym_errors} errores")
    
    # [2] Validar tecnologías
    print()
    print("[2/6] Validando tecnologías...")
    
    tech_path = base_path / "technologies"
    if tech_path.exists():
        total_formulas = 0
        all_equations = set()
        generic_geometries = 0
        
        for tech_dir in sorted(tech_path.iterdir()):
            if tech_dir.is_dir() and tech_dir.name.startswith("0"):
                # Fórmulas
                formulas_file = tech_dir / "C_formulas.json"
                if formulas_file.exists():
                    data, err = read_json_file(formulas_file)
                    if data:
                        total_formulas += len(data)
                        for item in data:
                            errs, warns = validate_formula_structure(item, str(formulas_file))
                            for e in errs:
                                result.add_error(e[0], e[1], str(formulas_file), e[2])
                            for w in warns:
                                result.add_warning(w[0], w[1], str(formulas_file), w[2])
                            
                            # Contar ecuaciones únicas
                            for eq in item.get("equations_ascii", []):
                                all_equations.add(eq)
                            
                            result.stats["calculations_tech"] += 1
                
                # Geometrías
                geom_file = tech_dir / "D_geometry_rules.json"
                if geom_file.exists():
                    data, err = read_json_file(geom_file)
                    if data:
                        for item in data:
                            errs = validate_geometry_structure(item, str(geom_file))
                            for e in errs:
                                result.add_error(e[0], e[1], str(geom_file), e[2])
                                if e[0] == "E_GEOMETRY_GENERIC":
                                    generic_geometries += 1
        
        result.stats["formulas_with_generic_content"] = sum(
            1 for e in result.errors if e["code"] == "E_FORMULA_GENERIC"
        )
        result.stats["geometry_with_generic_algorithm"] = generic_geometries
        
        print(f"  Total fórmulas tecnologías: {total_formulas}")
        print(f"  Ecuaciones distintas: {len(all_equations)}")
        print(f"  Geometrías con algoritmo genérico: {generic_geometries}")
    
    # [3] Validar fuentes
    print()
    print("[3/6] Validando fuentes...")
    
    source_file = base_path / "00_source_register.csv"
    if source_file.exists():
        data, err = read_csv_file(source_file)
        if data:
            primary_verified = 0
            primary_blocked = 0
            
            for row in data:
                is_primary = row.get("primary_or_secondary", "").lower() == "primary"
                is_accessible = row.get("accessible_full_text", "").lower() == "true"
                
                if is_primary:
                    if is_accessible:
                        primary_verified += 1
                    else:
                        primary_blocked += 1
            
            result.stats["sources_primary_verified"] = primary_verified
            result.stats["sources_primary_blocked"] = primary_blocked
            print(f"  Fuentes primarias verificadas: {primary_verified}")
            print(f"  Fuentes primarias bloqueadas: {primary_blocked}")
    
    # Resumen
    print()
    print("=" * 80)
    print("RESUMEN DE VALIDACIÓN")
    print("=" * 80)
    print(f"Errores estructurales: {sum(1 for e in result.errors if e['code'].startswith('E_SCHEMA') or e['code'].startswith('E_FILE'))}")
    print(f"Errores semánticos (fórmulas): {sum(1 for e in result.errors if e['code'].startswith('E_FORMULA'))}")
    print(f"Errores semánticos (geometrías): {sum(1 for e in result.errors if e['code'].startswith('E_GEOMETRY'))}")
    print(f"Errores semánticos (QA): {sum(1 for e in result.errors if e['code'].startswith('E_QA'))}")
    print(f"Errores semánticos (símbolos): {sum(1 for e in result.errors if e['code'].startswith('E_SYMBOL'))}")
    print(f"Total errores: {len(result.errors)}")
    print(f"Total warnings: {len(result.warnings)}")
    print()
    
    # Guardar informe
    report = {
        "validation_date": datetime.now().isoformat(),
        "stats": result.stats,
        "errors": result.errors,
        "warnings": result.warnings,
        "summary": {
            "total_errors": len(result.errors),
            "total_warnings": len(result.warnings),
            "structural_errors": sum(1 for e in result.errors if e['code'].startswith('E_SCHEMA') or e['code'].startswith('E_FILE')),
            "formula_errors": sum(1 for e in result.errors if e['code'].startswith('E_FORMULA')),
            "geometry_errors": sum(1 for e in result.errors if e['code'].startswith('E_GEOMETRY')),
            "qa_errors": sum(1 for e in result.errors if e['code'].startswith('E_QA')),
            "symbol_errors": sum(1 for e in result.errors if e['code'].startswith('E_SYMBOL')),
        },
        "integration_recommendation": "READY" if len(result.errors) == 0 else "NOT_READY",
        "official_issue_recommendation": "BLOCKED" if result.stats["sources_primary_verified"] == 0 else "CONDITIONAL"
    }
    
    report_path = base_path / "validation_report_v3.json"
    with open(report_path, "w", encoding=ENCODING_WRITE, newline="") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Informe guardado en: {report_path}")
    
    # Código de salida
    sys.exit(0 if len(result.errors) == 0 else 1)

if __name__ == "__main__":
    main()
