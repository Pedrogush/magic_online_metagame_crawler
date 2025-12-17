#!/usr/bin/env python3
import ast
from collections import defaultdict
from pathlib import Path


class ArchitectureAnalyzer(ast.NodeVisitor):
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.classes = []
        self.imports = []

    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)


def analyze_directory(directory: Path) -> dict[str, dict]:
    modules = {}
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file) or "test" in str(py_file):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                tree = ast.parse(f.read())

            rel_path = py_file.relative_to(directory.parent)
            module_name = str(rel_path).replace("/", ".").replace(".py", "")

            analyzer = ArchitectureAnalyzer(module_name)
            analyzer.visit(tree)

            modules[module_name] = {
                "classes": analyzer.classes,
                "imports": analyzer.imports,
                "path": str(rel_path),
            }
        except Exception:
            pass

    return modules


def categorize_modules(modules: dict) -> dict[str, list[str]]:
    categories = {
        "Controllers": [],
        "Services": [],
        "Repositories": [],
        "UI": [],
        "Utils": [],
        "Navigators": [],
    }

    for module_name in modules.keys():
        if "controller" in module_name:
            categories["Controllers"].append(module_name)
        elif "service" in module_name:
            categories["Services"].append(module_name)
        elif "repositor" in module_name:
            categories["Repositories"].append(module_name)
        elif "widget" in module_name or "frame" in module_name or "panel" in module_name:
            categories["UI"].append(module_name)
        elif "navigator" in module_name:
            categories["Navigators"].append(module_name)
        elif "utils" in module_name or "util" in module_name:
            categories["Utils"].append(module_name)

    return {k: v for k, v in categories.items() if v}


def find_dependencies(modules: dict) -> dict[str, set[str]]:
    deps = defaultdict(set)
    for module_name, module_info in modules.items():
        for imp in module_info["imports"]:
            for other_module in modules.keys():
                if other_module != module_name and other_module in imp:
                    deps[module_name].add(other_module)
    return deps


def generate_mermaid(categories: dict, dependencies: dict, modules: dict) -> str:
    lines = ["graph TB"]

    for category, module_list in categories.items():
        lines.append(f"\n    subgraph {category}")
        for module in sorted(module_list)[:8]:
            module_id = module.replace(".", "_")
            classes = modules.get(module, {}).get("classes", [])
            class_str = "<br/>".join(classes[:3])
            if len(classes) > 3:
                class_str += f"<br/>+{len(classes)-3} more"
            label = module.split(".")[-1]
            if class_str:
                lines.append(f'        {module_id}["{label}<br/>{class_str}"]')
            else:
                lines.append(f'        {module_id}["{label}"]')
        lines.append("    end")

    lines.append("\n    %% Dependencies")
    seen = set()
    for module, deps in sorted(dependencies.items())[:50]:
        module_id = module.replace(".", "_")
        for dep in sorted(deps)[:3]:
            dep_id = dep.replace(".", "_")
            edge = (module_id, dep_id)
            if edge not in seen:
                lines.append(f"    {module_id} --> {dep_id}")
                seen.add(edge)

    lines.append("\n    %% Styling")
    lines.append("    classDef controller fill:#ff9999,stroke:#333,stroke-width:2px")
    lines.append("    classDef service fill:#99ccff,stroke:#333,stroke-width:2px")
    lines.append("    classDef repo fill:#99ff99,stroke:#333,stroke-width:2px")
    lines.append("    classDef ui fill:#ffcc99,stroke:#333,stroke-width:2px")
    lines.append("    classDef util fill:#cc99ff,stroke:#333,stroke-width:2px")
    lines.append("    classDef nav fill:#ffff99,stroke:#333,stroke-width:2px")

    for module in categories.get("Controllers", []):
        lines.append(f"    class {module.replace('.', '_')} controller")
    for module in categories.get("Services", []):
        lines.append(f"    class {module.replace('.', '_')} service")
    for module in categories.get("Repositories", []):
        lines.append(f"    class {module.replace('.', '_')} repo")
    for module in categories.get("UI", []):
        lines.append(f"    class {module.replace('.', '_')} ui")
    for module in categories.get("Utils", []):
        lines.append(f"    class {module.replace('.', '_')} util")
    for module in categories.get("Navigators", []):
        lines.append(f"    class {module.replace('.', '_')} nav")

    return "\n".join(lines)


def main():
    root = Path(__file__).parent.parent
    output_dir = root / "docs" / "diagrams"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Analyzing codebase structure...")
    modules = analyze_directory(root)
    print(f"Found {len(modules)} modules")

    print("Categorizing modules...")
    categories = categorize_modules(modules)
    for category, module_list in categories.items():
        print(f"  {category}: {len(module_list)} modules")

    print("Analyzing dependencies...")
    dependencies = find_dependencies(modules)

    print("Generating Mermaid diagram...")
    mermaid = generate_mermaid(categories, dependencies, modules)

    output_file = output_dir / "architecture.mmd"
    with open(output_file, "w") as f:
        f.write(mermaid)

    print(f"✓ Architecture diagram generated: {output_file}")
    print("\nTo view: paste contents into https://mermaid.live/")


if __name__ == "__main__":
    main()
