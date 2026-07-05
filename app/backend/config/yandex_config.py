# backend/config/yandex_config.py (новый файл)
import os
import logging

logger = logging.getLogger(__name__)


def read_secret_file(file_path: str) -> str:
    """Безопасно читает секрет из файла"""
    if not file_path:
        return ""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Failed to read secret from {file_path}: {e}")
        return ""


def load_yandex_config() -> dict:
    """
    Загружает конфигурацию Яндекс OAuth из секретов или переменных окружения

    Приоритет:
    1. Файлы секретов (YANDEX_*_FILE)
    2. Переменные окружения (YANDEX_*)
    """
    config = {
        'client_id': '',
        'client_secret': '',
        'redirect_uri': '',
    }

    # Пытаемся загрузить из файлов секретов
    client_id_file = os.getenv('YANDEX_CLIENT_ID_FILE')
    if client_id_file:
        config['client_id'] = read_secret_file(client_id_file)

    client_secret_file = os.getenv('YANDEX_CLIENT_SECRET_FILE')
    if client_secret_file:
        config['client_secret'] = read_secret_file(client_secret_file)

    redirect_uri_file = os.getenv('YANDEX_REDIRECT_URI_FILE')
    if redirect_uri_file:
        config['redirect_uri'] = read_secret_file(redirect_uri_file)

    # Если файлы не найдены, пробуем переменные окружения
    if not config['client_id']:
        config['client_id'] = os.getenv('YANDEX_CLIENT_ID', '')
    if not config['client_secret']:
        config['client_secret'] = os.getenv('YANDEX_CLIENT_SECRET', '')
    if not config['redirect_uri']:
        config['redirect_uri'] = os.getenv('YANDEX_REDIRECT_URI', '')

    # Логируем статус (без вывода самих секретов!)
    if config['client_id'] and config['client_secret'] and config['redirect_uri']:
        logger.info("✅ Yandex OAuth configuration loaded")
    else:
        missing = []
        if not config['client_id']: missing.append('client_id')
        if not config['client_secret']: missing.append('client_secret')
        if not config['redirect_uri']: missing.append('redirect_uri')
        logger.warning(f"⚠️ Yandex OAuth missing: {', '.join(missing)}")

    return config


# Загружаем конфигурацию при импорте
YANDEX_CONFIG = load_yandex_config()