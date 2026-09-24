"""Observabilidad con Langfuse (E-1, D-3): el backend es el único que envía, y solo metadatos.

No es una rebanada de §2 (architecture.md §8): lee la base de cualquier proyecto y no la
escribe. Qué se envía está en `traza.py`; cómo se codifica, en `otlp.py`; el cliente HTTP,
en `cliente.py`; cuándo, en `exportar.py`.
"""
