import json
import os
import stat

import pytest

import almacenamiento as alm
from modelos import AnalisisOpinion, ErrorAlmacenamiento, ErrorCatalogo, ErrorClasificacion

MESSI = {"id": "j001", "nombre": "Lionel Messi", "pais": "Argentina"}
DIAZ = {"id": "j013", "nombre": "Luis Díaz", "pais": "Colombia"}


def analisis(s="positivo"):
    return AnalisisOpinion(es_pertinente=True, sentimiento=s, razon="Razón de prueba.")


def registro(jugador=MESSI, texto="Su visión de juego es extraordinaria", s="positivo", **kw):
    return alm.crear_registro(jugador, texto, analisis(s), "modelo_prueba", **kw)


# ------------------------------------------------------------------ catálogo
def test_catalogo_real_tiene_20_jugadores_con_ids_unicos():
    jugadores = alm.cargar_jugadores(alm.BASE_DIR / "datos" / "jugadores.json")
    assert len(jugadores) >= 20
    assert len({j["id"] for j in jugadores}) == len(jugadores)
    assert all(j["id"] and j["nombre"] and j["pais"] for j in jugadores)


def test_catalogo_con_ids_repetidos_falla(tmp_path):
    ruta = tmp_path / "j.json"
    ruta.write_text(json.dumps({"version": 1, "jugadores": [
        {"id": "j001", "nombre": "A", "pais": "X"}, {"id": "j001", "nombre": "B", "pais": "Y"}]}))
    with pytest.raises(ErrorCatalogo, match="repetidos"):
        alm.cargar_jugadores(ruta)


def test_catalogo_inexistente_o_invalido_falla(tmp_path):
    with pytest.raises(ErrorCatalogo):
        alm.cargar_jugadores(tmp_path / "no_existe.json")
    mala = tmp_path / "mala.json"
    mala.write_text("{no es json")
    with pytest.raises(ErrorCatalogo):
        alm.cargar_jugadores(mala)


# ------------------------------------------------------------- opiniones.json
def test_si_no_existe_se_inicializa_vacio(tmp_path):
    ruta = tmp_path / "datos" / "opiniones.json"
    assert alm.cargar_opiniones(ruta) == {"version": 1, "opiniones": []}
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"version": 1, "opiniones": []}


@pytest.mark.parametrize("contenido", ["{esto no es json", "[]", '{"opiniones": "x"}', '{"version": 1}'])
def test_archivo_danado_da_error_y_se_conserva(tmp_path, contenido):
    ruta = tmp_path / "opiniones.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ErrorAlmacenamiento):
        alm.cargar_opiniones(ruta)
    with pytest.raises(ErrorAlmacenamiento):
        alm.guardar_opinion(ruta, registro())
    assert ruta.read_text(encoding="utf-8") == contenido  # NO se sustituyó por una lista vacía


def test_registro_con_sentimiento_invalido_no_se_acepta(tmp_path):
    ruta = tmp_path / "o.json"
    r = registro()
    r["sentimiento"] = "feliz"
    with pytest.raises(ErrorAlmacenamiento):
        alm.guardar_opinion(ruta, r)


def test_guardar_conserva_los_anteriores_y_persiste(tmp_path):
    ruta = tmp_path / "opiniones.json"
    assert alm.guardar_opinion(ruta, registro(texto="Primera opinión")) is True
    assert alm.guardar_opinion(ruta, registro(texto="Segunda opinión")) is True
    # «reinicio»: se vuelve a leer desde disco
    guardadas = alm.cargar_opiniones(ruta)["opiniones"]
    assert [r["opinion_original"] for r in guardadas] == ["Primera opinión", "Segunda opinión"]
    assert len({r["id"] for r in guardadas}) == 2  # dos registros independientes


def test_mismo_texto_enviado_dos_veces_son_dos_registros(tmp_path):
    ruta = tmp_path / "o.json"
    alm.guardar_opinion(ruta, registro(texto="Igual de buena"))
    alm.guardar_opinion(ruta, registro(texto="Igual de buena"))
    assert len(alm.cargar_opiniones(ruta)["opiniones"]) == 2


def test_mismo_id_no_se_duplica(tmp_path):
    ruta = tmp_path / "o.json"
    r = registro()
    assert alm.guardar_opinion(ruta, r) is True
    assert alm.guardar_opinion(ruta, r) is False  # reintento / reejecución
    assert len(alm.cargar_opiniones(ruta)["opiniones"]) == 1


def test_cada_registro_conserva_su_jugador(tmp_path):
    ruta = tmp_path / "o.json"
    alm.guardar_opinion(ruta, registro(MESSI, "Opinión de Messi"))
    alm.guardar_opinion(ruta, registro(DIAZ, "Opinión de Díaz"))
    ops = alm.cargar_opiniones(ruta)["opiniones"]
    assert [(r["jugador_id"], r["jugador_nombre"]) for r in ops] == [("j001", "Lionel Messi"), ("j013", "Luis Díaz")]


def test_formato_utf8_sin_escapes_e_indentado(tmp_path):
    ruta = tmp_path / "o.json"
    alm.guardar_opinion(ruta, registro(DIAZ, "Qué jugador, ¡me encanta! ñ"))
    texto = ruta.read_text(encoding="utf-8")
    assert "Luis Díaz" in texto and "¡me encanta! ñ" in texto and "\\u" not in texto
    assert '\n  "opiniones": [' in texto  # indentación de 2 espacios


def test_fallo_de_escritura_no_deja_rastro_ni_pierde_datos(tmp_path, monkeypatch):
    ruta = tmp_path / "o.json"
    alm.guardar_opinion(ruta, registro(texto="Ya guardada"))
    antes = ruta.read_text(encoding="utf-8")

    def falla(*a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", falla)
    with pytest.raises(ErrorAlmacenamiento, match="No se pudo escribir"):
        alm.guardar_opinion(ruta, registro(texto="Nueva"))
    monkeypatch.undo()
    assert ruta.read_text(encoding="utf-8") == antes  # archivo intacto
    assert [p.name for p in tmp_path.iterdir()] == ["o.json"]  # sin temporales huérfanos


def test_se_conservan_los_permisos_del_archivo(tmp_path):
    ruta = tmp_path / "o.json"
    alm.guardar_opinion(ruta, registro())
    os.chmod(ruta, 0o664)
    alm.guardar_opinion(ruta, registro(texto="Otra distinta"))
    assert stat.S_IMODE(ruta.stat().st_mode) == 0o664


def test_crear_registro_trae_uuid_fecha_y_metadatos():
    r = registro()
    assert set(r) == set(alm.CAMPOS_REGISTRO)
    assert len(r["id"]) == 36 and r["fecha_utc"].endswith("+00:00")
    assert (r["modelo"], r["version_prompt"], r["jugador_id"]) == ("modelo_prueba", "1.0", "j001")


def test_crear_registro_usa_el_id_recibido_y_rechaza_no_pertinentes():
    assert registro(registro_id="abc-123")["id"] == "abc-123"
    with pytest.raises(ErrorClasificacion):
        alm.crear_registro(MESSI, "x" * 10, AnalisisOpinion(es_pertinente=False, sentimiento=None, razon="no"), "m")


# ------------------------------------------------------------------- consulta
def test_consultar_filtra_cuenta_y_ordena():
    regs = [
        {**registro(MESSI, "a", "positivo"), "fecha_utc": "2026-11-05T10:00:00+00:00"},
        {**registro(MESSI, "b", "negativo"), "fecha_utc": "2026-11-05T12:00:00+00:00"},
        {**registro(DIAZ, "c", "positivo"), "fecha_utc": "2026-11-05T11:00:00.500000+00:00"},
    ]
    assert len(alm.consultar_opiniones(regs)) == 3
    assert [r["opinion_original"] for r in alm.consultar_opiniones(regs)] == ["b", "c", "a"]  # recientes primero
    assert len(alm.consultar_opiniones(regs, jugador_id="j001")) == 2
    assert len(alm.consultar_opiniones(regs, sentimiento="positivo")) == 2
    assert len(alm.consultar_opiniones(regs, "j013", "positivo")) == 1
    assert alm.consultar_opiniones(regs, "j013", "mixto") == []
    assert alm.contar_por_sentimiento(regs) == {"positivo": 2, "negativo": 1, "neutro": 0, "mixto": 0}
    assert alm.contar_por_sentimiento([]) == {"positivo": 0, "negativo": 0, "neutro": 0, "mixto": 0}


def test_el_archivo_demo_cumple_los_entregables():
    demo = alm._validar_estructura(alm._leer_json(alm.BASE_DIR / "ejemplos" / "opiniones_demo.json"))["opiniones"]
    assert len(demo) >= 12
    assert len({r["jugador_id"] for r in demo}) >= 4
    assert {r["sentimiento"] for r in demo} == set(alm.SENTIMIENTOS)
