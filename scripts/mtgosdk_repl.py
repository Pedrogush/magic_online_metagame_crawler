"""Inspect pythonnet coreclr bootstrap state."""
from __future__ import annotations

from pathlib import Path

try:
    import pythonnet
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("pythonnet is not installed in this environment.") from exc

pythonnet.load("coreclr")

import clr  # type: ignore
from System import AppDomain  # type: ignore


def _candidate_dirs() -> list[Path]:
    dotnet_root = Path(r"C:\Program Files\dotnet")
    reference_root = Path(r"C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework")
    dirs: list[Path] = []

    windows_desktop = dotnet_root / "shared" / "Microsoft.WindowsDesktop.App"
    for version in ("9.0.10", "9.0.2", "8.0.13", "6.0.36"):
        candidate = windows_desktop / version
        if candidate.exists():
            dirs.append(candidate)

    netcore_app = dotnet_root / "shared" / "Microsoft.NETCore.App"
    if netcore_app.exists():
        for version in ("9.0.10", "9.0.2", "8.0.13", "6.0.36"):
            candidate = netcore_app / version
            if candidate.exists():
                dirs.append(candidate)

    for version in ("v4.8.1", "v4.8", "v4.7.2", "v4.7.1", "v4.6.2", "v4.6"):
        netfx = reference_root / version
        if netfx.exists():
            dirs.append(netfx)
            facades = netfx / "Facades"
            if facades.exists():
                dirs.append(facades)

    return dirs


def _add_reference(name: str, candidate_dirs: list[Path]) -> None:
    for directory in candidate_dirs:
        dll = directory / f"{name}.dll"
        if dll.exists():
            clr.AddReference(str(dll))
            return
    clr.AddReference(name)


_shared_dirs = _candidate_dirs()
for _assembly in ("WindowsBase", "PresentationCore", "PresentationFramework", "System.Xaml"):
    _add_reference(_assembly, _shared_dirs)

_publish_dir = Path(r"C:\Users\Pedro\Documents\GitHub\magic_online_metagame_crawler\dotnet\MTGOBridge\bin\Release\net9.0-windows7.0\win-x64\publish")
for _dll in ("MTGOSDK.Win32.dll", "MTGOSDK.dll"):
    _path = _publish_dir / _dll
    if not _path.exists():
        raise SystemExit(f"Missing expected bridge assembly: {_path}")
    clr.AddReference(str(_path))

del _assembly, _dll, _path, _publish_dir, _shared_dirs

import MTGOSDK  # type: ignore

print("MTGOSDK loaded; call list_mtgosdk_namespaces() or list_methods_by_type() for inspection.")


def explain_namespace_visibility() -> str:
    """Explain why dir(MTGOSDK) omits the 'API' module."""
    assembly = _get_mtgosdk_assembly()
    namespaces = sorted(
        {
            dtype.Namespace
            for dtype in assembly.GetTypes()
            if dtype.Namespace and dtype.Namespace.startswith("MTGOSDK.")
        }
    )
    return (
        "pythonnet surfaces .NET namespaces lazily. Attributes such as 'API' are created on-demand "
        "when you first access them (e.g., 'import MTGOSDK.API'), so they do not appear in dir(MTGOSDK) "
        "until they are accessed. "
        f"Namespaces exported by MTGOSDK: {namespaces}"
    )


def list_mtgosdk_namespaces() -> list[str]:
    """Return sorted MTGOSDK namespace names discovered from the loaded assembly."""
    assembly = _get_mtgosdk_assembly()
    return sorted(
        {
            dtype.Namespace
            for dtype in assembly.GetTypes()
            if dtype.Namespace and dtype.Namespace.startswith("MTGOSDK.")
        }
    )


def _get_mtgosdk_assembly():
    for assembly in AppDomain.CurrentDomain.GetAssemblies():
        if assembly.GetName().Name == "MTGOSDK":
            return assembly
    raise RuntimeError("MTGOSDK assembly is not loaded.")


def list_methods_by_type(include_inherited: bool = False) -> None:
    """Print every public method for each MTGOSDK type."""
    from System.Reflection import BindingFlags  # type: ignore

    def _format_type(dtype) -> str:
        name = dtype.FullName or dtype.Name
        if dtype.IsGenericType:
            generic_args = ", ".join(_format_type(arg) for arg in dtype.GetGenericArguments())
            base = dtype.GetGenericTypeDefinition().FullName or dtype.GetGenericTypeDefinition().Name
            base = base.split("`", 1)[0]
            return f"{base}<{generic_args}>"
        return name

    def _format_parameter(param) -> str:
        prefix = []
        if param.IsOut:
            prefix.append("out")
        elif param.ParameterType.IsByRef:
            prefix.append("ref")
        if param.IsOptional:
            prefix.append("[optional]")
        type_name = _format_type(param.ParameterType.GetElementType() if param.ParameterType.IsByRef else param.ParameterType)
        prefix.append(type_name)
        prefix.append(param.Name or "_")
        return " ".join(prefix)

    flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public
    if not include_inherited:
        flags |= BindingFlags.DeclaredOnly

    assembly = _get_mtgosdk_assembly()
    for typ in assembly.GetTypes():
        if not typ.Namespace or not typ.Namespace.startswith("MTGOSDK."):
            continue
        methods = typ.GetMethods(flags)
        if not methods:
            continue
        print(f"{typ.FullName}:")
        for method in methods:
            parameters = ", ".join(_format_parameter(param) for param in method.GetParameters())
            return_type = _format_type(method.ReturnType) if method.ReturnType else "void"
            print(f"  - {method.Name}({parameters}) -> {return_type}")
