from dataclasses import dataclass

from src.guardrails.pii_filter import PiiMode, contains_pii, mask_pii
from src.guardrails.prompt_injection import is_injection
from src.guardrails.secret_detector import contains_secret


@dataclass
class GuardrailResult:
    passed: bool
    blocked: bool = False
    reason: str = ""
    modified_text: str | None = None  # set when text was modified (masked)

    @classmethod
    def ok(cls, text: str | None = None) -> "GuardrailResult":
        return cls(passed=True, blocked=False, modified_text=text)

    @classmethod
    def block(cls, reason: str) -> "GuardrailResult":
        return cls(passed=False, blocked=True, reason=reason)

    @classmethod
    def masked(cls, text: str) -> "GuardrailResult":
        return cls(passed=True, blocked=False, modified_text=text)


class GuardrailsEngine:
    """Pipeline of security checks applied to LLM input and output."""

    def __init__(self, pii_mode: PiiMode = PiiMode.MASK) -> None:
        self.pii_mode = pii_mode

    async def check_input(self, message: str) -> GuardrailResult:
        """Check user input before it reaches the agent."""
        # 1. Prompt injection
        if is_injection(message):
            return GuardrailResult.block("Запрос заблокирован системой безопасности: обнаружена попытка инъекции.")

        # 2. Secret leak (user sending API keys, passwords, etc.)
        if contains_secret(message):
            return GuardrailResult.block("Запрос заблокирован: обнаружены конфиденциальные данные (ключи API, пароли).")

        # 3. PII handling
        if contains_pii(message):
            if self.pii_mode == PiiMode.BLOCK:
                return GuardrailResult.block("Запрос заблокирован: обнаружены персональные данные.")
            else:
                masked = mask_pii(message)
                return GuardrailResult.masked(masked)

        return GuardrailResult.ok()

    async def check_output(self, response: str) -> GuardrailResult:
        """Check agent output before it is sent to the user."""
        # Mask PII that the model might have produced
        if contains_pii(response):
            if self.pii_mode == PiiMode.BLOCK:
                return GuardrailResult.block("Ответ заблокирован: содержит персональные данные.")
            else:
                masked = mask_pii(response)
                return GuardrailResult.masked(masked)

        # Mask secrets accidentally included in output
        if contains_secret(response):
            return GuardrailResult.block("Ответ заблокирован: содержит конфиденциальные данные.")

        return GuardrailResult.ok()
