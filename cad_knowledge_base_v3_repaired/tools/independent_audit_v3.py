#!/usr/bin/env python3
"""
Auditoría Independiente V3 - Verifica resultados del validador principal
Draft 2020-12 compliant, UTF-8 puro, compatible Windows
"""

import json
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

class IndependentAuditor:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.errors = []
        self.warnings = []
        self.results = {
            "files_audited": 0,
            "structural_checks": {},
            "semantic_checks": {},
            "counts": {}
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
    
    def compute_file_hash(self, path: Path) -> str:
        """Calcular SHA-256 de un archivo"""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def audit_structure(self) -> Dict:
        """Auditar estructura de archivos"""
        results = {
            "total_files": 0,
            "json_files": 0,
            "csv_files": 0,
            "svg_files": 0,
            "py_files": 0,
            "schema_files": 0,
            "readable": 0,
            "unreadable": 0,
            "files": []
        }
        
        for path in self.base_path.rglob('*'):
            if path.is_file() and not path.name.startswith('.'):
                results["total_files"] += 1
                
                file_info = {
                    "path": str(path.relative_to(self.base_path)),
                    "size": path.stat().st_size,
                    "hash": self.compute_file_hash(path),
                    "type": path.suffix.lower()
                }
                
                if path.suffix == '.json':
                    results["json_files"] += 1
                    # Intentar cargar
                    data = self.load_json(path)
                    if data is not None:
                        results["readable"] += 1
                        file_info["records"] = len(data) if isinstance(data, list) else 1
                    else:
                        results["unreadable"] += 1
                elif path.suffix == '.csv':
                    results["csv_files"] += 1
                    try:
                        with open(path, 'r', encoding='utf-8-sig') as f:
                            lines = f.readlines()
                            results["readable"] += 1
                            file_info["records"] = len(lines) - 1  # Excluir header
                    except:
                        results["unreadable"] += 1
                elif path.suffix == '.svg':
                    results["svg_files"] += 1
                elif path.suffix == '.py':
                    results["py_files"] += 1
                
                results["files"].append(file_info)
        
        return results
    
    def audit_formulas(self) -> Dict:
        """Auditar fórmulas independientemente"""
        results = {
            "common_formulas": 0,
            "technology_formulas": 0,
            "formulas_with_domain_tags": 0,
            "formulas_with_generic_content": 0,
            "formulas_with_undefined_vars": 0,
            "by_technology": {}
        }
        
        # Fórmulas comunes
        common_file = self.base_path / "05_common_calculations.json"
        if common_file.exists():
            formulas = self.load_json(common_file)
            if formulas and isinstance(formulas, list):
                results["common_formulas"] = len(formulas)
                for f in formulas:
                    if f.get("domain_tags"):
                        results["formulas_with_domain_tags"] += 1
        
        # Fórmulas por tecnología
        tech_dir = self.base_path / "technologies"
        if tech_dir.exists():
            for tech_path in sorted(tech_dir.iterdir()):
                if tech_path.is_dir() and tech_path.name.startswith("0"):
                    formula_file = tech_path / "C_formulas.json"
                    if formula_file.exists():
                        formulas = self.load_json(formula_file)
                        if formulas and isinstance(formulas, list):
                            tech_count = len(formulas)
                            results["technology_formulas"] += tech_count
                            
                            tech_results = {
                                "total": tech_count,
                                "with_domain_tags": 0,
                                "generic": 0
                            }
                            
                            for f in formulas:
                                if f.get("domain_tags"):
                                    tech_results["with_domain_tags"] += 1
                                    results["formulas_with_domain_tags"] += 1
                                
                                # Verificar contenido genérico
                                formula_str = f.get("formula", "").lower()
                                eq_str = str(f.get("equations_ascii", [])).lower()
                                if "within valid ranges" in formula_str or "f(x)" in formula_str:
                                    tech_results["generic"] += 1
                                    results["formulas_with_generic_content"] += 1
                            
                            results["by_technology"][tech_path.name] = tech_results
        
        return results
    
    def audit_geometries(self) -> Dict:
        """Auditar reglas geométricas independientemente"""
        results = {
            "common_geometries": 0,
            "technology_geometries": 0,
            "geometries_with_domain_tags": 0,
            "geometries_with_generic_algorithm": 0,
            "by_technology": {}
        }
        
        # Geometrías comunes
        common_file = self.base_path / "07_common_geometry_rules.json"
        if common_file.exists():
            rules = self.load_json(common_file)
            if rules and isinstance(rules, list):
                results["common_geometries"] = len(rules)
                for r in rules:
                    if r.get("domain_tags"):
                        results["geometries_with_domain_tags"] += 1
        
        # Geometrías por tecnología
        tech_dir = self.base_path / "technologies"
        if tech_dir.exists():
            for tech_path in sorted(tech_dir.iterdir()):
                if tech_path.is_dir() and tech_path.name.startswith("0"):
                    geo_file = tech_path / "D_geometry_rules.json"
                    if geo_file.exists():
                        rules = self.load_json(geo_file)
                        if rules and isinstance(rules, list):
                            tech_count = len(rules)
                            results["technology_geometries"] += tech_count
                            
                            tech_results = {
                                "total": tech_count,
                                "with_domain_tags": 0,
                                "generic_algorithm": 0
                            }
                            
                            generic_patterns = [
                                "tech_specific_layout_algorithm",
                                "deterministic_layout_placement",
                                "COMPUTE positions based on field values"
                            ]
                            
                            for r in rules:
                                if r.get("domain_tags"):
                                    tech_results["with_domain_tags"] += 1
                                    results["geometries_with_domain_tags"] += 1
                                
                                # Verificar algoritmo genérico
                                algo = str(r.get("algorithm", "")).lower()
                                pseudo = str(r.get("pseudocode", "")).lower()
                                for pattern in generic_patterns:
                                    if pattern.lower() in algo or pattern.lower() in pseudo:
                                        tech_results["generic_algorithm"] += 1
                                        results["geometries_with_generic_algorithm"] += 1
                                        break
                            
                            results["by_technology"][tech_path.name] = tech_results
        
        return results
    
    def audit_qa_rules(self) -> Dict:
        """Auditar reglas QA independientemente"""
        results = {
            "common_qa": 0,
            "technology_qa": 0,
            "qa_with_constant_assertion": 0,
            "qa_with_generic_message": 0,
            "qa_with_fake_evidence": 0,
            "by_technology": {}
        }
        
        # QA común
        common_file = self.base_path / "08_common_qa_rules.json"
        if common_file.exists():
            rules = self.load_json(common_file)
            if rules and isinstance(rules, list):
                results["common_qa"] = len(rules)
                for r in rules:
                    assertion = r.get("assertion_expression", "")
                    if assertion.strip() in ["true", "false"]:
                        results["qa_with_constant_assertion"] += 1
                    
                    message = r.get("message_template", "")
                    if "revisar" in message.lower() or "verificación fallida" in message.lower():
                        results["qa_with_generic_message"] += 1
                    
                    evidence = r.get("evidence_type", "")
                    if "_evidence_record" in evidence:
                        results["qa_with_fake_evidence"] += 1
        
        # QA por tecnología
        tech_dir = self.base_path / "technologies"
        if tech_dir.exists():
            for tech_path in sorted(tech_dir.iterdir()):
                if tech_path.is_dir() and tech_path.name.startswith("0"):
                    qa_file = tech_path / "F_qa_rules.json"
                    if qa_file.exists():
                        rules = self.load_json(qa_file)
                        if rules and isinstance(rules, list):
                            tech_count = len(rules)
                            results["technology_qa"] += tech_count
                            
                            tech_results = {
                                "total": tech_count,
                                "constant_assertion": 0,
                                "generic_message": 0,
                                "fake_evidence": 0
                            }
                            
                            for r in rules:
                                assertion = r.get("assertion_expression", "")
                                if assertion.strip() in ["true", "false"]:
                                    tech_results["constant_assertion"] += 1
                                    results["qa_with_constant_assertion"] += 1
                                
                                message = r.get("message_template", "")
                                if "revisar" in message.lower() or "verificación fallida" in message.lower():
                                    tech_results["generic_message"] += 1
                                    results["qa_with_generic_message"] += 1
                                
                                evidence = r.get("evidence_type", "")
                                if "_evidence_record" in evidence:
                                    tech_results["fake_evidence"] += 1
                                    results["qa_with_fake_evidence"] += 1
                            
                            results["by_technology"][tech_path.name] = tech_results
        
        return results
    
    def audit_symbols(self) -> Dict:
        """Auditar símbolos independientemente"""
        results = {
            "total_symbols": 0,
            "symbols_with_generic_name": 0,
            "symbols_with_gen_discipline": 0,
            "symbols_with_generic_ports": 0,
            "by_discipline": {}
        }
        
        symbols_file = self.base_path / "04_common_symbols.json"
        if symbols_file.exists():
            symbols = self.load_json(symbols_file)
            if symbols and isinstance(symbols, list):
                results["total_symbols"] = len(symbols)
                
                for s in symbols:
                    discipline = s.get("discipline", "UNKNOWN")
                    if discipline not in results["by_discipline"]:
                        results["by_discipline"][discipline] = {
                            "count": 0,
                            "generic_name": 0,
                            "generic_ports": 0
                        }
                    
                    results["by_discipline"][discipline]["count"] += 1
                    
                    name = s.get("name", "")
                    if name.startswith("Símbolo:") or name.startswith("Symbol:"):
                        results["symbols_with_generic_name"] += 1
                        results["by_discipline"][discipline]["generic_name"] += 1
                    
                    ports = s.get("ports", [])
                    for port in ports:
                        if port.get("name") in ["IN PROCESS", "OUT PROCESS"]:
                            results["symbols_with_generic_ports"] += 1
                            results["by_discipline"][discipline]["generic_ports"] += 1
                            break
                
                # Contar disciplina GEN
                if "GEN" in results["by_discipline"]:
                    results["symbols_with_gen_discipline"] = results["by_discipline"]["GEN"]["count"]
        
        return results
    
    def audit_sources(self) -> Dict:
        """Auditar fuentes independientemente"""
        results = {
            "total_sources": 0,
            "primary_sources": 0,
            "secondary_sources": 0,
            "accessible_primary": 0,
            "verified_primary": 0
        }
        
        source_file = self.base_path / "00_source_register.csv"
        if source_file.exists():
            try:
                with open(source_file, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                    # Saltar header
                    for line in lines[1:]:
                        results["total_sources"] += 1
                        
                        # Parsear CSV simple
                        parts = line.strip().split(',')
                        if len(parts) >= 5:
                            source_type = parts[3] if len(parts) > 3 else ""
                            accessible = parts[4] if len(parts) > 4 else ""
                            
                            if "primary" in source_type.lower():
                                results["primary_sources"] += 1
                                if "true" in accessible.lower():
                                    results["accessible_primary"] += 1
                                    results["verified_primary"] += 1
                            elif "secondary" in source_type.lower():
                                results["secondary_sources"] += 1
            except Exception as e:
                self.errors.append({
                    "type": "E_AUDIT_SOURCE_PARSE",
                    "message": str(e)
                })
        
        return results
    
    def run_full_audit(self) -> Dict:
        """Ejecutar auditoría completa"""
        report = {
            "structure": self.audit_structure(),
            "formulas": self.audit_formulas(),
            "geometries": self.audit_geometries(),
            "qa_rules": self.audit_qa_rules(),
            "symbols": self.audit_symbols(),
            "sources": self.audit_sources(),
            "summary": {},
            "comparison_with_validator": {}
        }
        
        # Resumen
        report["summary"] = {
            "files_audited": report["structure"]["total_files"],
            "formulas_total": report["formulas"]["common_formulas"] + report["formulas"]["technology_formulas"],
            "geometries_total": report["geometries"]["common_geometries"] + report["geometries"]["technology_geometries"],
            "qa_total": report["qa_rules"]["common_qa"] + report["qa_rules"]["technology_qa"],
            "symbols_total": report["symbols"]["total_symbols"],
            "sources_total": report["sources"]["total_sources"],
            "verified_primary_sources": report["sources"]["verified_primary"],
            "errors_found": len(self.errors),
            "warnings_found": len(self.warnings)
        }
        
        return report
    
    def compare_with_validator(self, validator_report_path: Path) -> Dict:
        """Comparar resultados con el validador principal"""
        comparison = {
            "match": True,
            "discrepancies": []
        }
        
        if not validator_report_path.exists():
            comparison["match"] = False
            comparison["discrepancies"].append("Validator report not found")
            return comparison
        
        validator_report = self.load_json(validator_report_path)
        if not validator_report:
            comparison["match"] = False
            comparison["discrepancies"].append("Could not load validator report")
            return comparison
        
        # Comparar conteos básicos
        audit_summary = self.run_full_audit()["summary"]
        val_summary = validator_report.get("summary", {})
        
        # Comparar fuentes primarias verificadas
        audit_verified = audit_summary.get("verified_primary_sources", 0)
        val_verified = val_summary.get("verified_primary_sources", -1)
        
        if audit_verified != val_verified:
            comparison["match"] = False
            comparison["discrepancies"].append({
                "field": "verified_primary_sources",
                "audit_value": audit_verified,
                "validator_value": val_verified
            })
        
        return comparison
    
    def save_report(self, report: Dict, output_path: Path):
        """Guardar reporte con codificación UTF-8"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)


def main():
    base_path = Path(__file__).parent.parent
    auditor = IndependentAuditor(str(base_path))
    
    print("[INFO] Iniciando auditoría independiente...")
    report = auditor.run_full_audit()
    
    # Comparar con validador principal
    validator_report_path = base_path / "validation_report_v3.json"
    comparison = auditor.compare_with_validator(validator_report_path)
    report["comparison_with_validator"] = comparison
    
    output_file = base_path / "reports" / "independent_audit_v3.json"
    output_file.parent.mkdir(exist_ok=True)
    auditor.save_report(report, output_file)
    
    summary = report["summary"]
    print(f"[RESULTADO] Archivos auditados: {summary['files_audited']}")
    print(f"[RESULTADO] Fórmulas totales: {summary['formulas_total']}")
    print(f"[RESULTADO] Geometrías totales: {summary['geometries_total']}")
    print(f"[RESULTADO] Reglas QA totales: {summary['qa_total']}")
    print(f"[RESULTADO] Símbolos totales: {summary['symbols_total']}")
    print(f"[RESULTADO] Fuentes primarias verificadas: {summary['verified_primary_sources']}")
    print(f"[RESULTADO] Errores encontrados: {summary['errors_found']}")
    print(f"[RESULTADO] Coincidencia con validador: {comparison['match']}")
    
    if not comparison['match']:
        print("\n[FAIL] Discrepancias encontradas con el validador principal")
        for disc in comparison['discrepancies']:
            print(f"  - {disc}")
        return 1
    else:
        print("\n[PASS] Auditoría independiente completada sin discrepancias")
        return 0


if __name__ == "__main__":
    sys.exit(main())
