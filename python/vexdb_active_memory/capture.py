from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


CAPTURE_TRIGGERS = (
    r"\bremember\b",
    r"\bnote that\b",
    r"\bkeep in mind\b",
    r"\bprefer(?:s|ence)?\b",
    r"\bdecided?\b",
    r"\bdeadline\b",
    r"\bphone\b",
    r"\bemail\b",
    r"记住",
    r"请记",
    r"偏好",
    r"决定",
    r"截止",
    r"电话",
    r"邮箱",
    r"重要",
)

_TRIGGER_RE = re.compile("|".join(f"(?:{item})" for item in CAPTURE_TRIGGERS), re.I)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s-]{7,}\d)")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}")
_STOPWORDS = {
    "remember",
    "please",
    "that",
    "this",
    "user",
    "prefers",
    "preference",
    "important",
    "记住",
    "请记",
    "用户",
    "这个",
    "那个",
}


@dataclass(frozen=True)
class CaptureCandidate:
    content: str
    message_id: str | None = None
    memory_type: str = "fact"
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.75
    reason: str = "trigger"


def should_capture(text: str) -> bool:
    value = text.strip()
    if len(value) < 8:
        return False
    return bool(_TRIGGER_RE.search(value) or _EMAIL_RE.search(value) or _PHONE_RE.search(value))


def classify_memory_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["prefer", "preference", "likes", "dislikes", "偏好", "喜欢", "不喜欢"]):
        return "preference"
    if any(term in lowered for term in ["decide", "decided", "decision", "决定", "决策", "结论"]):
        return "decision"
    if _EMAIL_RE.search(text) or _PHONE_RE.search(text) or any(term in lowered for term in ["entity", "contact", "person", "实体", "联系人", "电话", "邮箱"]):
        return "entity"
    if any(term in lowered for term in ["todo", "task", "deadline", "due", "follow up", "任务", "待办", "截止"]):
        return "task"
    if any(term in lowered for term in ["policy", "rule", "must", "requirement", "规则", "必须", "要求"]):
        return "policy"
    if any(term in lowered for term in ["note", "observation", "备注", "记录"]):
        return "note"
    return "fact"


def extract_tags(text: str, *, limit: int = 8) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(text):
        value = token.strip().lower()
        if value in _STOPWORDS or value in seen:
            continue
        seen.add(value)
        tags.append(value[:40])
        if len(tags) >= limit:
            break
    return tags


def capture_candidates(messages: list[dict[str, Any]], *, after_message_id: str | None = None) -> list[CaptureCandidate]:
    candidates: list[CaptureCandidate] = []
    seen_after = after_message_id is None
    for message in messages:
        message_id = str(message.get("id") or message.get("message_id") or "")
        if not seen_after:
            if message_id == after_message_id:
                seen_after = True
            continue
        content = str(message.get("content") or message.get("text") or "").strip()
        if not should_capture(content):
            continue
        candidates.append(
            CaptureCandidate(
                content=content,
                message_id=message_id or None,
                memory_type=classify_memory_type(content),
                tags=extract_tags(content),
                confidence=0.85 if _TRIGGER_RE.search(content) else 0.7,
                reason="trigger_or_entity",
            )
        )
    return candidates
