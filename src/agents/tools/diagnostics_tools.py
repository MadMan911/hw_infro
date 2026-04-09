"""Diagnostics agent tools — service status, error lookup, troubleshooting."""

SERVICE_STATUSES = {
    "api": {"status": "online", "uptime": "99.98%", "last_incident": "2026-03-15"},
    "database": {"status": "online", "uptime": "99.95%", "last_incident": "2026-03-20"},
    "billing": {"status": "degraded", "uptime": "98.5%", "last_incident": "2026-04-08"},
    "auth": {"status": "online", "uptime": "99.99%", "last_incident": "2026-02-10"},
    "storage": {"status": "online", "uptime": "99.9%", "last_incident": "2026-03-01"},
    "notifications": {"status": "offline", "uptime": "95.0%", "last_incident": "2026-04-09"},
}

ERROR_CODES = {
    "E-001": {
        "description": "Ошибка подключения к серверу",
        "cause": "Сервер недоступен или нет интернет-соединения",
        "solution": "Проверьте интернет-соединение. Если интернет работает — попробуйте позже.",
    },
    "E-100": {
        "description": "Ошибка аутентификации",
        "cause": "Неверный логин или пароль",
        "solution": "Проверьте правильность ввода. Попробуйте сбросить пароль.",
    },
    "E-200": {
        "description": "Превышен лимит запросов",
        "cause": "Слишком много запросов за короткий период",
        "solution": "Подождите 5 минут и повторите запрос. Для увеличения лимита — обновите тариф.",
    },
    "E-301": {
        "description": "Ошибка загрузки файла",
        "cause": "Файл превышает допустимый размер (100 МБ) или неподдерживаемый формат",
        "solution": "Уменьшите размер файла или сконвертируйте в поддерживаемый формат (PDF, DOCX, JPG, PNG).",
    },
    "E-403": {
        "description": "Ошибка авторизации в биллинг-системе",
        "cause": "Проблема с платёжным токеном или истёк срок сессии биллинга",
        "solution": "Перелогиньтесь в личный кабинет. Если не помогло — обратитесь в поддержку биллинга.",
    },
    "E-500": {
        "description": "Внутренняя ошибка сервера",
        "cause": "Непредвиденная ошибка на стороне сервера",
        "solution": "Попробуйте повторить запрос через несколько минут. Если ошибка повторяется — обратитесь в поддержку.",
    },
    "E-502": {
        "description": "Сервис временно недоступен",
        "cause": "Плановое обслуживание или перегрузка сервера",
        "solution": "Подождите 10-15 минут. Проверьте статус сервисов на status.techcorp.ru.",
    },
}

TROUBLESHOOTING_STEPS = {
    "connection": [
        "Проверьте интернет-соединение (откройте другой сайт)",
        "Перезагрузите роутер",
        "Попробуйте подключиться через мобильную сеть",
        "Очистите DNS-кэш: ipconfig /flushdns (Windows) или sudo dscacheutil -flushcache (Mac)",
        "Если ничего не помогло — обратитесь к интернет-провайдеру",
    ],
    "performance": [
        "Закройте неиспользуемые вкладки и приложения",
        "Очистите кэш приложения/браузера",
        "Проверьте свободное место на диске (нужно минимум 1 ГБ)",
        "Обновите приложение до последней версии",
        "Перезагрузите устройство",
    ],
    "auth": [
        "Проверьте правильность логина и пароля (CapsLock, раскладка)",
        "Попробуйте сбросить пароль через «Забыли пароль?»",
        "Очистите куки и кэш браузера",
        "Попробуйте войти через инкогнито-режим",
        "Если используете 2FA — проверьте синхронизацию времени на устройстве",
    ],
    "crash": [
        "Обновите приложение до последней версии",
        "Очистите кэш и данные приложения",
        "Переустановите приложение",
        "Обновите операционную систему",
        "Если проблема повторяется — соберите логи и отправьте в поддержку",
    ],
}


def check_service_status(service: str) -> str:
    """Check the operational status of a service."""
    service_lower = service.lower()
    if service_lower in SERVICE_STATUSES:
        info = SERVICE_STATUSES[service_lower]
        return (
            f"Сервис '{service}': статус={info['status']}, "
            f"uptime={info['uptime']}, последний инцидент={info['last_incident']}"
        )
    available = ", ".join(SERVICE_STATUSES.keys())
    return f"Сервис '{service}' не найден. Доступные сервисы: {available}"


def lookup_error_code(code: str) -> str:
    """Look up an error code and return description, cause, and solution."""
    code_upper = code.upper()
    if not code_upper.startswith("E-"):
        code_upper = f"E-{code_upper}"

    if code_upper in ERROR_CODES:
        info = ERROR_CODES[code_upper]
        return (
            f"Код: {code_upper}\n"
            f"Описание: {info['description']}\n"
            f"Причина: {info['cause']}\n"
            f"Решение: {info['solution']}"
        )
    return f"Код ошибки '{code}' не найден в базе известных ошибок."


def get_troubleshooting_steps(issue: str) -> str:
    """Get troubleshooting steps for a given issue type."""
    issue_lower = issue.lower()

    for key, steps in TROUBLESHOOTING_STEPS.items():
        if key in issue_lower:
            numbered = [f"{i}. {s}" for i, s in enumerate(steps, 1)]
            return f"Шаги диагностики ({key}):\n" + "\n".join(numbered)

    # Fuzzy matching by keywords
    keyword_map = {
        "connection": ["интернет", "подключение", "сеть", "соединение", "связь"],
        "performance": ["медленно", "тормозит", "долго", "скорость", "зависает"],
        "auth": ["логин", "пароль", "вход", "авторизация", "доступ"],
        "crash": ["падает", "вылетает", "ошибка", "не работает", "крэш"],
    }

    for key, keywords in keyword_map.items():
        if any(kw in issue_lower for kw in keywords):
            steps = TROUBLESHOOTING_STEPS[key]
            numbered = [f"{i}. {s}" for i, s in enumerate(steps, 1)]
            return f"Шаги диагностики ({key}):\n" + "\n".join(numbered)

    return "Не удалось определить тип проблемы. Опишите проблему подробнее."


CHECK_SERVICE_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "check_service_status",
        "description": "Проверить статус работы сервиса (online/degraded/offline, uptime, последний инцидент).",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Название сервиса (api, database, billing, auth, storage, notifications)",
                },
            },
            "required": ["service"],
        },
    },
}

LOOKUP_ERROR_CODE_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_error_code",
        "description": "Найти информацию об ошибке по её коду. Возвращает описание, причину и решение.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Код ошибки (например, E-403, E-500)",
                },
            },
            "required": ["code"],
        },
    },
}

GET_TROUBLESHOOTING_STEPS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_troubleshooting_steps",
        "description": "Получить пошаговую инструкцию по диагностике проблемы указанного типа.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue": {
                    "type": "string",
                    "description": "Тип или описание проблемы (connection, performance, auth, crash или описание)",
                },
            },
            "required": ["issue"],
        },
    },
}

DIAGNOSTICS_TOOLS = [CHECK_SERVICE_STATUS_TOOL, LOOKUP_ERROR_CODE_TOOL, GET_TROUBLESHOOTING_STEPS_TOOL]

DIAGNOSTICS_TOOL_EXECUTORS = {
    "check_service_status": lambda service: check_service_status(service),
    "lookup_error_code": lambda code: lookup_error_code(code),
    "get_troubleshooting_steps": lambda issue: get_troubleshooting_steps(issue),
}
