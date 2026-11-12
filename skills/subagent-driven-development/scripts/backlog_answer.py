#!/usr/bin/env python3
"""The one answer rule for backlog decide and answer: an option label, a label plus a note, or free text."""
from backlog_checks import REC

RULE = ('an answer is an option label, a label plus a note ("<label>; note: <text>" or {"label": L, "note": N}), '
        'or your own text: 1 to 2000 characters, no control characters but newline and tab')
MAX = 2000


def labels_of(question: dict) -> list[str]:
    """Option labels of a question, without the recommended suffix."""
    out = []  # O(1)
    for o in question.get("options") or []:  # O(options)
        if isinstance(o, dict) and isinstance(o.get("label"), str):  # O(1)
            out.append(_bare(o["label"]))  # O(len)
    return out  # O(1)


def _bare(s: str) -> str:
    s = s.strip()  # O(len)
    return s[:len(s) - len(REC)].rstrip() if s.endswith(REC) and len(s) > len(REC) else s  # O(len)


def _bad(s: str) -> bool:
    return any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in s)  # O(len)


def _one_of(labels: list[str]) -> str:
    return "answer must be one of: " + ", ".join(labels)  # O(labels)


def answer_text(value: object, labels: list[str], fixed: bool = False) -> tuple[str | None, str]:
    """(text, "") for a valid answer, (None, reason) otherwise."""
    if isinstance(value, str):  # O(1)
        s = value.strip()  # O(len)
        if not 1 <= len(s) <= MAX or _bad(s):  # O(len)
            return None, RULE  # O(1)
        base = _bare(s)  # O(len)
        if base in labels:  # O(labels)
            return base, ""  # O(1)
        return (None, _one_of(labels)) if fixed else (s, "")  # O(1)
    if not isinstance(value, dict) or "label" not in value or set(value) - {"label", "note"}:  # O(1)
        return None, RULE  # O(1)
    label, note = value["label"], value.get("note", "")  # O(1)
    if not isinstance(label, str) or not isinstance(note, str):  # O(1)
        return None, RULE  # O(1)
    label, note = _bare(label), note.strip()  # O(len)
    if not label or _bad(label) or _bad(note) or len(label) + len(note) > MAX:  # O(len)
        return None, RULE  # O(1)
    if fixed and label not in labels:  # O(labels)
        return None, _one_of(labels)  # O(1)
    if fixed and note:  # O(1)
        return None, "this question takes only its label, no note"  # O(1)
    if labels and label not in labels:  # O(labels)
        return None, f'label "{label}" is not one of: ' + ", ".join(labels)  # O(labels)
    text = f"{label}; note: {note}" if note else label  # O(len)
    return (None, RULE) if len(text) > MAX else (text, "")  # O(1)
