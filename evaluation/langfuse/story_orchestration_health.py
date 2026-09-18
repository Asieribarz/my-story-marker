"""Langfuse code evaluator: story-orchestration-health.

Judges one delegated call of the adventure-story generator against the
invariants that a machine can check without reading the prose. Every check
here is executed, never asserted; narrative judgement belongs to the
consistency-checker and the continuity-auditor, not to this evaluator.

Rules checked: FR-46 / TR-09 (one call type per invocation), FR-48 (labelled
delegation), FR-45 / I-9 (workspace confinement), context discipline.
No configuration value is hard-coded here (FR-20): the evaluator reads what
the payload declares and never supplies a number of its own.
"""

import re

LABEL = re.compile(
    r"CALL\s*TYPE:\s*(?P<type>[a-z\- ]+?)\s*(?:\u00b7|\|)\s*SUBJECT:\s*(?P<subject>.+?)"
    r"(?:\s*(?:\u00b7|\|)\s*ATTEMPT:\s*(?P<attempt>\d+))?\s*(?:\(|$)",
    re.IGNORECASE,
)
PAGE_REF = re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE)
K_CHECK = re.compile(r"\bK[1-7]\b")
CONSISTENCY_WORDS = re.compile(r"consistency check|seven checks|verdict", re.IGNORECASE)
PROSE_WORDS = re.compile(r"return the prose|write the prose|write page", re.IGNORECASE)
TRAVERSAL = re.compile(r"\.\.[\/]")
KNOWN_TYPES = ("page", "consistency", "bible", "continuity", "closing", "extraction", "digest")


def _first_user_text(messages):
    if isinstance(messages, str):
        return messages
    if isinstance(messages, dict):
        return str(messages.get("content", ""))
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _all_text(messages):
    if isinstance(messages, str):
        return messages
    parts = []
    for m in messages or []:
        if isinstance(m, dict):
            parts.append(str(m.get("content", "")))
    return "\n".join(parts)


def _read_calls(messages):
    n = 0
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        for tc in m.get("tool_calls") or []:
            fn = (tc.get("function") or {}).get("name") if isinstance(tc, dict) else None
            if fn == "Read":
                n += 1
    return n


def evaluate(context):
    obs = context.observation
    messages = obs.input if obs is not None else None
    prompt = _first_user_text(messages)
    body = _all_text(messages)
    output = ""
    if obs is not None and isinstance(obs.output, dict):
        output = str(obs.output.get("content", ""))

    findings = []
    m = LABEL.search(prompt)
    call_type = "unlabelled"
    attempt = None

    # FR-48 - every delegation carries its call type, its page and its attempt.
    if m is None:
        findings.append(
            "FR-48 - the call carries no 'CALL TYPE / SUBJECT / ATTEMPT' header, so it is "
            "recoverable only by hand - have the orchestrator prefix every delegation with it"
        )
        labelled = False
    else:
        labelled = True
        raw = (m.group("type") or "").strip().lower()
        call_type = next((t for t in KNOWN_TYPES if raw.startswith(t)), raw or "unknown")
        if m.group("attempt"):
            attempt = int(m.group("attempt"))
        else:
            findings.append(
                "FR-48 - the header names no attempt number, so a retry is indistinguishable "
                "from a first try - add 'ATTEMPT: n' to the label"
            )
        if call_type in ("page", "consistency") and not PAGE_REF.search(m.group("subject") or ""):
            findings.append(
                "FR-48 - the subject does not name the page this call is about - "
                "put the page number in the SUBJECT field"
            )

    # FR-46 / TR-09 - page and consistency are never the same invocation.
    merged = False
    if call_type == "page" and (K_CHECK.search(body) or CONSISTENCY_WORDS.search(body)):
        merged = True
        findings.append(
            "FR-46 / TR-09 - this page call also carries the consistency checks; running the "
            "check inside the writing call is the defect the split exists to retire - "
            "issue the consistency call as its own invocation"
        )
    if call_type == "consistency" and PROSE_WORDS.search(prompt):
        merged = True
        findings.append(
            "FR-46 / TR-09 - this consistency call also asks for prose - a checker never rewrites"
        )

    # FR-45 / I-9 - no path may climb above the story root.
    traversal = bool(TRAVERSAL.search(body))
    if traversal:
        findings.append(
            "FR-45 / I-9 - a path in the payload traverses above the story root; one story "
            "overwriting another is the defect the workspace layout removes - "
            "resolve every path against derived.story_root and reject the rest"
        )

    # Context discipline - a page call is handed one assembled context and reads only it.
    reads = _read_calls(messages if isinstance(messages, list) else [])
    over_read = call_type == "page" and reads > 1
    if over_read:
        findings.append(
            "context discipline - the page call opened %d files although its payload was one "
            "assembled context; each extra read is context the beat did not declare - "
            "assemble in code and hand a single path" % reads
        )

    empty_output = call_type in ("page", "consistency") and len(output.strip()) == 0
    if empty_output:
        findings.append(
            "the call returned no content to the orchestrator - a delegation whose result is "
            "empty cannot be validated or logged"
        )

    penalty = 0.0
    penalty += 0.30 if merged else 0.0
    penalty += 0.30 if not labelled else 0.0
    penalty += 0.20 if traversal else 0.0
    penalty += 0.20 if over_read else 0.0
    penalty += 0.10 if (labelled and attempt is None) else 0.0
    penalty += 0.10 if empty_output else 0.0
    health = max(0.0, min(1.0, 1.0 - penalty))

    comment = "\n".join("- " + f for f in findings) if findings else \
        "No mechanical improvement found: the call is labelled, single-typed, confined to its " \
        "workspace and read only what it was handed."

    scores = [
        {
            "name": "orchestration-health",
            "dataType": "NUMERIC",
            "value": round(health, 2),
            "comment": comment,
        },
        {
            "name": "call-type",
            "dataType": "CATEGORICAL",
            "value": call_type,
            "comment": "Call type read from the FR-48 label; 'unlabelled' when there is none.",
        },
        {
            "name": "call-type-separation",
            "dataType": "BOOLEAN",
            "value": 0 if merged else 1,
            "comment": "1 when the invocation carries exactly one call type (FR-46, TR-09).",
        },
        {
            "name": "workspace-confinement",
            "dataType": "BOOLEAN",
            "value": 0 if traversal else 1,
            "comment": "1 when no path in the payload climbs above the story root (FR-45, I-9).",
        },
    ]
    if attempt is not None:
        scores.append({
            "name": "attempt",
            "dataType": "NUMERIC",
            "value": attempt,
            "comment": "Attempt number from the label; group by call-type to see where retries cluster.",
        })
    return {"scores": scores}
