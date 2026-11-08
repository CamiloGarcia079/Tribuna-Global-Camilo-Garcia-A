"""Carga las opiniones FICTICIAS de ejemplos/opiniones_demo.json en datos/opiniones.json.

Uso (desde la carpeta tribuna_global):
    python cargar_demo.py             # añade los ejemplos que falten (no duplica)
    python cargar_demo.py --vaciar    # deja opiniones.json vacío (estructura inicial)
    python cargar_demo.py --reemplazar  # opiniones.json = solo los ejemplos

Los registros de ejemplo llevan modelo = "ejemplo_manual_sin_IA": no los generó
ningún modelo; sirven para probar la consulta, los filtros y la descarga.
"""
import argparse
from pathlib import Path

import almacenamiento as alm
from modelos import ErrorAlmacenamiento

RUTA_DEMO = Path(__file__).resolve().parent / "ejemplos" / "opiniones_demo.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--vaciar", action="store_true", help="deja opiniones.json sin registros")
    grupo.add_argument("--reemplazar", action="store_true", help="sustituye todo por los ejemplos")
    args = ap.parse_args()

    try:
        if args.vaciar:
            alm._escribir_atomico(alm.RUTA_OPINIONES, alm.estructura_vacia())
            print(f"opiniones.json vaciado: {alm.RUTA_OPINIONES}")
            return 0

        demo = alm._validar_estructura(alm._leer_json(RUTA_DEMO))["opiniones"]
        if args.reemplazar:
            alm._escribir_atomico(alm.RUTA_OPINIONES, {"version": alm.VERSION_ESQUEMA, "opiniones": demo})
            print(f"opiniones.json reemplazado por {len(demo)} ejemplos.")
            return 0

        nuevos = sum(1 for r in demo if alm.guardar_opinion(alm.RUTA_OPINIONES, r))
        total = len(alm.cargar_opiniones(alm.RUTA_OPINIONES)["opiniones"])
        print(f"Ejemplos añadidos: {nuevos} (ya existían: {len(demo) - nuevos}). Total en el archivo: {total}.")
        return 0
    except ErrorAlmacenamiento as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
