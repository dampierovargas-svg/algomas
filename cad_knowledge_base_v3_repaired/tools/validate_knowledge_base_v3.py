#!/usr/bin/env python3
"""
Validador V3 de cad_knowledge_base.
Portabilidad Windows: UTF-8-sig lectura, UTF-8 escritura, sin Unicode ✓/✗.
Códigos de error estables: E_SCHEMA_JSON, E_REF_FIELD, E_FORMULA_GENERIC, etc.
"""

import json
import csv
import hashlib
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Configuración de codificación para Windows
def open_read(path):
    return open(path, 'r', encoding='utf-8-sig')

def open_write(path):
    return open(path, 'w', encoding='utf-8', newline='')

BASE_DIR = Path('.')
ERRORS = []
WARNINGS = []

def add_error(code, message, location, severity='error'):
    ERRORS.append({
        'code': code,
        'message': message,
        'location': str(location),
        'severity': severity
    })

def add_warning(code, message, location):
    WARNINGS.append({
        'code': code,
        'message': message,
        'location': str(location)
    })

# Patrones prohibidos
GENERIC_FORMULA_PATTERNS = [
    'y = f(x)',
    'result = calculate(inputs)',
    'inputs within valid ranges',
    'output within plausible range',
    'input outside valid physical range',
    'invalid inputs',
    'tech_specific_formula',
    'generic_formula'
]

GENERIC_GEOMETRY_PATTERNS = [
    'deterministic_layout_placement',
    'tech_specific_layout_algorithm',
    'generic_layout',
    'place_entities',
    'calculate_positions',
    'draw_elements',
    'compute positions based on field values and design rules'
]

GENERIC_VARIABLE_NAMES = ['input', 'x', 'var', 'value', 'result', 'output']
GENERIC_UNITS = ['various', 'unit', 'unknown', '?']

def validate_json_schema(filepath, schema=None):
    """Valida estructura JSON básica."""
    try:
        with open_read(filepath) as f:
            data = json.load(f)
        return True, data
    except json.JSONDecodeError as e:
        add_error('E_SCHEMA_JSON', f'JSON inválido: {e}', filepath)
        return False, None
    except Exception as e:
        add_error('E_READ_ERROR', f'Error de lectura: {e}', filepath)
        return False, None

def validate_csv(filepath):
    """Valida estructura CSV básica."""
    try:
        with open_read(filepath) as f:
            reader = csv.reader(f)
            rows = list(reader)
        return True, rows
    except Exception as e:
        add_error('E_CSV_ERROR', f'CSV inválido: {e}', filepath)
        return False, []

def check_formula(calc):
    """Valida una fórmula/cálculo según contrato formal."""
    errors = []
    
    # Verificar claves canónicas requeridas
    required_keys = ['calculation_id', 'name_es', 'purpose', 'domain_tags', 
                     'applicability_expression', 'input_field_ids', 'equations_ascii', 
                     'variables', 'outputs']
    for key in required_keys:
        if key not in calc:
            errors.append(f'Falta clave requerida: {key}')
    
    # Verificar ecuaciones genéricas
    equations = calc.get('equations_ascii', [])
    for eq in equations:
        eq_lower = eq.lower()
        if any(p.lower() in eq_lower for p in GENERIC_FORMULA_PATTERNS):
            errors.append(f'Ecuación genérica detectada: {eq[:50]}...')
    
    # Verificar variables
    variables = calc.get('variables', [])
    for v in variables:
        name = v.get('name', '')
        unit = v.get('unit', '')
        var_type = v.get('type', '')
        
        if name.lower() in GENERIC_VARIABLE_NAMES:
            errors.append(f'Variable con nombre genérico: {name}')
        
        if unit.lower() in GENERIC_UNITS:
            errors.append(f'Variable con unidad genérica: {unit}')
        
        # Verificar origin_field_id para inputs
        if var_type == 'input' and not v.get('origin_field_id') and not v.get('origin'):
            errors.append(f'Variable input sin origin_field_id: {name}')
        
        # Verificar constant_value para constants
        if var_type == 'constant' and not v.get('constant_value'):
            errors.append(f'Constante sin valor: {name}')
    
    # Verificar outputs
    outputs = calc.get('outputs', [])
    if not outputs:
        errors.append('Sin outputs definidos')
    
    return errors

def check_geometry_rule(rule):
    """Valida una regla geométrica según contrato formal."""
    errors = []
    
    # Verificar algoritmo genérico
    algo = rule.get('algorithm_pseudocode', [])
    if isinstance(algo, list):
        algo_str = ' '.join(algo).lower()
    else:
        algo_str = str(algo).lower()
    
    if any(p in algo_str for p in GENERIC_GEOMETRY_PATTERNS):
        errors.append(f'Algoritmo genérico detectado en {rule.get("geometry_rule_id", "unknown")}')
    
    # Verificar pseudocódigo específico (mínimo 5 pasos)
    if isinstance(algo, list) and len(algo) < 5:
        errors.append(f'Pseudocódigo insuficiente: {len(algo)} pasos, se requieren mínimo 5')
    
    # Verificar entidades producidas
    entities = rule.get('entities_produced', [])
    if not entities:
        errors.append('Sin entidades producidas definidas')
    
    # Verificar clearances
    clearances = rule.get('clearances', [])
    for c in clearances:
        if not all(k in c for k in ['from_entity', 'to_entity', 'distance', 'unit', 'condition']):
            errors.append(f'Clearance incompleto: {c}')
    
    return errors

def check_qa_rule(rule):
    """Valida una regla QA según contrato formal."""
    errors = []
    
    # Verificar assertion_expression no constante
    expr = rule.get('assertion_expression', '')
    if expr.lower().strip() in ['true', 'false', '1', '0', 'yes', 'no']:
        errors.append(f'Assertion constante: {expr}')
    
    # Verificar mensaje específico
    msg = rule.get('message_template', '')
    if len(msg) < 20:
        errors.append(f'Mensaje demasiado genérico ({len(msg)} chars)')
    
    if 'fallida' in msg.lower() or 'revisar dependencias' in msg.lower():
        errors.append(f'Mensaje genérico tipo "revisar dependencias"')
    
    # Verificar affected_fields no vacío
    fields = rule.get('affected_fields', [])
    if not fields:
        errors.append('affected_fields vacío')
    
    # Verificar affected_drawings no vacío
    drawings = rule.get('affected_drawings', [])
    if not drawings:
        errors.append('affected_drawings vacío')
    
    # Verificar evidence_type no es *_evidence_record
    evidence = rule.get('evidence_type', '')
    if '_evidence_record' in evidence:
        errors.append(f'Evidencia ficticia: {evidence}')
    
    return errors

def check_symbol(sym):
    """Valida un símbolo según contrato formal."""
    errors = []
    
    # Verificar ID sin caracteres prohibidos
    sym_id = sym.get('symbol_id', '')
    if any(c in sym_id for c in ['|', ';', ',', '*']):
        errors.append(f'ID con caracteres prohibidos: {sym_id}')
    
    # Verificar nombre no es "Símbolo: ..."
    name = sym.get('name_es', '')
    if name.startswith('Símbolo:'):
        errors.append(f'Nombre genérico "Símbolo: ...": {name}')
    
    # Verificar disciplina correcta para equipos específicos
    discipline = sym.get('discipline', '')
    keywords_elec = ['PLC', 'RTU', 'CT', 'PT', 'RELAY', 'BREAKER', 'FUSE', 'SWITCH']
    if any(k in name.upper() for k in keywords_elec) and discipline == 'GEN':
        errors.append(f'Disciplina GEN incorrecta para equipo eléctrico: {name}')
    
    # Verificar puertos no genéricos
    ports = sym.get('ports', [])
    generic_ports = ['IN', 'OUT', 'PROCESS', 'IN PROCESS', 'OUT PROCESS', 'IN/OUT PROCESS']
    for p in ports:
        port_type = p.get('type', '')
        if port_type in generic_ports:
            errors.append(f'Puerto genérico {port_type} en símbolo {name}')
    
    return errors

def count_verified_primary_sources(sources):
    """Cuenta fuentes primarias verificadas correctamente."""
    count = 0
    for s in sources:
        if s.get('primary_or_secondary') == 'primary' and s.get('accessible_full_text') == True:
            count += 1
    return count

def main():
    print("=" * 80)
    print("VALIDADOR CAD KNOWLEDGE BASE V3")
    print(f"Fecha: {datetime.now().isoformat()}")
    print("=" * 80)
    
    structural_errors = 0
    semantic_errors = 0
    formula_errors = 0
    geometry_errors = 0
    qa_errors = 0
    symbol_errors = 0
    
    # Validar archivos comunes
    print("\n[1/6] Validando archivos comunes...")
    
    # 05_common_calculations.json
    calc_file = BASE_DIR / '05_common_calculations.json'
    if calc_file.exists():
        ok, calcs = validate_json_schema(calc_file)
        if ok and calcs:
            for c in calcs:
                errs = check_formula(c)
                if errs:
                    formula_errors += len(errs)
                    for e in errs:
                        add_error('E_FORMULA_GENERIC', e, f"{calc_file}:{c.get('calculation_id', 'unknown')}")
            print(f"  - 05_common_calculations.json: {len(calcs)} cálculos, {formula_errors} errores")
    
    # 07_common_geometry_rules.json
    geo_file = BASE_DIR / '07_common_geometry_rules.json'
    if geo_file.exists():
        ok, geos = validate_json_schema(geo_file)
        if ok and geos:
            for g in geos:
                errs = check_geometry_rule(g)
                if errs:
                    geometry_errors += len(errs)
                    for e in errs:
                        add_error('E_GEOMETRY_GENERIC', e, f"{geo_file}:{g.get('geometry_rule_id', 'unknown')}")
            print(f"  - 07_common_geometry_rules.json: {len(geos)} reglas, {geometry_errors} errores")
    
    # 08_common_qa_rules.json
    qa_file = BASE_DIR / '08_common_qa_rules.json'
    if qa_file.exists():
        ok, qas = validate_json_schema(qa_file)
        if ok and qas:
            for q in qas:
                errs = check_qa_rule(q)
                if errs:
                    qa_errors += len(errs)
                    for e in errs:
                        add_error('E_QA_CONSTANT', e, f"{qa_file}:{q.get('qa_rule_id', 'unknown')}")
            print(f"  - 08_common_qa_rules.json: {len(qas)} reglas, {qa_errors} errores")
    
    # 04_common_symbols.json
    sym_file = BASE_DIR / '04_common_symbols.json'
    if sym_file.exists():
        ok, syms = validate_json_schema(sym_file)
        if ok and syms:
            for s in syms:
                errs = check_symbol(s)
                if errs:
                    symbol_errors += len(errs)
                    for e in errs:
                        add_error('E_SYMBOL_GENERIC', e, f"{sym_file}:{s.get('symbol_id', 'unknown')}")
            print(f"  - 04_common_symbols.json: {len(syms)} símbolos, {symbol_errors} errores")
    
    # Validar tecnologías
    print("\n[2/6] Validando tecnologías...")
    tech_dirs = [d for d in BASE_DIR.iterdir() if d.is_dir() and d.name.startswith('0')]
    
    total_generic_geo = 0
    total_formulas = 0
    total_eq_distinct = set()
    
    for tech_dir in sorted(tech_dirs):
        # Fórmulas
        formula_file = tech_dir / 'C_formulas.json'
        if formula_file.exists():
            ok, formulas = validate_json_schema(formula_file)
            if ok and formulas:
                total_formulas += len(formulas)
                for f in formulas:
                    for eq in f.get('equations_ascii', []):
                        total_eq_distinct.add(eq.strip())
                    errs = check_formula(f)
                    if errs:
                        formula_errors += len(errs)
                        for e in errs:
                            add_error('E_FORMULA_GENERIC', e, f"{formula_file}:{f.get('calculation_id', 'unknown')}")
        
        # Geometrías
        geo_file = tech_dir / 'D_geometry_rules.json'
        if geo_file.exists():
            ok, geos = validate_json_schema(geo_file)
            if ok and geos:
                for g in geos:
                    algo = g.get('algorithm_pseudocode', [])
                    algo_str = ' '.join(algo).lower() if isinstance(algo, list) else str(algo).lower()
                    if any(p in algo_str for p in GENERIC_GEOMETRY_PATTERNS):
                        total_generic_geo += 1
                    
                    errs = check_geometry_rule(g)
                    if errs:
                        geometry_errors += len(errs)
                        for e in errs:
                            add_error('E_GEOMETRY_GENERIC', e, f"{geo_file}:{g.get('geometry_rule_id', 'unknown')}")
        
        # QA
        qa_file = tech_dir / 'F_qa_rules.json'
        if qa_file.exists():
            ok, qas = validate_json_schema(qa_file)
            if ok and qas:
                for q in qas:
                    errs = check_qa_rule(q)
                    if errs:
                        qa_errors += len(errs)
                        for e in errs:
                            add_error('E_QA_CONSTANT', e, f"{qa_file}:{q.get('qa_rule_id', 'unknown')}")
    
    print(f"  Total fórmulas tecnologías: {total_formulas}")
    print(f"  Ecuaciones distintas: {len(total_eq_distinct)}")
    print(f"  Geometrías con algoritmo genérico: {total_generic_geo}")
    
    # Fuentes
    print("\n[3/6] Validando fuentes...")
    source_file = BASE_DIR / '00_source_register.csv'
    verified_primary = 0
    blocked_sources = 0
    
    if source_file.exists():
        ok, rows = validate_csv(source_file)
        if ok:
            header = rows[0] if rows else []
            for row in rows[1:]:
                if len(row) >= 6:
                    primary = row[header.index('primary_or_secondary')] if 'primary_or_secondary' in header else ''
                    accessible = row[header.index('accessible_full_text')] if 'accessible_full_text' in header else ''
                    if primary == 'primary' and accessible == 'TRUE':
                        verified_primary += 1
                    elif primary == 'primary' and accessible == 'FALSE':
                        blocked_sources += 1
            
            print(f"  Fuentes primarias verificadas: {verified_primary}")
            print(f"  Fuentes primarias bloqueadas: {blocked_sources}")
    
    # Resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE VALIDACIÓN")
    print("=" * 80)
    
    total_errors = len(ERRORS)
    total_warnings = len(WARNINGS)
    
    print(f"Errores estructurales: {structural_errors}")
    print(f"Errores semánticos (fórmulas): {formula_errors}")
    print(f"Errores semánticos (geometrías): {geometry_errors}")
    print(f"Errores semánticos (QA): {qa_errors}")
    print(f"Errores semánticos (símbolos): {symbol_errors}")
    print(f"Total errores: {total_errors}")
    print(f"Total warnings: {total_warnings}")
    
    # Generar informe
    report = {
        'validation_timestamp': datetime.now().isoformat(),
        'base_directory': str(BASE_DIR),
        'structural_validation': {
            'status': 'FAIL' if structural_errors > 0 else 'PASS',
            'errors': structural_errors
        },
        'semantic_validation': {
            'status': 'FAIL' if (formula_errors + geometry_errors + qa_errors + symbol_errors) > 0 else 'PASS',
            'generic_formulas': formula_errors,
            'generic_geometries': total_generic_geo,
            'constant_qa': qa_errors,
            'generic_symbols': symbol_errors,
            'errors': formula_errors + geometry_errors + qa_errors + symbol_errors
        },
        'integration_recommendation': 'NOT_READY' if total_errors > 0 else 'READY',
        'official_issue_recommendation': 'BLOCKED' if verified_primary == 0 else 'CONDITIONAL',
        'error_details': ERRORS[:100],  # Limitar a 100 errores
        'warning_details': WARNINGS[:100]
    }
    
    with open_write(BASE_DIR / 'validation_report_v3.json') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nInforme guardado en: validation_report_v3.json")
    
    # Código de salida
    sys.exit(1 if total_errors > 0 else 0)

if __name__ == '__main__':
    main()
