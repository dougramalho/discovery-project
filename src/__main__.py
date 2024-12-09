import os
import json
from pathlib import Path
import re

class ProjectDiscovery:
    def __init__(self):
        self.structure = {}

    def _parse_method_params(self, param_str):
        params = {}
        if not param_str.strip():
            return params
            
        for param in param_str.split(','):
            parts = param.strip().split()
            if len(parts) >= 2:
                params[parts[-1]] = parts[-2]
        return params

    def _parse_cs_file(self, file_path):
        result = {}
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    content = file.read()
                    
                    param_types = {}
                    param_matches = re.finditer(r'(?:public|private|protected)\s+(?:static\s+)?(?:async\s+)?(?:override\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\((.*?)\)', content)
                    for param_match in param_matches:
                        method_name = param_match.group(1)
                        param_types[method_name] = self._parse_method_params(param_match.group(2))
                    
                    classes = re.finditer(r'public\s+class\s+(\w+)', content)
                    for class_match in classes:
                        class_name = class_match.group(1)
                        result[class_name] = {"type": "class", "members": {}}
                        
                        class_start = class_match.end()
                        next_class = re.search(r'public\s+class\s+\w+', content[class_start:])
                        class_end = class_start + next_class.start() if next_class else len(content)
                        class_content = content[class_start:class_end]
                        
                        properties = re.finditer(r'public\s+(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*{\s*get\s*;', class_content)
                        for prop in properties:
                            prop_name = prop.group(1)
                            result[class_name]["members"][prop_name] = {"type": "property"}
                        
                        # Encontrar assinaturas dos métodos
                        method_signatures = re.finditer(r'(?:public|private|protected)\s+(?:static\s+)?(?:async\s+)?(?:override\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(', class_content)
                        
                        for method_sig in method_signatures:
                            method_name = method_sig.group(1)
                            method_start = method_sig.start()
                            
                            # Encontrar o fim do método contando chaves
                            open_braces = 0
                            found_first_brace = False
                            method_end = method_start
                            
                            for i in range(method_start, len(class_content)):
                                if class_content[i] == '{':
                                    open_braces += 1
                                    found_first_brace = True
                                elif class_content[i] == '}':
                                    open_braces -= 1
                                    if found_first_brace and open_braces == 0:
                                        method_end = i + 1
                                        break
                            
                            if method_end > method_start:
                                method_text = class_content[method_start:method_end].strip()
                                method_info = {
                                    "type": "method",
                                    "raw": method_text
                                }
                                
                                dependencies = []
                                
                                service_calls = re.finditer(r'_(\w+)\.(\w+)\(', method_text)
                                for call in service_calls:
                                    service_name = 'I' + call.group(1)[0].upper() + call.group(1)[1:]
                                    method_called = call.group(2)
                                    dependencies.append({
                                        "type": service_name,
                                        "method": method_called
                                    })
                                
                                class_calls = re.finditer(r'(\w+)\.(\w+)\(', method_text)
                                for call in class_calls:
                                    var_name = call.group(1)
                                    method_called = call.group(2)
                                    
                                    var_type = param_types.get(method_name, {}).get(var_name, var_name)
                                    
                                    if not var_name.startswith('_'):
                                        dependencies.append({
                                            "type": var_type,
                                            "method": method_called
                                        })
                                
                                if dependencies:
                                    method_info["dependencies"] = dependencies
                                
                                result[class_name]["members"][method_name] = method_info
                    
                    return result
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Erro ao processar arquivo {file_path}: {str(e)}")
                return result
                
        print(f"Não foi possível ler o arquivo {file_path} com nenhum dos encodings disponíveis")
        return result

    def discover(self, root_path):
        if not os.path.exists(root_path):
            raise ValueError("Caminho não encontrado")

        def process_directory(current_path):
            result = {}
            
            for item in os.listdir(current_path):
                full_path = os.path.join(current_path, item)
                
                if os.path.isfile(full_path):
                    if item.endswith('.cs'):
                        file_name = os.path.splitext(item)[0]
                        parsed_content = self._parse_cs_file(full_path)
                        if parsed_content:
                            result[file_name] = parsed_content
                
                elif os.path.isdir(full_path):
                    if item not in ['bin', 'obj'] and not item.startswith('.'):
                        sub_dir = process_directory(full_path)
                        if sub_dir:
                            result[item] = sub_dir
            
            return result

        self.structure = process_directory(root_path)
        return self.structure

def main():
    project_path = input("Digite o caminho da pasta raiz do projeto: ").strip()
    
    try:
        discovery = ProjectDiscovery()
        result = discovery.discover(project_path)
        
        output_path = os.path.join(os.path.dirname(__file__), 'project_structure.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=3, ensure_ascii=False)
            
        print(f"Arquivo JSON gerado com sucesso em: {output_path}")
        
    except Exception as e:
        print(f"Erro: {str(e)}")

if __name__ == "__main__":
    main()