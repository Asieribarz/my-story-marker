"""Spans a OTLP/HTTP en JSON, el formato del endpoint OpenTelemetry de Langfuse.

Es el camino de escritura que Langfuse mantiene: su API de ingesta por lotes está
obsoleta en Langfuse Cloud y deja de aceptar trazas el 2026-11-16 (docs/iteraciones.md
I-09). En OTLP/JSON los identificadores van en hexadecimal y los enteros como cadena.
"""

from collections.abc import Sequence
from typing import Any

from backend.observabilidad.traza import Span, Valor

SERVICIO = "my-story-marker"
AMBITO = "my-story-marker.observabilidad"
TIPO_INTERNO = 1


def _valor(valor: Valor) -> dict[str, Any]:
    if isinstance(valor, bool):
        return {"boolValue": valor}
    if isinstance(valor, int):
        return {"intValue": str(valor)}
    if isinstance(valor, float):
        return {"doubleValue": valor}
    return {"stringValue": valor}


def _atributos(atributos: dict[str, Valor]) -> list[dict[str, Any]]:
    return [{"key": clave, "value": _valor(valor)} for clave, valor in atributos.items()]


def _span(span: Span) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "traceId": span.traza,
        "spanId": span.id,
        "name": span.nombre,
        "kind": TIPO_INTERNO,
        "startTimeUnixNano": str(span.inicio_ns),
        "endTimeUnixNano": str(span.fin_ns),
        "attributes": _atributos(span.atributos),
    }
    if span.padre is not None:
        cuerpo["parentSpanId"] = span.padre
    return cuerpo


def peticion(spans: Sequence[Span]) -> dict[str, Any]:
    """Un `ExportTraceServiceRequest` con todos los spans bajo un mismo recurso."""
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _atributos({"service.name": SERVICIO})},
                "scopeSpans": [{"scope": {"name": AMBITO}, "spans": [_span(s) for s in spans]}],
            }
        ]
    }
