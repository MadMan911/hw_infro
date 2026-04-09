"""Billing agent tools — account info, tariffs, payment history."""

ACCOUNTS = {
    "user-123": {
        "name": "Иван Петров",
        "tariff": "Стандарт",
        "balance": 1250.00,
        "next_payment_date": "2026-05-01",
        "next_payment_amount": 490.00,
        "auto_renewal": True,
    },
    "user-456": {
        "name": "Мария Сидорова",
        "tariff": "Премиум",
        "balance": 0.00,
        "next_payment_date": "2026-04-15",
        "next_payment_amount": 990.00,
        "auto_renewal": True,
    },
    "user-789": {
        "name": "Алексей Козлов",
        "tariff": "Базовый",
        "balance": 0.00,
        "next_payment_date": None,
        "next_payment_amount": 0.00,
        "auto_renewal": False,
    },
}

TARIFFS = {
    "Базовый": {
        "price": "Бесплатно",
        "storage": "5 ГБ",
        "support": "Базовая (email, до 48 часов)",
        "features": ["5 ГБ хранилища", "Базовые функции", "Email-поддержка"],
    },
    "Стандарт": {
        "price": "490 руб/мес",
        "storage": "50 ГБ",
        "support": "Приоритетная (чат, до 4 часов)",
        "features": ["50 ГБ хранилища", "Все базовые функции", "Приоритетная поддержка", "API доступ"],
    },
    "Премиум": {
        "price": "990 руб/мес",
        "storage": "Безлимит",
        "support": "Персональный менеджер, SLA 99.9%",
        "features": [
            "Безлимитное хранилище",
            "Все функции Стандарт",
            "Персональный менеджер",
            "SLA 99.9%",
            "Приоритетный API",
        ],
    },
}

PAYMENT_HISTORY = {
    "user-123": [
        {"date": "2026-04-01", "amount": 490.00, "status": "success", "description": "Стандарт — апрель"},
        {"date": "2026-04-01", "amount": 490.00, "status": "success", "description": "Стандарт — апрель (дубль)"},
        {"date": "2026-03-01", "amount": 490.00, "status": "success", "description": "Стандарт — март"},
        {"date": "2026-02-01", "amount": 490.00, "status": "success", "description": "Стандарт — февраль"},
    ],
    "user-456": [
        {"date": "2026-04-01", "amount": 990.00, "status": "success", "description": "Премиум — апрель"},
        {"date": "2026-03-01", "amount": 990.00, "status": "success", "description": "Премиум — март"},
    ],
    "user-789": [],
}


def get_account_info(account_id: str) -> str:
    """Get account information: balance, tariff, next payment."""
    if account_id in ACCOUNTS:
        acc = ACCOUNTS[account_id]
        return (
            f"Аккаунт: {acc['name']}\n"
            f"Тариф: {acc['tariff']}\n"
            f"Баланс: {acc['balance']:.2f} руб.\n"
            f"Следующее списание: {acc['next_payment_date'] or 'Нет'} "
            f"({acc['next_payment_amount']:.2f} руб.)\n"
            f"Автопродление: {'Да' if acc['auto_renewal'] else 'Нет'}"
        )
    return f"Аккаунт '{account_id}' не найден. Доступные для демо: user-123, user-456, user-789"


def get_tariff_info(tariff: str) -> str:
    """Get tariff details: price, storage, features."""
    for name, info in TARIFFS.items():
        if tariff.lower() in name.lower():
            features = "\n".join(f"  - {f}" for f in info["features"])
            return (
                f"Тариф: {name}\n"
                f"Стоимость: {info['price']}\n"
                f"Хранилище: {info['storage']}\n"
                f"Поддержка: {info['support']}\n"
                f"Включено:\n{features}"
            )
    available = ", ".join(TARIFFS.keys())
    return f"Тариф '{tariff}' не найден. Доступные тарифы: {available}"


def get_payment_history(account_id: str) -> str:
    """Get recent payment history for an account."""
    if account_id not in PAYMENT_HISTORY:
        return f"Аккаунт '{account_id}' не найден."

    payments = PAYMENT_HISTORY[account_id]
    if not payments:
        return f"История платежей для '{account_id}' пуста."

    lines = []
    for p in payments:
        lines.append(
            f"  {p['date']} | {p['amount']:.2f} руб. | {p['status']} | {p['description']}"
        )
    return f"История платежей ({account_id}):\n" + "\n".join(lines)


GET_ACCOUNT_INFO_TOOL = {
    "type": "function",
    "function": {
        "name": "get_account_info",
        "description": "Получить информацию об аккаунте: баланс, текущий тариф, дату следующего списания.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "ID аккаунта пользователя (например, user-123)",
                },
            },
            "required": ["account_id"],
        },
    },
}

GET_TARIFF_INFO_TOOL = {
    "type": "function",
    "function": {
        "name": "get_tariff_info",
        "description": "Получить подробную информацию о тарифном плане: стоимость, хранилище, функции.",
        "parameters": {
            "type": "object",
            "properties": {
                "tariff": {
                    "type": "string",
                    "description": "Название тарифа (Базовый, Стандарт, Премиум)",
                },
            },
            "required": ["tariff"],
        },
    },
}

GET_PAYMENT_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_payment_history",
        "description": "Получить историю платежей по аккаунту.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "ID аккаунта пользователя (например, user-123)",
                },
            },
            "required": ["account_id"],
        },
    },
}

BILLING_TOOLS = [GET_ACCOUNT_INFO_TOOL, GET_TARIFF_INFO_TOOL, GET_PAYMENT_HISTORY_TOOL]

BILLING_TOOL_EXECUTORS = {
    "get_account_info": lambda account_id: get_account_info(account_id),
    "get_tariff_info": lambda tariff: get_tariff_info(tariff),
    "get_payment_history": lambda account_id: get_payment_history(account_id),
}
