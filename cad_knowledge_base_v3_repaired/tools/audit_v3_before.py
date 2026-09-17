#!/usr/bin/env python3
"""
Auditoría inicial de cad_knowledge_base antes de la reparación v3.
Registra: ruta, tamaño, SHA-256, tipo, registros, esquema, estado, referencias.
"""

import json
import hashlib
import os
import csv
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(".")
OUTPUT_FILE = BASE_DIR / "audit_v3_before.json"

def sha256_file(filepath):
    """Calcula SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def count_json_records(filepath):
    """Cuenta registros en JSON (array u objeto con arrays)."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            # Contar arrays dentro del objeto
            counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
            return counts
        return 1
    except Exception as e:
        return {"error": str(e)}

def count_csv_records(filepath):
    """Cuenta filas en CSV."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
            return len(rows) - 1 if rows else 0  # Excluir header
    except Exception as e:
        return {"error": str(e)}

def detect_artifact_type(filepath):
    """Detecta el tipo de artefacto según nombre y extensión."""
    name = filepath.name.lower()
    suffix = filepath.suffix.lower()
    
    if suffix == ".json":
        if "symbol" in name or "symbols" in name:
            return "symbols"
        elif "calculation" in name or "calculations" in name:
            return "calculations"
        elif "geometry" in name:
            return "geometry_rules"
        elif "qa" in name:
            return "qa_rules"
        elif "standard" in name or "cad_standard" in name:
            return "cad_standard"
        elif "layer" in name:
            return "layers"
        elif "drawing" in name or "catalog" in name:
            return "drawing_catalog"
        elif "audit" in name:
            return "audit_report"
        elif "correction" in name or "manifest" in name:
            return "correction_manifest"
        elif "jurisdiction" in name:
            return "jurisdiction"
        elif "source" in name and "register" in name:
            return "source_register"
        elif "input" in name:
            return "project_inputs"
        elif "test" in name or "result" in name:
            return "test_results"
        elif "validation" in name or "report" in name:
            return "validation_report"
        else:
            return "unknown_json"
    elif suffix == ".csv":
        if "layer" in name:
            return "layers"
        elif "input" in name:
            return "project_inputs"
        elif "source" in name:
            return "source_register"
        elif "drawing" in name or "catalog" in name:
            return "drawing_catalog"
        else:
            return "unknown_csv"
    elif suffix == ".svg":
        return "symbol_svg"
    elif suffix == ".png":
        return "symbol_png"
    elif suffix == ".py":
        return "python_script"
    elif suffix == ".schema.json" or "schema" in name:
        return "json_schema"
    else:
        return "other"

def get_expected_schema(filepath):
    """Determina el esquema esperado según el tipo."""
    artifact_type = detect_artifact_type(filepath)
    schema_map = {
        "symbols": "schemas/symbols.schema.json",
        "calculations": "schemas/calculations.schema.json",
        "geometry_rules": "schemas/geometry_rules.schema.json",
        "qa_rules": "schemas/qa_rules.schema.json",
        "cad_standard": "schemas/cad_standard.schema.json",
        "layers": "schemas/layers.schema.json",
        "drawing_catalog": "schemas/drawing_catalog.schema.json",
        "source_register": "schemas/sources.schema.json",
        "project_inputs": "schemas/fields.schema.json",
        "jurisdiction": "schemas/jurisdiction.schema.json",
    }
    return schema_map.get(artifact_type, None)

def extract_outgoing_references(filepath, data):
    """Extrae referencias salientes de un archivo."""
    refs = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for key, value in item.items():
                    if key.endswith("_id") or key.endswith("_ids"):
                        if isinstance(value, str):
                            refs.add(value)
                        elif isinstance(value, list):
                            refs.update(value)
                    elif isinstance(value, str) and ("_id" in key or "ref" in key.lower()):
                        refs.add(value)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if k.endswith("_id") or k.endswith("_ids"):
                                if isinstance(v, str):
                                    refs.add(v)
                                elif isinstance(v, list):
                                    refs.update(v)
    return list(refs)[:50]  # Limitar a 50 referencias

def audit_file(filepath):
    """Audita un solo archivo."""
    rel_path = str(filepath.relative_to(BASE_DIR))
    size = filepath.stat().st_size
    sha = sha256_file(filepath)
    artifact_type = detect_artifact_type(filepath)
    expected_schema = get_expected_schema(filepath)
    
    records = 0
    state = "unreadable"
    outgoing_refs = []
    
    try:
        if filepath.suffix.lower() == ".json":
            with open(filepath, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            records = count_json_records(filepath)
            state = "valid_json"
            outgoing_refs = extract_outgoing_references(filepath, data)
        elif filepath.suffix.lower() == ".csv":
            records = count_csv_records(filepath)
            state = "valid_csv"
        elif filepath.suffix.lower() in [".svg", ".png"]:
            records = 1
            state = "binary_ok"
        elif filepath.suffix.lower() == ".py":
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()
            records = len(content.splitlines())
            state = "valid_python"
        else:
            state = "other_format"
            records = 1
    except json.JSONDecodeError as e:
        state = f"invalid_json: {str(e)}"
    except Exception as e:
        state = f"error: {str(e)}"
    
    return {
        "relative_path": rel_path,
        "size_bytes": size,
        "sha256": sha,
        "artifact_type": artifact_type,
        "record_count": records,
        "expected_schema": expected_schema,
        "state": state,
        "outgoing_references": outgoing_refs
    }

def main():
    print("=" * 80)
    print("AUDITORÍA INICIAL - cad_knowledge_base v3")
    print(f"Fecha: {datetime.now().isoformat()}")
    print("=" * 80)
    
    audit_results = []
    file_count = 0
    
    # Recorrer todos los archivos
    for root, dirs, files in os.walk(BASE_DIR):
        # Excluir directorios de backup y temporales
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__"]]
        
        for filename in files:
            filepath = Path(root) / filename
            if filepath.suffix.lower() in [".gitignore"]:
                continue
                
            print(f"Auditando: {filepath.relative_to(BASE_DIR)}")
            result = audit_file(filepath)
            audit_results.append(result)
            file_count += 1
    
    # Generar informe
    report = {
        "audit_timestamp": datetime.now().isoformat(),
        "base_directory": str(BASE_DIR),
        "total_files": file_count,
        "files": audit_results,
        "summary": {
            "by_type": {},
            "by_state": {},
            "total_size_bytes": sum(f["size_bytes"] for f in audit_results),
            "schemas_missing": [],
            "read_errors": []
        }
    }
    
    # Agrupar por tipo
    for f in audit_results:
        t = f["artifact_type"]
        report["summary"]["by_type"][t] = report["summary"]["by_type"].get(t, 0) + 1
        s = f["state"]
        report["summary"]["by_state"][s] = report["summary"]["by_state"].get(s, 0) + 1
        
        if f["expected_schema"] is None and t not in ["audit_report", "correction_manifest", "test_results", "validation_report", "other_format", "binary_ok", "valid_python"]:
            report["summary"]["schemas_missing"].append(f["relative_path"])
        
        if "error" in f["state"] or "invalid" in f["state"]:
            report["summary"]["read_errors"].append({
                "path": f["relative_path"],
                "state": f["state"]
            })
    
    # Guardar informe
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print(f"Total archivos: {file_count}")
    print(f"Tamaño total: {report['summary']['total_size_bytes']:,} bytes")
    print("\nPor tipo:")
    for t, count in sorted(report["summary"]["by_type"].items()):
        print(f"  {t}: {count}")
    print("\nPor estado:")
    for s, count in sorted(report["summary"]["by_state"].items()):
        print(f"  {s}: {count}")
    print(f"\nInforme guardado en: {OUTPUT_FILE}")
    
    return report

if __name__ == "__main__":
    main()
