from __future__ import annotations

from typing import Any


HIGH_IMPORTANCE_TERMS = {
    "must",
    "critical",
    "important",
    "always",
    "never",
    "preference",
    "prefers",
    "policy",
    "requirement",
    "deadline",
    "必须",
    "重要",
    "偏好",
    "要求",
    "截止",
    "永远",
    "不要",
}


LOW_IMPORTANCE_TERMS = {
    "temporary",
    "draft",
    "maybe",
    "scratch",
    "debug",
    "临时",
    "草稿",
    "可能",
    "调试",
}


def estimate_importance(text: str, metadata: dict[str, Any] | None = None) -> int:
    metadata = metadata or {}
    explicit = metadata.get("importance")
    if isinstance(explicit, int) and 1 <= explicit <= 5:
        return explicit

    lowered = text.lower()
    score = 3
    memory_type = str(metadata.get("memory_type", "")).lower()
    source_trust = metadata.get("source_trust")
    confidence = metadata.get("confidence")

    if any(term in lowered for term in HIGH_IMPORTANCE_TERMS):
        score += 1
    if any(term in lowered for term in LOW_IMPORTANCE_TERMS):
        score -= 1
    if memory_type in {"policy", "preference", "requirement"}:
        score += 1
    if isinstance(source_trust, (int, float)):
        if source_trust >= 0.8:
            score += 1
        elif source_trust <= 0.3:
            score -= 1
    if isinstance(confidence, (int, float)) and confidence < 0.4:
        score -= 1
    if len(text) > 240:
        score += 1
    return max(1, min(5, score))


def normalize_tags(tags: list[str] | tuple[str, ...] | None) -> list[str]:
    if not tags:
        return []
    clean: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        value = tag.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        clean.append(value)
    return clean[:32]


def auto_conflict_decision(policy: str, *, nearest_distance: float | None = None) -> str | None:
    policy = (policy or "manual").lower()
    if policy in {"manual", "off", "none"}:
        return None
    if policy in {"append", "update", "reject"}:
        return policy
    if policy == "heuristic":
        if nearest_distance is not None and nearest_distance < 0.08:
            return "update"
        return "append"
    return None
