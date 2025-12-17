#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent.parent
    output_dir = root / "docs" / "diagrams"
    output_dir.mkdir(parents=True, exist_ok=True)

    modules = ["controllers", "services", "repositories", "widgets", "navigators", "utils"]

    print("Generating dependency diagrams with pydeps...")
    print(f"Output directory: {output_dir}")

    for module in modules:
        module_path = root / module
        if not module_path.exists():
            print(f"Skipping {module} (directory not found)")
            continue

        output_file = output_dir / f"{module}_dependencies.svg"
        print(f"\nGenerating {module} dependencies...")

        try:
            subprocess.run(
                ["pydeps", str(module), "--max-bacon=2", "-o", str(output_file), "--noshow"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"✓ Created {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to generate {module}: {e.stderr}")
        except FileNotFoundError:
            print("✗ pydeps not found. Install with: pip install pydeps")
            print("  Also requires Graphviz: https://graphviz.org/download/")
            sys.exit(1)

    print("\nGenerating full application dependency graph...")
    output_file = output_dir / "full_dependencies.svg"
    try:
        subprocess.run(
            [
                "pydeps",
                ".",
                "--max-bacon=3",
                "-o",
                str(output_file),
                "--noshow",
                "--exclude",
                "tests",
                "vendor",
                "dotnet",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ Created {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to generate full graph: {e.stderr}")

    print(f"\n✓ Dependency diagrams generated in {output_dir}")


if __name__ == "__main__":
    main()
