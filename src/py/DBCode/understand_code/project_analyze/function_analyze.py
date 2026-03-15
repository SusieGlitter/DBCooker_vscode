# -*- coding: utf-8 -*-
# @Project: DBCode
# @Module: function_analyze
# @Author: Anonymous
# @Time: 2025/8/30 2:55


import understand
import sys

from code_utils.sampleWithoutDep import project_dir
from understand_code.model import UnderstandRepo


class UnderstandFunctionExtractor:
    def __init__(self, udb_path):
        self.db = understand.open(udb_path)
        self.language = self._detect_language()

    def _detect_language(self):
        """Detect the main programming language of the project"""
        # Simple language detection logic
        ents = self.db.ents("file")
        ext_count = {}
        for file in ents:
            ext = file.longname().split('.')[-1].lower()
            ext_count[ext] = ext_count.get(ext, 0) + 1

        # Determine language based on file extensions
        ext_mapping = {
            'c': 'C', 'h': 'C',
            'cpp': 'C++', 'cc': 'C++', 'cxx': 'C++', 'hpp': 'C++', 'hh': 'C++',
            'java': 'Java',
            'py': 'Python',
            'cs': 'C#',
            'js': 'JavaScript', 'ts': 'TypeScript'
        }

        for ext, count in sorted(ext_count.items(), key=lambda x: x[1], reverse=True):
            if ext in ext_mapping:
                return ext_mapping[ext]

        return "Unknown"

    def get_all_functions(self):
        """Get all function declarations"""
        functions = []

        # Select appropriate entity type based on language
        if self.language == "Python":
            entity_types = "function,method"
        else:
            entity_types = "function,method,procedure"

        for func in self.db.ents(entity_types):
            func_info = self._get_function_info(func)
            if func_info:
                functions.append(func_info)

        return functions

    def _get_function_info(self, func_entity):
        """Get detailed information for a single function"""
        try:
            info = {
                "name": func_entity.name(),
                "kind": func_entity.kind().name(),
                "return_type": func_entity.type() or "void",
                "parameters": self._get_parameters(func_entity),
                "file": func_entity.parent().longname() if func_entity.parent() else "Unknown",
                "line": self._get_line_number(func_entity),
                "declaration": self._build_declaration(func_entity)
            }
            return info

        except Exception as e:
            print(f"Error processing {func_entity.name()}: {e}")
            return None

    def _get_parameters(self, func_entity):
        """Get function parameters"""
        parameters = []

        # Find parameter entities
        for ref in func_entity.refs("Define", "Parameter"):
            param_ent = ref.ent()
            if param_ent and "parameter" in param_ent.kind().name().lower():
                param_info = {
                    "name": param_ent.name(),
                    "type": param_ent.type() or "unknown",
                    "position": len(parameters) + 1
                }
                parameters.append(param_info)

        return parameters

    def _get_line_number(self, entity):
        """Get line number where entity is located"""
        for ref in entity.refs("Definein"):
            return ref.line()
        return 0

    def _build_declaration(self, func_entity):
        """Build function declaration string"""
        name = func_entity.name()
        return_type = func_entity.type() or "void"
        parameters = self._get_parameters(func_entity)

        # Build parameter string
        params_str = ", ".join([
            f"{param['type']} {param['name']}" for param in parameters
        ])

        # Build declaration based on language
        if self.language == "Python":
            return f"def {name}({params_str}):"
        else:
            return f"{return_type} {name}({params_str});"

    def close(self):
        """Close database connection"""
        self.db.close()


# Usage example
def main():
    try:
        # 添加 Understand API 路径
        # sys.path.append("C:/Program Files/SciTools/bin/pc-win64/python")

        lang = "C++"
        project_dir = "/data/user/code/postgres"
        project = UnderstandRepo(lang, project_dir)
        if not project.if_exists():
            project.create_udb()
        project.get_db()

        # Usage example
        udb_path = "path/to/your/project.udb"
        extractor = UnderstandFunctionExtractor(udb_path)

        functions = extractor.get_all_functions()

        # 输出函数声明
        for func in functions[:10]:  # 显示前10个
            print(f"File: {func['file']}:{func['line']}")
            print(f"Declaration: {func['declaration']}")
            print(f"Return type: {func['return_type']}")
            print(f"Parameters: {len(func['parameters'])}")
            print("-" * 50)

        extractor.close()

    except understand.UnderstandError as e:
        print(f"Understand Error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

