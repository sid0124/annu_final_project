\"\"\"
VTR-Agent: Prompt Injection & Untrusted Content Sanitizer

Scans retrieved documents and external web search results (e.g. Tavily)
for prompt injection, instruction override attempts, exfiltration payloads,
and malicious instructions before they can be processed by the agent.
\"\"\"
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field


class InjectionScanResult(BaseModel):
    is_safe: bool
    risk_score: float = 0.0  # 0.0 (clean) to 1.0 (dangerous)
    detected_patterns: List[str] = Field(default_factory=list)
    sanitized_text: str
    action: str = \"ALLOW\"  # ALLOW, WARN, SANITIZE, BLOCK


class PromptInjectionDetector:
    \"\"\"
    Detects direct and indirect prompt injection patterns in untrusted text.
    \"\"\"

    # High-risk instruction override patterns
    INJECTION_PATTERNS = [
        (r\"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions?\", \"instruction_override\"),
        (r\"(?i)disregard\s+(all\s+)?(previous|prior|system)\s+instructions?\", \"instruction_override\"),
        (r\"(?i)you\s+are\s+now\s+(a|an)?\s*(new\s+)?(unrestricted|jailbroken|dan|mode)\", \"jailbreak_attempt\"),
        (r\"(?i)system\s*:\s*you\s+are\", \"system_prompt_impersonation\"),
        (r\"(?i)<\|im_start\|>system\", \"chatml_injection\"),
        (r\"(?i)read_environment_variables?\", \"secret_extraction_attempt\"),
        (r\"(?i)(reveal|show|print|leak|send|exfiltrate)\s+(the\s+)?(api[_\s]?keys?|secrets?|passwords?|tokens?|env)\", \"credential_exfiltration\"),
        (r\"(?i)curl\s+.*http\", \"outbound_network_attempt\"),
        (r\"(?i)webhook\.(site|com)\", \"exfiltration_endpoint\"),
        (r\"(?i)sudo\s+[a-z0-9]+\", \"privilege_escalation\"),
        (r\"(?i)execute:\s*[a-z0-9_]+\(\)\", \"arbitrary_execution_instruction\"),
    ]

    def scan(self, text: str, source: str = \"untrusted_external\") -> InjectionScanResult:
        \"\"\"
        Scans given text for injection patterns.
        \"\"\"
        if not text:
            return InjectionScanResult(
                is_safe=True,
                risk_score=0.0,
                detected_patterns=[],
                sanitized_text=\"\",
                action=\"ALLOW\",
            )

        detected = []
        for pattern, label in self.INJECTION_PATTERNS:
            if re.search(pattern, text):
                detected.append(label)

        risk_score = min(1.0, len(detected) * 0.35)
        is_safe = len(detected) == 0

        # Sanitization: Neutralize obvious override commands
        sanitized = text
        if not is_safe:
            for pattern, _ in self.INJECTION_PATTERNS:
                sanitized = re.sub(pattern, \"[UNTRUSTED_CONTENT_REDACTED]\", sanitized)

        action = \"ALLOW\"
        if risk_score >= 0.7:
            action = \"BLOCK\"
        elif risk_score >= 0.3:
            action = \"SANITIZE\"

        return InjectionScanResult(
            is_safe=is_safe,
            risk_score=risk_score,
            detected_patterns=detected,
            sanitized_text=sanitized,
            action=action,
        )


injection_detector = PromptInjectionDetector()


def scan_untrusted_content(text: str, source: str = \"untrusted_external\") -> InjectionScanResult:
    return injection_detector.scan(text, source)
\"\"\"
