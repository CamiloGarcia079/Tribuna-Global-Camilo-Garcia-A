"""Documenta las versiones REALES instaladas en tu entorno (requisito del taller).

    python versiones.py          # imprime y escribe requirements-lock.txt
"""
import importlib.metadata as md
import platform
from pathlib import Path

PAQUETES = [
    "streamlit", "langchain", "langchain-core", "langchain-openai", "langchain-google-genai",
    "openai", "google-genai", "pydantic", "python-dotenv", "pandas", "pytest",
]


def main() -> None:
    lineas = [f"# Python {platform.python_version()} en {platform.system()}"]
    for p in PAQUETES:
        try:
            lineas.append(f"{p}=={md.version(p)}")
        except md.PackageNotFoundError:
            lineas.append(f"# {p}: no instalado")
    texto = "\n".join(lineas) + "\n"
    print(texto)
    (Path(__file__).resolve().parent / "requirements-lock.txt").write_text(texto, encoding="utf-8")
    print("Escrito: requirements-lock.txt")


if __name__ == "__main__":
    main()
