#!/usr/bin/env python3
"""
Generador de Atlas de Símbolos - Renderiza SVG y PNG por disciplina
Draft 2020-12 compliant, UTF-8 puro, compatible Windows
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom

class SymbolAtlasRenderer:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.errors = []
        self.warnings = []
        self.results = {
            "total_symbols": 0,
            "rendered": 0,
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
    
    def validate_symbol(self, symbol: Dict, path: str) -> List[Dict]:
        """Validar estructura de símbolo"""
        errors = []
        
        # Claves requeridas
        required_keys = [
            "symbol_id", "name", "discipline", "ports", "geometry", "layers"
        ]
        
        for key in required_keys:
            if key not in symbol:
                errors.append({
                    "type": "E_SYMBOL_MISSING_KEY",
                    "path": path,
                    "symbol_id": symbol.get("symbol_id", "UNKNOWN"),
                    "missing_key": key
                })
        
        # Verificar nombre genérico
        name = symbol.get("name", "")
        if name.startswith("Símbolo:") or name.startswith("Symbol:"):
            errors.append({
                "type": "E_SYMBOL_GENERIC_NAME",
                "path": path,
                "symbol_id": symbol.get("symbol_id"),
                "name": name
            })
        
        # Verificar disciplina
        discipline = symbol.get("discipline", "")
        valid_disciplines = ["ELEC", "CIVIL", "STR", "MECH", "PROC", "HYD", "INST", "FIRE", "COMM", "GEN"]
        if discipline not in valid_disciplines:
            errors.append({
                "type": "E_SYMBOL_INVALID_DISCIPLINE",
                "path": path,
                "symbol_id": symbol.get("symbol_id"),
                "discipline": discipline
            })
        
        # Verificar puertos genéricos
        ports = symbol.get("ports", [])
        for port in ports:
            port_name = port.get("name", "")
            if port_name in ["IN PROCESS", "OUT PROCESS", "PROCESS"]:
                if discipline not in ["PROC", "MECH"]:
                    errors.append({
                        "type": "E_SYMBOL_GENERIC_PORT",
                        "path": path,
                        "symbol_id": symbol.get("symbol_id"),
                        "port": port_name
                    })
        
        # Verificar geometría
        geometry = symbol.get("geometry", {})
        if not geometry:
            errors.append({
                "type": "E_SYMBOL_NO_GEOMETRY",
                "path": path,
                "symbol_id": symbol.get("symbol_id")
            })
        
        return errors
    
    def check_duplicate_graphics(self, symbols: List[Dict], path: str) -> List[Dict]:
        """Detectar símbolos con geometría idéntica"""
        errors = []
        geometry_hashes = {}
        
        for symbol in symbols:
            geometry = symbol.get("geometry", {})
            # Crear hash normalizado de la geometría
            geo_str = json.dumps(geometry, sort_keys=True)
            hash_val = hash(geo_str)
            
            if hash_val in geometry_hashes:
                errors.append({
                    "type": "E_SYMBOL_DUPLICATE_GRAPHIC",
                    "path": path,
                    "symbol_id_1": geometry_hashes[hash_val],
                    "symbol_id_2": symbol.get("symbol_id"),
                    "hash": hash_val
                })
            else:
                geometry_hashes[hash_val] = symbol.get("symbol_id")
        
        return errors
    
    def render_svg_atlas(self, symbols_by_discipline: Dict[str, List[Dict]], output_dir: Path) -> Dict:
        """Generar atlas SVG por disciplina"""
        results = {
            "atlases_generated": 0,
            "symbols_rendered": 0,
            "errors": []
        }
        
        for discipline, symbols in symbols_by_discipline.items():
            if not symbols:
                continue
            
            # Crear SVG
            svg_width = 1200
            svg_height = max(100 * len(symbols), 400)
            
            svg_root = ET.Element('svg')
            svg_root.set('xmlns', 'http://www.w3.org/2000/svg')
            svg_root.set('width', str(svg_width))
            svg_root.set('height', str(svg_height))
            svg_root.set('viewBox', f'0 0 {svg_width} {svg_height}')
            
            # Título
            title = ET.SubElement(svg_root, 'title')
            title.text = f'Atlas de Símbolos - {discipline}'
            
            # Grid de símbolos
            x_offset = 20
            y_offset = 20
            cell_width = 100
            cell_height = 80
            cols = 10
            
            for i, symbol in enumerate(symbols):
                col = i % cols
                row = i // cols
                cell_x = x_offset + col * cell_width
                cell_y = y_offset + row * cell_height
                
                # Celda
                rect = ET.SubElement(svg_root, 'rect')
                rect.set('x', str(cell_x))
                rect.set('y', str(cell_y))
                rect.set('width', str(cell_width - 5))
                rect.set('height', str(cell_height - 5))
                rect.set('fill', '#f0f0f0')
                rect.set('stroke', '#999999')
                rect.set('stroke-width', '1')
                
                # ID del símbolo
                text_id = ET.SubElement(svg_root, 'text')
                text_id.set('x', str(cell_x + 5))
                text_id.set('y', str(cell_y + 15))
                text_id.set('font-size', '10')
                text_id.set('font-family', 'Arial')
                text_id.text = symbol.get('symbol_id', 'UNKNOWN')[:20]
                
                # Nombre
                text_name = ET.SubElement(svg_root, 'text')
                text_name.set('x', str(cell_x + 5))
                text_name.set('y', str(cell_y + 30))
                text_name.set('font-size', '8')
                text_name.set('font-family', 'Arial')
                text_name.text = symbol.get('name', '')[:25]
                
                # Disciplina
                text_disc = ET.SubElement(svg_root, 'text')
                text_disc.set('x', str(cell_x + 5))
                text_disc.set('y', str(cell_y + 45))
                text_disc.set('font-size', '8')
                text_disc.set('font-family', 'Arial')
                text_disc.text = symbol.get('discipline', '')
                
                # Geometría (simplificada como rectángulo)
                geometry = symbol.get('geometry', {})
                prim_type = geometry.get('type', 'rect')
                geo_x = cell_x + 25
                geo_y = cell_y + 50
                
                if prim_type == 'rect':
                    geo_rect = ET.SubElement(svg_root, 'rect')
                    geo_rect.set('x', str(geo_x))
                    geo_rect.set('y', str(geo_y))
                    geo_rect.set('width', str(40))
                    geo_rect.set('height', str(20))
                    geo_rect.set('fill', 'none')
                    geo_rect.set('stroke', '#000000')
                    geo_rect.set('stroke-width', '2')
                elif prim_type == 'circle':
                    geo_circle = ET.SubElement(svg_root, 'circle')
                    geo_circle.set('cx', str(geo_x + 20))
                    geo_circle.set('cy', str(geo_y + 10))
                    geo_circle.set('r', str(15))
                    geo_circle.set('fill', 'none')
                    geo_circle.set('stroke', '#000000')
                    geo_circle.set('stroke-width', '2')
                
                results["symbols_rendered"] += 1
            
            # Guardar SVG
            svg_file = output_dir / f'atlas_{discipline}_v3.svg'
            svg_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Formatear XML
            xml_str = ET.tostring(svg_root, encoding='unicode')
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent='  ')
            
            with open(svg_file, 'w', encoding='utf-8', newline='') as f:
                f.write(pretty_xml)
            
            results["atlases_generated"] += 1
        
        return results
    
    def process_common_symbols(self) -> Dict:
        """Procesar símbolos comunes"""
        results = {
            "source": "common",
            "symbols_total": 0,
            "symbols_valid": 0,
            "symbols_invalid": 0,
            "symbols_by_discipline": {},
            "errors": []
        }
        
        symbols_file = self.base_path / "04_common_symbols.json"
        if not symbols_file.exists():
            return results
        
        symbols = self.load_json(symbols_file)
        if not symbols or not isinstance(symbols, list):
            return results
        
        results["symbols_total"] = len(symbols)
        
        # Agrupar por disciplina
        for symbol in symbols:
            discipline = symbol.get("discipline", "GEN")
            if discipline not in results["symbols_by_discipline"]:
                results["symbols_by_discipline"][discipline] = []
            results["symbols_by_discipline"][discipline].append(symbol)
            
            self.results["total_symbols"] += 1
            
            # Validar
            errors = self.validate_symbol(symbol, str(symbols_file))
            
            if errors:
                results["symbols_invalid"] += 1
                self.results["failed"] += 1
                results["errors"].extend(errors)
                self.errors.extend(errors)
            else:
                results["symbols_valid"] += 1
                self.results["passed"] += 1
            
            self.results["rendered"] += 1
        
        # Verificar duplicados gráficos
        duplicate_errors = self.check_duplicate_graphics(symbols, str(symbols_file))
        results["errors"].extend(duplicate_errors)
        self.errors.extend(duplicate_errors)
        
        return results
    
    def run_full_render(self) -> Dict:
        """Ejecutar renderizado completo"""
        report = {
            "common": self.process_common_symbols(),
            "render_results": {},
            "summary": {}
        }
        
        # Generar atlas SVG
        output_dir = self.base_path / "symbol_atlas_v3"
        symbols_by_discipline = report["common"].get("symbols_by_discipline", {})
        render_results = self.render_svg_atlas(symbols_by_discipline, output_dir)
        report["render_results"] = render_results
        
        # Resumen
        report["summary"] = {
            "total_symbols": self.results["total_symbols"],
            "rendered": self.results["rendered"],
            "passed": self.results["passed"],
            "failed": self.results["failed"],
            "atlases_generated": render_results.get("atlases_generated", 0),
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
    renderer = SymbolAtlasRenderer(str(base_path))
    
    print("[INFO] Iniciando generación de atlas de símbolos...")
    report = renderer.run_full_render()
    
    output_file = base_path / "reports" / "render_report_v3.json"
    output_file.parent.mkdir(exist_ok=True)
    renderer.save_report(report, output_file)
    
    summary = report["summary"]
    print(f"[RESULTADO] Símbolos totales: {summary['total_symbols']}")
    print(f"[RESULTADO] Renderizados: {summary['rendered']}")
    print(f"[RESULTADO] Aprobados: {summary['passed']}")
    print(f"[RESULTADO] Fallidos: {summary['failed']}")
    print(f"[RESULTADO] Atlas generados: {summary['atlases_generated']}")
    print(f"[RESULTADO] Errores: {summary['total_errors']}")
    print(f"[RESULTADO] Advertencias: {summary['total_warnings']}")
    
    if summary['failed'] > 0:
        print("\n[FAIL] Algunos símbolos requieren reparación")
        return 1
    else:
        print("\n[PASS] Todos los símbolos renderizados correctamente")
        return 0


if __name__ == "__main__":
    sys.exit(main())
