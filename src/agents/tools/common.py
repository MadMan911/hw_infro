"""Common tools shared by all agents."""

ESCALATE_TOOL = {
    "type": "function",
    "function": {
        "name": "escalate",
        "description": (
            "Передать запрос другому агенту, если текущий не может помочь. "
            "Используй когда вопрос выходит за рамки твоей компетенции."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Причина эскалации (почему ты не можешь помочь)",
                },
                "target": {
                    "type": "string",
                    "enum": ["faq", "diagnostics", "billing", "escalation"],
                    "description": (
                        "Кому передать: faq (частые вопросы), "
                        "diagnostics (техническая диагностика), "
                        "billing (оплата и тарифы), "
                        "escalation (живой оператор)"
                    ),
                },
            },
            "required": ["reason", "target"],
        },
    },
}


def execute_escalate(reason: str, target: str) -> str:
    return f"Запрос эскалирован к агенту '{target}'. Причина: {reason}"
