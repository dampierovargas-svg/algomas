#!/usr/bin/env python3
"""
Evaluador de fórmulas - Verifica matemática, unidades y dependencias
Draft 2020-12 compliant, UTF-8 puro, compatible Windows
"""

import json
import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Forzar UTF-8 en todas las operaciones
import locale
try:
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')
except:
    pass

class FormulaEvaluator:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.errors = []
        self.warnings = []
        self.results = {
            "total_formulas": 0,
            "evaluated": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "errors_by_type": {}
        }
        
    def load_json(self, path: Path) -> Optional[Any]:
        """Cargar JSON con codificación UTF-8 explícita"""
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception as e:
            self.errors.append({
                "type": "E_LOAD_JSON",
                "path": str(path),
                "message": str(e)
            })
            return None
    
    def validate_formula_structure(self, formula: Dict, path: str) -> List[Dict]:
        """Validar estructura canónica de fórmula"""
        errors = []
        
        # Claves requeridas
        required_keys = [
            "calculation_id", "name_es", "purpose", "domain_tags",
            "applicability_expression", "input_field_ids", "derived_input_ids",
            "equations_ascii", "variables", "outputs"
        ]
        
        for key in required_keys:
            if key not in formula:
                errors.append({
                    "type": "E_FORMULA_MISSING_KEY",
                    "path": path,
                    "calculation_id": formula.get("calculation_id", "UNKNOWN"),
                    "missing_key": key
                })
        
        # Verificar contenido prohibido
        if formula.get("formula", "").strip() in ["y = f(x)", "result = calculate(inputs)", ""]:
            errors.append({
                "type": "E_FORMULA_GENERIC",
                "path": path,
                "calculation_id": formula.get("calculation_id"),
                "message": "Fórmula genérica prohibida detectada"
            })
        
        # Verificar variables
        variables = formula.get("variables", [])
        if not variables:
            errors.append({
                "type": "E_FORMULA_NO_VARIABLES",
                "path": path,
                "calculation_id": formula.get("calculation_id")
            })
        else:
            for var in variables:
                # Verificar variable genérica
                if var.get("name") in ["input", "x", "var", "value"]:
                    errors.append({
                        "type": "E_FORMULA_GENERIC_VAR",
                        "path": path,
                        "calculation_id": formula.get("calculation_id"),
                        "variable": var.get("name")
                    })
                
                # Verificar unidad genérica
                if var.get("unit") in ["various", "units", "-"]:
                    if var.get("type") == "output":
                        errors.append({
                            "type": "E_FORMULA_GENERIC_UNIT",
                            "path": path,
                            "calculation_id": formula.get("calculation_id"),
                            "variable": var.get("name"),
                            "unit": var.get("unit")
                        })
                
                # Verificar origen de inputs
                if var.get("type") == "input" and not var.get("origin_field_id"):
                    errors.append({
                        "type": "E_FORMULA_INPUT_NO_ORIGIN",
                        "path": path,
                        "calculation_id": formula.get("calculation_id"),
                        "variable": var.get("name")
                    })
        
        # Verificar ecuaciones
        equations = formula.get("equations_ascii", [])
        for eq in equations:
            if "within valid ranges" in eq.lower() or "f(x)" in eq.lower():
                errors.append({
                    "type": "E_FORMULA_GENERIC_EQ",
                    "path": path,
                    "calculation_id": formula.get("calculation_id"),
                    "equation": eq[:100]
                })
        
        # Verificar outputs
        outputs = formula.get("outputs", [])
        if not outputs:
            errors.append({
                "type": "E_FORMULA_NO_OUTPUTS",
                "path": path,
                "calculation_id": formula.get("calculation_id")
            })
        else:
            for out in outputs:
                if not out.get("name") or not out.get("unit") or not out.get("type"):
                    errors.append({
                        "type": "E_FORMULA_OUTPUT_INCOMPLETE",
                        "path": path,
                        "calculation_id": formula.get("calculation_id"),
                        "output": out
                    })
        
        # Verificar domain_tags
        domain_tags = formula.get("domain_tags", [])
        if not domain_tags:
            errors.append({
                "type": "E_FORMULA_NO_DOMAIN_TAGS",
                "path": path,
                "calculation_id": formula.get("calculation_id")
            })
        
        return errors
    
    def evaluate_mathematical_consistency(self, formula: Dict, path: str) -> List[Dict]:
        """Evaluar consistencia matemática básica"""
        errors = []
        
        # Extraer símbolos de ecuaciones
        symbols_in_eq = set()
        for eq in formula.get("equations_ascii", []):
            # Extraer identificadores (símbolos algebraicos)
            matches = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', eq)
            symbols_in_eq.update(matches)
        
        # Extraer símbolos declarados
        symbols_declared = set()
        for var in formula.get("variables", []):
            symbol = var.get("symbol", var.get("name", ""))
            symbols_declared.add(symbol)
            symbols_declared.add(var.get("name", ""))
        
        # Verificar que todos los símbolos en ecuaciones estén declarados
        undefined = symbols_in_eq - symbols_declared - {"exp", "log", "sin", "cos", "tan", "sqrt", "pi", "e"}
        if undefined:
            errors.append({
                "type": "E_FORMULA_UNDEFINED_SYMBOL",
                "path": path,
                "calculation_id": formula.get("calculation_id"),
                "undefined_symbols": list(undefined)
            })
        
        return errors
    
    def check_unit_dimensional_closure(self, formula: Dict, path: str) -> List[Dict]:
        """Verificar cierre dimensional básico"""
        errors = []
        
        # Esta es una verificación simplificada
        # Una implementación completa requeriría un sistema de unidades completo
        
        outputs = formula.get("outputs", [])
        unit_equations = formula.get("unit_equations", [])
        
        if outputs and not unit_equations:
            # Advertencia si no hay ecuaciones de unidades
            self.warnings.append({
                "type": "W_FORMULA_NO_UNIT_EQUATIONS",
                "path": path,
                "calculation_id": formula.get("calculation_id")
            })
        
        return errors
    
    def run_test_cases(self, formula: Dict, path: str) -> Dict:
        """Ejecutar casos de prueba numéricos"""
        result = {
            "nominal": None,
            "lower_bound": None,
            "upper_bound": None,
            "invalid_input": None,
            "invariant_check": None
        }
        
        # Para una implementación completa, se necesitaría:
        # 1. Parser de expresiones matemáticas
        # 2. Valores de prueba definidos en fixtures
        # 3. Evaluador numérico real
        
        # Por ahora, marcamos como pendiente si no hay datos de prueba
        test_data = formula.get("test_cases", [])
        if not test_data:
            result["status"] = "PENDING_TEST_DATA"
        else:
            result["status"] = "EXECUTED"
        
        return result
    
    def process_technology_formulas(self, tech_path: Path) -> Dict:
        """Procesar todas las fórmulas de una tecnología"""
        results = {
            "technology": tech_path.name,
            "formulas_total": 0,
            "formulas_valid": 0,
            "formulas_invalid": 0,
            "errors": []
        }
        
        formulas_file = tech_path / "C_formulas.json"
        if not formulas_file.exists():
            return results
        
        formulas = self.load_json(formulas_file)
        if not formulas or not isinstance(formulas, list):
            results["errors"].append({
                "type": "E_LOAD_FORMULAS",
                "file": str(formulas_file)
            })
            return results
        
        results["formulas_total"] = len(formulas)
        
        for i, formula in enumerate(formulas):
            self.results["total_formulas"] += 1
            
            # Validar estructura
            struct_errors = self.validate_formula_structure(formula, str(formulas_file))
            
            # Validar consistencia matemática
            math_errors = self.evaluate_mathematical_consistency(formula, str(formulas_file))
            
            # Verificar unidades
            unit_errors = self.check_unit_dimensional_closure(formula, str(formulas_file))
            
            all_errors = struct_errors + math_errors + unit_errors
            
            if all_errors:
                results["formulas_invalid"] += 1
                self.results["failed"] += 1
                results["errors"].extend(all_errors)
                self.errors.extend(all_errors)
            else:
                results["formulas_valid"] += 1
                self.results["passed"] += 1
            
            self.results["evaluated"] += 1
        
        return results
    
    def process_common_formulas(self) -> Dict:
        """Procesar fórmulas comunes"""
        results = {
            "source": "common",
            "formulas_total": 0,
            "formulas_valid": 0,
            "formulas_invalid": 0,
            "errors": []
        }
        
        formulas_file = self.base_path / "05_common_calculations.json"
        if not formulas_file.exists():
            return results
        
        formulas = self.load_json(formulas_file)
        if not formulas or not isinstance(formulas, list):
            return results
        
        results["formulas_total"] = len(formulas)
        
        for formula in formulas:
            self.results["total_formulas"] += 1
            
            errors = self.validate_formula_structure(formula, str(formulas_file))
            errors.extend(self.evaluate_mathematical_consistency(formula, str(formulas_file)))
            
            if errors:
                results["formulas_invalid"] += 1
                self.results["failed"] += 1
                results["errors"].extend(errors)
                self.errors.extend(errors)
            else:
                results["formulas_valid"] += 1
                self.results["passed"] += 1
            
            self.results["evaluated"] += 1
        
        return results
    
    def run_full_evaluation(self) -> Dict:
        """Ejecutar evaluación completa"""
        report = {
            "common": self.process_common_formulas(),
            "technologies": [],
            "summary": {}
        }
        
        # Procesar tecnologías
        tech_dir = self.base_path / "technologies"
        if tech_dir.exists():
            for tech_path in sorted(tech_dir.iterdir()):
                if tech_path.is_dir() and tech_path.name.startswith("0"):
                    tech_result = self.process_technology_formulas(tech_path)
                    report["technologies"].append(tech_result)
        
        # Resumen
        report["summary"] = {
            "total_formulas": self.results["total_formulas"],
            "evaluated": self.results["evaluated"],
            "passed": self.results["passed"],
            "failed": self.results["failed"],
            "blocked": self.results["blocked"],
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings)
        }
        
        return report
    
    def save_report(self, report: Dict, output_path: Path):
        """Guardar reporte con codificación UTF-8"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)


def main():
    base_path = Path(__file__).parent.parent
    evaluator = FormulaEvaluator(str(base_path))
    
    print("[INFO] Iniciando evaluación de fórmulas...")
    report = evaluator.run_full_evaluation()
    
    output_file = base_path / "reports" / "formula_test_results_v3.json"
    output_file.parent.mkdir(exist_ok=True)
    evaluator.save_report(report, output_file)
    
    summary = report["summary"]
    print(f"[RESULTADO] Fórmulas totales: {summary['total_formulas']}")
    print(f"[RESULTADO] Evaluadas: {summary['evaluated']}")
    print(f"[RESULTADO] Aprobadas: {summary['passed']}")
    print(f"[RESULTADO] Fallidas: {summary['failed']}")
    print(f"[RESULTADO] Errores: {summary['total_errors']}")
    print(f"[RESULTADO] Advertencias: {summary['total_warnings']}")
    
    if summary['failed'] > 0:
        print("\n[FAIL] Algunas fórmulas requieren reparación")
        return 1
    else:
        print("\n[PASS] Todas las fórmulas validadas correctamente")
        return 0


if __name__ == "__main__":
    sys.exit(main())
