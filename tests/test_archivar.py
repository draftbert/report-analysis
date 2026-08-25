"""`archivar`: zip de evidencia con manifest.json y sha256 verificables."""
from __future__ import annotations

import hashlib
import json
import zipfile

from audit_agent.acciones import accion_archivar, estado_expediente, verificar_archivo


def test_archivar_contenido_y_hashes(expediente_tmp):
    exp = expediente_tmp
    exp.archivo("observaciones").write_text("# obs\n", encoding="utf-8")
    exp.escribir("informe", "# informe v1\n", "redactar")
    exp.escribir("informe", "# informe v2\n", "corregir")  # deja snapshot en historial/
    exp.trazar("extraer", {"system": "s", "user": "u", "respuesta": {"x": 1}})
    (exp.ruta / "salidas" / "ResumenEjecutivo_EXP-TEST.pptx").write_bytes(b"PK-falso")
    (exp.ruta / "EXP-TEST_archivo_viejo.zip").write_bytes(b"zip previo")  # no debe entrar

    salida = accion_archivar(exp)
    zips = list(exp.ruta.glob("EXP-TEST_archivo_*.zip"))
    nuevo = [z for z in zips if "viejo" not in z.name][0]
    assert nuevo.name in salida

    with zipfile.ZipFile(nuevo) as z:
        nombres = set(z.namelist())
        manifiesto = json.loads(z.read("manifest.json"))
        assert {"expediente.yaml", "01_observaciones.md", "02_informe.md", "03_instrucciones.md",
                "salidas/ResumenEjecutivo_EXP-TEST.pptx"} <= nombres
        assert any(n.startswith("historial/") and "02_informe" in n for n in nombres)
        assert any(n.startswith("trazas/") and n.endswith("_extraer.json") for n in nombres)
        assert not any(n.endswith(".zip") for n in nombres)
        assert manifiesto["referencia"] == "EXP-TEST" and manifiesto["algoritmo_hash"] == "sha256"
        assert manifiesto["fecha_archivo"] and manifiesto["herramienta"].startswith("revisor-informes")
        rutas = {f["ruta"] for f in manifiesto["ficheros"]}
        assert rutas == nombres - {"manifest.json"}
        for f in manifiesto["ficheros"]:
            assert hashlib.sha256(z.read(f["ruta"])).hexdigest() == f["sha256"]
            assert f["bytes"] == len(z.read(f["ruta"]))
        assert z.read("02_informe.md") == b"# informe v2\n"
    assert verificar_archivo(nuevo) == []


def test_verificar_detecta_manipulacion(expediente_tmp, tmp_path):
    exp = expediente_tmp
    exp.archivo("informe").write_text("# informe\n", encoding="utf-8")
    accion_archivar(exp)
    original = next(exp.ruta.glob("EXP-TEST_archivo_*.zip"))
    manipulado = tmp_path / "manipulado.zip"
    with zipfile.ZipFile(original) as zin, zipfile.ZipFile(manipulado, "w") as zout:
        for n in zin.namelist():
            zout.writestr(n, b"# informe alterado\n" if n == "02_informe.md" else zin.read(n))
    assert verificar_archivo(manipulado) == ["hash distinto: 02_informe.md"]


def test_estado_sugiere_archivar_tras_ppt(expediente_tmp):
    exp = expediente_tmp
    exp.archivo("observaciones").write_text("## OBS-01 · T\n\n- Estado: aprobada\n", encoding="utf-8")
    exp.archivo("informe").write_text("## Objetivo\n\nX\n", encoding="utf-8")
    exp.ruta_ppt().write_bytes(b"PK")
    e = estado_expediente(exp)
    assert e["fase"].startswith("4") and "archivar" in e["siguiente"]
    accion_archivar(exp)
    e = estado_expediente(exp)
    assert e["archivos"] and "archivado" in e["siguiente"]
