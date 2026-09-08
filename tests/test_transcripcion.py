"""Transcripción con identificación de hablantes: parseo de segments (formato real de
la Fase 0), umbral de relevancia, clips sin solape, etiquetado (fusión/ignorar),
agrupación de intervenciones, voces por expediente (aislamiento) y ciclo de vida en
archivar. Respuestas de la API mockeadas; ffmpeg con wavs sintéticos diminutos."""
from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from audit_agent import transcripcion
from audit_agent.expediente import Expediente, ExpedienteError
from audit_agent.transcripcion import (_por_hablante, _segmento_para_clip, accion_etiquetar, accion_transcribir,
                                       accion_voces, cargar_voces, dir_audio, guardar_voz, segmentos_globales,
                                       voces_para_enviar)

FFMPEG = shutil.which("ffmpeg")


def S(spk, a, b, t):
    return {"id": "seg", "speaker": spk, "start": a, "end": b, "text": t}


def R(*segs, dur=None):
    return {"model": "gpt-4o-transcribe-diarize", "provider": "openai",
            "duration": dur if dur is not None else (segs[-1]["end"] if segs else 0.0),
            "segments": list(segs), "text": " ".join(s["text"] for s in segs)}


def _wav(ruta: Path, segundos: float = 30.0):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={segundos}",
                    "-ac", "1", "-ar", "16000", str(ruta)], capture_output=True, check=True)


# ------------------------------------------------------------ unidades
def test_segmentos_globales_aplica_offsets_y_ordena():
    r1 = R(S("A", 0.0, 2.0, "hola"), S("B", 2.5, 4.0, "adiós"))
    r2 = R(S("A", 1.0, 3.0, "sigo"))
    segs = segmentos_globales([r1, None, r2], [0.0, 300.0, 600.0])   # una parte fallida en medio
    assert [(s["speaker"], s["start"], s["end"]) for s in segs] == [("A", 0.0, 2.0), ("B", 2.5, 4.0), ("A", 601.0, 603.0)]


def test_umbral_de_relevancia_y_clip_sin_solape():
    segs = [S("A", 0, 8, "a1"), S("B", 8, 9, "b"), S("A", 10, 13, "a2 limpio"), S("C", 12.5, 20, "c solapa con a2"),
            S("A", 30, 31.5, "a3"), S("C", 40, 55, "c2")]
    grupos = _por_hablante(segs)
    assert round(grupos["A"]["segundos"], 1) == 12.5 and round(grupos["B"]["segundos"], 1) == 1.0
    ini, dur = _segmento_para_clip(grupos["A"]["segmentos"], segs)
    assert (ini, dur) == (0, 8.0)     # el tramo ininterrumpido más largo y limpio (0-8), entero por ser < 10 s
    # tramo ininterrumpido de varios segmentos consecutivos -> se une y se recorta a ~10 s
    seguidos = [S("A", 0, 6, "x"), S("A", 6.2, 14, "y"), S("B", 15, 16, "z")]
    ini, dur = _segmento_para_clip([seguidos[0], seguidos[1]], seguidos)
    assert (ini, dur) == (0, 9.9)
    # si todos solapan, cae al tramo más largo igualmente
    todos = [S("A", 0, 10, "x"), S("B", 0, 10, "y")]
    ini, dur = _segmento_para_clip([todos[0]], todos)
    assert ini == 0 and dur == 9.9


# ------------------------------------------------------------ transcribir
@pytest.fixture
def exp_audio(expediente_tmp, monkeypatch, tmp_path):
    if not FFMPEG:
        pytest.skip("sin ffmpeg")
    audio = tmp_path / "reunion.wav"
    _wav(audio, 30)
    return expediente_tmp, audio


RESPUESTA_DOS_VOCES = R(
    S("A", 0.0, 6.0, "Buenos días, empezamos la revisión del borrador."),
    S("B", 6.5, 12.0, "De acuerdo, subimos el riesgo a alto."),
    S("A", 12.5, 18.0, "En el resumen añadid la viñeta de PackPro."),
    S("C", 18.5, 20.0, "(tos)"),
    S("B", 20.5, 27.0, "También dividimos la recomendación en dos."),
)


def test_transcribir_genera_cruda_hablantes_y_clips(exp_audio, monkeypatch):
    exp, audio = exp_audio
    visto = {}
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: (
        [visto.__setitem__("hablantes", hablantes), RESPUESTA_DOS_VOCES][1]))
    salida = accion_transcribir(exp, audio)
    base = dir_audio(exp)
    assert visto["hablantes"] == []                                     # sin voces guardadas no viaja nada
    cruda = (base / "transcripcion_cruda.md").read_text(encoding="utf-8")
    assert "SPEAKER_01: Buenos días" in cruda and "SPEAKER_02: De acuerdo" in cruda
    assert "[00:12–00:18]" in cruda and "] C: (tos)" in cruda   # la cruda es fiel: el menor aparece con su letra
    assert "Hablantes relevantes: 2 (+1 menores descartados" in cruda
    md = (base / "hablantes.md").read_text(encoding="utf-8")
    assert "| SPEAKER_01 | SPEAKER_01.wav |" in md and "| SPEAKER_02 |" in md and "SPEAKER_03" not in md
    assert (base / "hablantes" / "SPEAKER_01.wav").exists() and (base / "hablantes" / "SPEAKER_02.wav").exists()
    meta = json.loads((base / "hablantes" / "meta.json").read_text(encoding="utf-8"))
    assert meta["hablantes"]["SPEAKER_01"]["etiqueta_api"] == "A" and meta["menores_descartados"] == 1
    assert (base / meta["normalizado"]).exists()                        # copia normalizada mono 16 kHz
    assert "Por nombrar: SPEAKER_01, SPEAKER_02" in salida
    trazas = [p for p in (exp.ruta / "trazas").iterdir() if "_transcribir" in p.name]
    assert len(trazas) == 1 and b'"segments"' in trazas[0].read_bytes()
    assert trazas[0].stat().st_size < 20_000          # JSON de metadatos y texto: el audio no se copia a trazas
    # una segunda transcripción sin etiquetar la anterior exige --forzar
    with pytest.raises(ExpedienteError, match="sin etiquetar"):
        accion_transcribir(exp, audio)


def test_known_speakers_no_pasan_por_nombrado(exp_audio, monkeypatch, tmp_path):
    exp, audio = exp_audio
    clip = tmp_path / "marta.wav"
    _wav(clip, 2)
    guardar_voz(exp, "Marta", clip, "reunion0.wav", 120.0)
    visto = {}
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: (
        [visto.__setitem__("hablantes", hablantes), R(
            S("Marta", 0.0, 15.0, "Hola, soy Marta y hablo un buen rato."),
            S("A", 15.5, 30.0, "Y yo soy otra persona sin identificar."))][1]))
    salida = accion_transcribir(exp, audio)
    assert visto["hablantes"] == [("Marta", str(dir_audio(exp) / "voces" / "Marta.wav"))]
    cruda = (dir_audio(exp) / "transcripcion_cruda.md").read_text(encoding="utf-8")
    assert "] Marta: Hola" in cruda and "] SPEAKER_01: Y yo soy" in cruda
    md = (dir_audio(exp) / "hablantes.md").read_text(encoding="utf-8")
    assert "Marta" not in md and "| SPEAKER_01 |" in md                 # la conocida no se vuelve a nombrar
    assert "Ya nombrados por las voces del expediente: Marta." in salida


def test_aislamiento_entre_expedientes(exp_audio, monkeypatch, tmp_path):
    exp, audio = exp_audio
    otro = Expediente.crear(tmp_path / "OTRO-1", "Otro", "OTRO-1", "Mayo 2026", [])
    clip = tmp_path / "v.wav"
    _wav(clip, 2)
    guardar_voz(otro, "Intruso", clip, "x.wav", 500.0)
    visto = {}
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: (
        [visto.__setitem__("hablantes", hablantes), RESPUESTA_DOS_VOCES][1]))
    accion_transcribir(exp, audio)                                      # expediente SIN voces propias
    assert visto["hablantes"] == []                                     # jamás lee las voces de otro expediente
    assert voces_para_enviar(exp) == [] and len(voces_para_enviar(otro)) == 1


# ------------------------------------------------------------ etiquetar
def _rellenar_hablantes(exp, valores):
    """valores: {SPEAKER_01: (nombre, accion)}"""
    ruta = dir_audio(exp) / "hablantes.md"
    lineas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = transcripcion._RE_FILA.match(linea)
        if m and m.group(1) in valores:
            nombre, accion = valores[m.group(1)]
            partes = linea.split("|")
            partes[4], partes[5] = f" {nombre} ", f" {accion} "
            linea = "|".join(partes)
        lineas.append(linea)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def test_etiquetar_fusiona_ignora_agrupa_y_guarda_voces(exp_audio, monkeypatch):
    exp, audio = exp_audio
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: R(
        S("A", 0, 8, "Primera frase de Marta."), S("A", 8, 15, "Segunda frase seguida."),
        S("B", 15, 27, "Interviene Javier con su punto."),
        S("C", 27, 39, "El tercero es en realidad también Javier desde otro micro."),
        S("D", 39, 51, "Ruido de la sala que ignoramos."),
        S("E", 51, 53, "Comentario de un hablante menor.")))
    accion_transcribir(exp, audio)
    _rellenar_hablantes(exp, {"SPEAKER_01": ("Marta", ""), "SPEAKER_02": ("Javier", ""),
                              "SPEAKER_03": ("", "fusionar con SPEAKER_02"), "SPEAKER_04": ("", "ignorar")})
    preguntas = []
    salida = accion_etiquetar(exp, preguntar_guardar=lambda nombre, clip: preguntas.append(nombre) or nombre == "Marta")
    instrucciones = exp.archivo("instrucciones").read_text(encoding="utf-8")
    assert "- Marta: Primera frase de Marta. Segunda frase seguida." in instrucciones      # consecutivas agrupadas
    assert "- Javier: Interviene Javier con su punto. El tercero es en realidad" in instrucciones  # fusión + agrupación
    assert "Ruido de la sala" not in instrucciones                                          # ignorado
    assert "Comentario de un hablante menor" not in instrucciones                           # menor descartado
    assert "Reunión transcrita «reunion.wav»" in instrucciones
    assert (dir_audio(exp) / "transcripcion_cruda.md").read_text(encoding="utf-8").startswith("> Etiquetada")
    assert sorted(preguntas) == ["Javier", "Marta"] and sorted(cargar_voces(exp)) == ["Marta"]  # pregunta POR hablante
    assert "2 intervenciones de 2 hablante(s)" in salida   # Marta agrupada; Javier + su fusión consecutiva
    # ya etiquetada: no se puede repetir
    with pytest.raises(ExpedienteError, match="ya se etiquetó"):
        accion_etiquetar(exp)


def test_etiquetar_hablante_incompleto_da_error_claro(exp_audio, monkeypatch):
    exp, audio = exp_audio
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: RESPUESTA_DOS_VOCES)
    accion_transcribir(exp, audio)
    _rellenar_hablantes(exp, {"SPEAKER_01": ("Marta", "")})             # SPEAKER_02 sin nombre ni acción
    with pytest.raises(ExpedienteError, match="SPEAKER_02 no tiene Nombre ni Acción"):
        accion_etiquetar(exp)
    # y las fusiones circulares también son error claro
    _rellenar_hablantes(exp, {"SPEAKER_01": ("", "fusionar con SPEAKER_02"), "SPEAKER_02": ("", "fusionar con SPEAKER_01")})
    with pytest.raises(ExpedienteError, match="circulares"):
        accion_etiquetar(exp)


# ------------------------------------------------------------ voces y ciclo de vida
def test_voces_listar_borrar_y_prioridad(expediente_tmp, tmp_path):
    if not FFMPEG:
        pytest.skip("sin ffmpeg")
    exp = expediente_tmp
    for nombre, seg in (("Ana", 50), ("Bea", 300), ("Carlos", 200), ("David", 100), ("Eva", 400)):
        clip = tmp_path / f"{nombre}.wav"
        _wav(clip, 1)
        guardar_voz(exp, nombre, clip, "r.wav", seg)
    assert [n for n, _ in voces_para_enviar(exp)] == ["Eva", "Bea", "Carlos", "David"]   # top 4 por habla acumulada
    listado = accion_voces(exp)
    assert "Eva" in listado and "se borran al archivar" in listado
    accion_voces(exp, borrar=["Eva", "Ana"])
    assert sorted(cargar_voces(exp)) == ["Bea", "Carlos", "David"]
    with pytest.raises(ExpedienteError, match="No hay una voz"):
        accion_voces(exp, borrar=["Zoe"])


def test_archivar_destruye_voces_clips_y_audios_con_constancia(exp_audio, monkeypatch, tmp_path):
    from audit_agent.acciones import accion_archivar
    exp, audio = exp_audio
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: RESPUESTA_DOS_VOCES)
    accion_transcribir(exp, audio)
    clip = tmp_path / "m.wav"
    _wav(clip, 1)
    guardar_voz(exp, "Marta", clip, "reunion.wav", 30)
    exp.archivo("informe").write_text("# Informe\n", encoding="utf-8")
    salida = accion_archivar(exp)
    zip_ruta = next(exp.ruta.glob("*_archivo_*.zip"))
    with zipfile.ZipFile(zip_ruta) as z:
        nombres = z.namelist()
        manifiesto = json.loads(z.read("manifest.json"))
    assert "entrada/audio/hablantes.md" in nombres and "entrada/audio/transcripcion_cruda.md" in nombres
    assert not any("voces/" in n or "hablantes/" in n or n.endswith((".wav", ".mp3")) for n in nombres)
    borrados = {b["ruta"] for b in manifiesto["borrados_tras_archivar"]}
    assert "entrada/audio/voces/Marta.wav" in borrados and any("SPEAKER_01.wav" in b for b in borrados)
    assert all(len(b["sha256"]) == 64 for b in manifiesto["borrados_tras_archivar"])
    base = dir_audio(exp)
    assert not (base / "voces").exists() and not (base / "hablantes").exists()
    assert not any(p.suffix in (".mp3", ".wav") for p in base.iterdir())
    assert (base / "hablantes.md").exists() and (base / "transcripcion_cruda.md").exists()
    assert "Material de voz/audio destruido" in salida


# ------------------------------------------------------------ integración real (opt-in)
@pytest.mark.kaia_audio
def test_integracion_real_dos_voces(expediente_tmp, tmp_path):
    """pytest -m kaia_audio: contra la API real, con dos voces TTS locales."""
    import os
    if not (FFMPEG and shutil.which("espeak-ng") and os.environ.get("KAIA_CLIENT_ID")):
        pytest.skip("requiere ffmpeg, espeak-ng y credenciales KAIA")
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    subprocess.run(["espeak-ng", "-v", "es+f4", "-p", "70", "-w", str(a),
                    "En la conclusión uno subid el riesgo a alto."], check=True, capture_output=True)
    subprocess.run(["espeak-ng", "-v", "es+m3", "-p", "30", "-w", str(b),
                    "De acuerdo, y dividid la recomendación en dos."], check=True, capture_output=True)
    dialogo = tmp_path / "d.wav"
    lista = tmp_path / "l.txt"
    lista.write_text(f"file '{a}'\nfile '{b}'\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-ac", "1", "-ar", "16000",
                    str(dialogo)], check=True, capture_output=True)
    salida = accion_transcribir(expediente_tmp, dialogo, umbral_s=1.0)
    assert "Transcripción:" in salida
    cruda = (dir_audio(expediente_tmp) / "transcripcion_cruda.md").read_text(encoding="utf-8")
    assert "SPEAKER_01" in cruda


def test_partes_multiples_identidad_estable_y_alta_sobre_la_marcha(expediente_tmp, monkeypatch, tmp_path):
    """Con audio troceado, las voces se enrolan como referencias según aparecen: la de
    la parte 1 vale para todas; una voz nueva en la parte 2 se enrola para la 3; y las
    letras sin referencia quedan aisladas («A·pN») en vez de fusionarse con quien no toca."""
    if not FFMPEG:
        pytest.skip("sin ffmpeg")
    audio = tmp_path / "larga.wav"
    _wav(audio, 13)
    monkeypatch.setenv("KAIA_TRANSCRIBE_MAX_S", "4")     # -> 3 partes (0-4, 4-8, 8-13)
    llamadas = []

    def falso(ruta, hablantes=None):
        llamadas.append((Path(ruta).name, [n for n, _ in (hablantes or [])]))
        if len(llamadas) == 1:
            return R(S("A", 0.0, 3.0, "Voz principal de la primera parte hablando un rato largo."),
                     S("B", 3.2, 3.6, "Apunte brevísimo."))
        if len(llamadas) == 2:
            return R(S("HABLANTE_1", 0.0, 1.5, "Sigo siendo la misma voz."),
                     S("A", 1.8, 4.0, "Soy una persona nueva que entra en la segunda parte."))
        return R(S("HABLANTE_1", 0.0, 2.0, "Cierro yo."),
                 S("HABLANTE_2", 2.2, 4.0, "Y yo, ya identificada."),
                 S("A", 4.2, 4.8, "Voz suelta sin referencia."))

    monkeypatch.setattr(transcripcion, "transcribir_audio", falso)
    accion_transcribir(expediente_tmp, audio, umbral_s=0.5)
    assert llamadas[0][1] == [] and llamadas[1][1] == ["HABLANTE_1"] and llamadas[2][1] == ["HABLANTE_1", "HABLANTE_2"]
    meta = json.loads((dir_audio(expediente_tmp) / "hablantes" / "meta.json").read_text(encoding="utf-8"))
    etiquetas = {d["etiqueta_api"] for d in meta["hablantes"].values()}
    assert {"HABLANTE_1", "HABLANTE_2"} <= etiquetas and "A" not in etiquetas
    assert "A·p3" in etiquetas                       # la voz suelta de la parte 3 no se mezcla
    h1 = next(d for d in meta["hablantes"].values() if d["etiqueta_api"] == "HABLANTE_1")
    assert h1["segundos"] == pytest.approx(3.0 + 1.5 + 2.0, abs=0.3)   # una sola persona a través de las partes


def test_retranscribir_la_copia_normalizada_no_la_corrompe(exp_audio, monkeypatch):
    """Caso real: pasar como entrada el mp3 normalizado del propio expediente hacía que
    ffmpeg escribiera sobre su fuente y lo dejara en ruinas. Además, cada transcripción
    limpia los clips de la anterior."""
    exp, audio = exp_audio
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: RESPUESTA_DOS_VOCES)
    accion_transcribir(exp, audio)
    normalizado = dir_audio(exp) / json.loads((dir_audio(exp) / "hablantes" / "meta.json").read_text(encoding="utf-8"))["normalizado"]
    tam = normalizado.stat().st_size
    viejo = dir_audio(exp) / "hablantes" / "SPEAKER_99.wav"
    viejo.write_bytes(b"resto de otra ejecucion")
    accion_transcribir(exp, normalizado, forzar=True)      # retranscribir la copia del expediente
    assert normalizado.stat().st_size == tam               # la fuente no se toca
    assert not viejo.exists()                              # los clips viejos no sobreviven
    assert (dir_audio(exp) / "hablantes" / "SPEAKER_01.wav").exists()


def test_etiquetar_genera_acta_con_el_analisis_de_reunion(exp_audio, contexto, monkeypatch):
    """Con ctx (LLM disponible) el etiquetado guarda la transcripción en reuniones/ y la
    analiza como una reunión: acta con quién pide cada cosa e instrucciones detectadas al
    buzón (sin volcado en bruto)."""
    from audit_agent.esquemas import AnalisisReunion, CambioTextoDetectado
    exp, audio = exp_audio
    contexto.llm.respuestas["reunion"] = AnalisisReunion(
        resumen="Se revisó el borrador con el área.",
        cambios_texto=[CambioTextoDetectado(seccion="Conclusión 1", que_cambiar="Subir el nivel de riesgo",
                                            instruccion="En la conclusión 1, subir el nivel de riesgo a Alto.",
                                            solicitado_por="Marta")])
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: RESPUESTA_DOS_VOCES)
    accion_transcribir(exp, audio)
    exp.archivo("informe").write_text("# Informe\n\n## Conclusión 1\n\nTexto actual.", encoding="utf-8")
    _rellenar_hablantes(exp, {"SPEAKER_01": ("Marta", ""), "SPEAKER_02": ("Javier", "")})
    salida = accion_etiquetar(exp, ctx=contexto)
    txts = list((exp.ruta / "reuniones").glob("*_transcripcion.txt"))
    actas = list((exp.ruta / "reuniones").glob("*.md"))
    assert len(txts) == 1 and "Marta: Buenos días" in txts[0].read_text(encoding="utf-8")
    assert len(actas) == 1 and "pide: Marta" in actas[0].read_text(encoding="utf-8")
    instrucciones = exp.archivo("instrucciones").read_text(encoding="utf-8")
    assert "- En la conclusión 1, subir el nivel de riesgo a Alto. [Marta]" in instrucciones
    assert "Reunión transcrita «reunion.wav»" not in instrucciones      # con acta no hay volcado en bruto
    assert "Acta: reuniones/" in salida and "Transcripción etiquetada: reuniones/" in salida
    assert (dir_audio(exp) / "transcripcion_cruda.md").read_text(encoding="utf-8").startswith("> Etiquetada")


def test_etiquetar_sin_modelo_cae_al_volcado_en_bruto(exp_audio, contexto, monkeypatch):
    """Si el análisis no está disponible (p. ej. sin 02_informe.md), la conversación se
    vuelca en bruto al buzón y el mensaje explica cómo generar el acta más tarde."""
    exp, audio = exp_audio
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: RESPUESTA_DOS_VOCES)
    accion_transcribir(exp, audio)
    _rellenar_hablantes(exp, {"SPEAKER_01": ("Marta", ""), "SPEAKER_02": ("Javier", "")})
    salida = accion_etiquetar(exp, ctx=contexto)                        # sin 02_informe.md
    instrucciones = exp.archivo("instrucciones").read_text(encoding="utf-8")
    assert "- Marta: Buenos días" in instrucciones and "Reunión transcrita «reunion.wav»" in instrucciones
    assert "Sin acta" in salida and "02_informe.md" in salida
    assert list((exp.ruta / "reuniones").glob("*_transcripcion.txt"))   # la transcripción queda igualmente


def test_transcribir_misma_grabacion_avisa_y_repetir_desbloquea(exp_audio, monkeypatch):
    """La huella SHA-256 de la grabación queda registrada: volver a subir el mismo
    contenido avisa en vez de gastar otra transcripción; --repetir lo permite."""
    exp, audio = exp_audio
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda ruta, hablantes=None: RESPUESTA_DOS_VOCES)
    accion_transcribir(exp, audio)
    with pytest.raises(ExpedienteError, match="Reunión repetida"):
        accion_transcribir(exp, audio, forzar=True)
    assert "Transcripción:" in accion_transcribir(exp, audio, forzar=True, repetir=True)
