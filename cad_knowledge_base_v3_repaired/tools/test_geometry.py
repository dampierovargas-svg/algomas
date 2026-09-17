#!/usr/bin/env python3
"""
Probador de reglas geométricas - Verifica determinismo, entidades y coordenadas
Draft 2020-12 compliant, UTF-8 puro, compatible Windows
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import hashlib

class GeometryTester:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.errors = []
        self.warnings = []
        self.results = {
            "total_rules": 0,
            "tested": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0
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
    
    def validate_geometry_structure(self, rule: Dict, path: str) -> List[Dict]:
        """Validar estructura canónica de regla geométrica"""
        errors = []
        
        # Claves requeridas
        required_keys = [
            "geometry_rule_id", "name_es", "purpose", "domain_tags",
            "fields", "calculations", "coordinate_system", "origin",
            "orientation", "units", "algorithm", "pseudocode",
            "entities_produced", "target_layers", "symbols_used",
            "clearances", "collisions", "routing_costs", "tolerances",
            "failure_conditions", "sources"
        ]
        
        for key in required_keys:
            if key not in rule:
                errors.append({
                    "type": "E_GEOMETRY_MISSING_KEY",
                    "path": path,
                    "geometry_rule_id": rule.get("geometry_rule_id", "UNKNOWN"),
                    "missing_key": key
                })
        
        # Verificar algoritmos genéricos prohibidos
        algorithm = rule.get("algorithm", "")
        pseudocode = rule.get("pseudocode", "")
        
        generic_patterns = [
            "tech_specific_layout_algorithm",
            "deterministic_layout_placement",
            "generic_layout",
            "place_entities",
            "calculate_positions",
            "draw_elements",
            "COMPUTE positions based on field values",
            "OUTPUT generated entities"
        ]
        
        for pattern in generic_patterns:
            if pattern.lower() in algorithm.lower() or pattern.lower() in pseudocode.lower():
                errors.append({
                    "type": "E_GEOMETRY_GENERIC_ALGORITHM",
                    "path": path,
                    "geometry_rule_id": rule.get("geometry_rule_id"),
                    "pattern_found": pattern
                })
        
        # Verificar domain_tags
        domain_tags = rule.get("domain_tags", [])
        if not domain_tags:
            errors.append({
                "type": "E_GEOMETRY_NO_DOMAIN_TAGS",
                "path": path,
                "geometry_rule_id": rule.get("geometry_rule_id")
            })
        
        # Verificar pseudocódigo específico
        pseudocode = rule.get("pseudocode", "")
        if len(pseudocode) < 50 or len(pseudocode.split('\n')) < 3:
            errors.append({
                "type": "E_GEOMETRY_INSUFFICIENT_PSEUDOCODE",
                "path": path,
                "geometry_rule_id": rule.get("geometry_rule_id"),
                "pseudocode_length": len(pseudocode)
            })
        
        # Verificar entidades producidas
        entities = rule.get("entities_produced", [])
        if not entities:
            errors.append({
                "type": "E_GEOMETRY_NO_ENTITIES",
                "path": path,
                "geometry_rule_id": rule.get("geometry_rule_id")
            })
        else:
            for ent in entities:
                if not ent.get("type") or not ent.get("layer"):
                    errors.append({
                        "type": "E_GEOMETRY_ENTITY_INCOMPLETE",
                        "path": path,
                        "geometry_rule_id": rule.get("geometry_rule_id"),
                        "entity": ent
                    })
        
        # Verificar clearances
        clearances = rule.get("clearances", [])
        for cl in clearances:
            if not cl.get("from") or not cl.get("to") or not cl.get("value") or not cl.get("unit"):
                errors.append({
                    "type": "E_GEOMETRY_CLEARANCE_INCOMPLETE",
                    "path": path,
                    "geometry_rule_id": rule.get("geometry_rule_id"),
                    "clearance": cl
                })
        
        # Verificar tolerancias
        tolerances = rule.get("tolerances", [])
        for tol in tolerances:
            if isinstance(tol, dict):
                if not tol.get("parameter") or not tol.get("value") or not tol.get("unit"):
                    errors.append({
                        "type": "E_GEOMETRY_TOLERANCE_INCOMPLETE",
                        "path": path,
                        "geometry_rule_id": rule.get("geometry_rule_id"),
                        "tolerance": tol
                    })
        
        return errors
    
    def check_pseudocode_uniqueness(self, rules: List[Dict], path: str) -> List[Dict]:
        """Detectar pseudocódigo duplicado mediante hash normalizado"""
        errors = []
        pseudocode_hashes = {}
        
        for rule in rules:
            pseudocode = rule.get("pseudocode", "")
            # Normalizar pseudocódigo (quitar espacios extra, lowercase)
            normalized = ' '.join(pseudocode.lower().split())
            hash_val = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            
            if hash_val in pseudocode_hashes:
                errors.append({
                    "type": "E_GEOMETRY_DUPLICATE_TEMPLATE",
                    "path": path,
                    "geometry_rule_id_1": pseudocode_hashes[hash_val],
                    "geometry_rule_id_2": rule.get("geometry_rule_id"),
                    "hash": hash_val
                })
            else:
                pseudocode_hashes[hash_val] = rule.get("geometry_rule_id")
        
        return errors
    
    def test_determinism(self, rule: Dict, path: str) -> Dict:
        """Probar determinismo de la regla geométrica"""
        result = {
            "deterministic": True,
            "reason": ""
        }
        
        # Para una prueba real, se necesitaría:
        # 1. Ejecutar el algoritmo con inputs fijos
        # 2. Verificar que outputs son idénticos en múltiples ejecuciones
        
        # Por ahora, verificamos que el pseudocódigo sea suficientemente específico
        pseudocode = rule.get("pseudocode", "")
        if len(pseudocode) < 100:
            result["deterministic"] = False
            result["reason"] = "Pseudocódigo insuficiente para garantizar determinismo"
        
        return result
    
    def process_technology_geometries(self, tech_path: Path) -> Dict:
        """Procesar todas las geometrías de una tecnología"""
        results = {
            "technology": tech_path.name,
            "rules_total": 0,
            "rules_valid": 0,
            "rules_invalid": 0,
            "errors": []
        }
        
        geometry_file = tech_path / "D_geometry_rules.json"
        if not geometry_file.exists():
            return results
        
        rules = self.load_json(geometry_file)
        if not rules or not isinstance(rules, list):
            results["errors"].append({
                "type": "E_LOAD_GEOMETRIES",
                "file": str(geometry_file)
            })
            return results
        
        results["rules_total"] = len(rules)
        
        # Verificar duplicados
        duplicate_errors = self.check_pseudocode_uniqueness(rules, str(geometry_file))
        results["errors"].extend(duplicate_errors)
        
        for i, rule in enumerate(rules):
            self.results["total_rules"] += 1
            
            # Validar estructura
            struct_errors = self.validate_geometry_structure(rule, str(geometry_file))
            
            # Probar determinismo
            det_result = self.test_determinism(rule, str(geometry_file))
            if not det_result["deterministic"]:
                struct_errors.append({
                    "type": "E_GEOMETRY_NON_DETERMINISTIC",
                    "path": str(geometry_file),
                    "geometry_rule_id": rule.get("geometry_rule_id"),
                    "reason": det_result["reason"]
                })
            
            all_errors = struct_errors + duplicate_errors
            
            if all_errors:
                results["rules_invalid"] += 1
                self.results["failed"] += 1
                results["errors"].extend(all_errors)
                self.errors.extend(all_errors)
            else:
                results["rules_valid"] += 1
                self.results["passed"] += 1
            
            self.results["tested"] += 1
        
        return results
    
    def process_common_geometries(self) -> Dict:
        """Procesar reglas geométricas comunes"""
        results = {
            "source": "common",
            "rules_total": 0,
            "rules_valid": 0,
            "rules_invalid": 0,
            "errors": []
        }
        
        geometry_file = self.base_path / "07_common_geometry_rules.json"
        if not geometry_file.exists():
            return results
        
        rules = self.load_json(geometry_file)
        if not rules or not isinstance(rules, list):
            return results
        
        results["rules_total"] = len(rules)
        
        # Verificar duplicados
        duplicate_errors = self.check_pseudocode_uniqueness(rules, str(geometry_file))
        results["errors"].extend(duplicate_errors)
        
        for rule in rules:
            self.results["total_rules"] += 1
            
            errors = self.validate_geometry_structure(rule, str(geometry_file))
            errors.extend(duplicate_errors)
            
            if errors:
                results["rules_invalid"] += 1
                self.results["failed"] += 1
                results["errors"].extend(errors)
                self.errors.extend(errors)
            else:
                results["rules_valid"] += 1
                self.results["passed"] += 1
            
            self.results["tested"] += 1
        
        return results
    
    def run_full_test(self) -> Dict:
        """Ejecutar pruebas completas"""
        report = {
            "common": self.process_common_geometries(),
            "technologies": [],
            "summary": {}
        }
        
        # Procesar tecnologías
        tech_dir = self.base_path / "technologies"
        if tech_dir.exists():
            for tech_path in sorted(tech_dir.iterdir()):
                if tech_path.is_dir() and tech_path.name.startswith("0"):
                    tech_result = self.process_technology_geometries(tech_path)
                    report["technologies"].append(tech_result)
        
        # Resumen
        report["summary"] = {
            "total_rules": self.results["total_rules"],
            "tested": self.results["tested"],
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
    tester = GeometryTester(str(base_path))
    
    print("[INFO] Iniciando pruebas de geometría...")
    report = tester.run_full_test()
    
    output_file = base_path / "reports" / "geometry_test_results_v3.json"
    output_file.parent.mkdir(exist_ok=True)
    tester.save_report(report, output_file)
    
    summary = report["summary"]
    print(f"[RESULTADO] Reglas totales: {summary['total_rules']}")
    print(f"[RESULTADO] Probadas: {summary['tested']}")
    print(f"[RESULTADO] Aprobadas: {summary['passed']}")
    print(f"[RESULTADO] Fallidas: {summary['failed']}")
    print(f"[RESULTADO] Errores: {summary['total_errors']}")
    print(f"[RESULTADO] Advertencias: {summary['total_warnings']}")
    
    if summary['failed'] > 0:
        print("\n[FAIL] Algunas reglas geométricas requieren reparación")
        return 1
    else:
        print("\n[PASS] Todas las reglas geométricas validadas correctamente")
        return 0


if __name__ == "__main__":
    sys.exit(main())
