"""Request classifier — determines which agent should handle the request."""

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """\
Классифицируй запрос пользователя техподдержки. Определи тип запроса и верни JSON.

Типы:
- faq — частые вопросы (пароль, аккаунт, настройки, подписка, общие вопросы)
- diagnostics — техническая проблема (ошибка, баг, не работает, тормозит, код ошибки)
- billing — оплата, тарифы, счета, платежи, возврат средств
- escalation — жалоба, срочный вопрос, просьба позвать оператора, сложный случай

Ответь ТОЛЬКО валидным JSON без markdown:
{"method": "<тип>", "topic": "<тема одним словом>", "confidence": <0.0-1.0>}\
"""

# Rule-based keyword mapping for fallback
KEYWORD_RULES: list[tuple[list[str], str, str]] = [
    # (keywords, method, default_topic)
    (["ошибка", "error", "crash", "не работает", "баг", "bug", "тормозит", "зависает", "E-"], "diagnostics", "error"),
    (["оплата", "счёт", "счет", "тариф", "платёж", "платеж", "баланс", "стоимость", "цена", "возврат"], "billing", "payment"),
    (["жалоба", "оператор", "человек", "срочно", "менеджер", "претензия"], "escalation", "complaint"),
    (["пароль", "аккаунт", "подписка", "настройки", "email", "удалить", "восстановить", "2fa"], "faq", "account"),
]


@dataclass
class ClassificationResult:
    method: str  # faq, diagnostics, billing, escalation
    topic: str
    confidence: float


def classify_rule_based(message: str) -> ClassificationResult:
    """Classify using keyword matching (fallback when LLM is unavailable)."""
    message_lower = message.lower()

    best_method = "faq"
    best_topic = "general"
    best_score = 0

    for keywords, method, topic in KEYWORD_RULES:
        score = sum(1 for kw in keywords if kw.lower() in message_lower)
        if score > best_score:
            best_score = score
            best_method = method
            best_topic = topic

    confidence = min(0.5 + best_score * 0.15, 0.9) if best_score > 0 else 0.3
    return ClassificationResult(method=best_method, topic=best_topic, confidence=confidence)


async def classify_with_llm(message: str, model: str) -> ClassificationResult:
    """Classify using LLM (primary method)."""
    import litellm

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
            max_tokens=100,
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        return ClassificationResult(
            method=data.get("method", "faq"),
            topic=data.get("topic", "general"),
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception as e:
        logger.warning("LLM classification failed (%s), falling back to rules", e)
        return classify_rule_based(message)


class RequestClassifier:
    """Classifies user requests to determine the appropriate agent."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def classify(self, message: str) -> ClassificationResult:
        return await classify_with_llm(message, self.model)

    def classify_sync(self, message: str) -> ClassificationResult:
        """Synchronous rule-based classification (for testing / fallback)."""
        return classify_rule_based(message)
