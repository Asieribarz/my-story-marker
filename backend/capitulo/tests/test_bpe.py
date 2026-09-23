"""RF-52c: el BPE de o200k_base está versionado y el estimador carga sin red."""

import hashlib
from pathlib import Path

import pytest
import tiktoken
import tiktoken.load
from tiktoken_ext import openai_public  # type: ignore[import-untyped]

DIRECTORIO_BPE = Path(__file__).resolve().parents[1] / "bpe"
URL_O200K = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
NOMBRE = "fb374d419588a4632f3f557e76b4b70aebbca790"
SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"


def test_el_nombre_es_el_que_tiktoken_busca_en_su_cache() -> None:
    assert hashlib.sha1(URL_O200K.encode()).hexdigest() == NOMBRE


def test_el_fichero_versionado_conserva_su_sha256() -> None:
    # Si falla, casi seguro que Git ha convertido saltos de línea: ver .gitattributes.
    contenido = (DIRECTORIO_BPE / NOMBRE).read_bytes()
    assert hashlib.sha256(contenido).hexdigest() == SHA256


def test_la_codificacion_carga_sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    def sin_red(ruta: str) -> bytes:
        raise AssertionError(f"tiktoken ha intentado descargar {ruta}")

    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(DIRECTORIO_BPE))
    monkeypatch.setattr(tiktoken.load, "read_file", sin_red)

    codificacion = tiktoken.Encoding(**openai_public.o200k_base())

    assert len(codificacion.encode("Érase una vez un perro llamado Nala.")) > 0
