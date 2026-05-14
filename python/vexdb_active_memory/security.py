from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptInjectionFinding:
    pattern: str
    reason: str


_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)\b", re.I), "ignore_instructions"),
    (re.compile(r"\b(system|developer)\s+prompt\b", re.I), "prompt_exfiltration"),
    (re.compile(r"\b(reveal|print|dump|show)\s+(the\s+)?(system|developer)\s+(prompt|message)\b", re.I), "prompt_exfiltration"),
    (re.compile(r"\b(disable|bypass|override)\s+(safety|guardrails|policy|filters?)\b", re.I), "safety_bypass"),
    (re.compile(r"\bforget\s+(all\s+)?(previous|prior)\s+(instructions|rules|memory)\b", re.I), "memory_override"),
    (re.compile(r"<\s*(script|iframe|object|embed|meta)\b", re.I), "html_script"),
    (re.compile(r"(?i)(忽略|无视).{0,12}(之前|以上|所有).{0,12}(指令|规则|要求)"), "ignore_instructions_zh"),
    (re.compile(r"(?i)(泄露|输出|打印|展示).{0,12}(系统|开发者).{0,12}(提示词|提示|prompt)"), "prompt_exfiltration_zh"),
)


def detect_prompt_injection(text: str) -> list[PromptInjectionFinding]:
    findings: list[PromptInjectionFinding] = []
    for pattern, reason in _PATTERNS:
        if pattern.search(text):
            findings.append(PromptInjectionFinding(pattern=pattern.pattern, reason=reason))
    return findings


def escape_memory_for_prompt(text: str) -> str:
    return html.escape(text, quote=True)
