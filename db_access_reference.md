# Справочник обращений к БД

## Общая информация
- Скрипт создания БД: `initscripts/init_db.sql` (продакшн версия)
- Модули работы с БД: `app/backend/database.py`, `app/backend/*_services.py`

## Таблицы и обращения к ним

### Таблица `users`
**Поля:**
- telegram_id (PRIMARY KEY)
- birth_date
- birth_time
- birth_city
- profession
- job_position
- current_city
- created_at
- updated_at

**Обращения:**
1. **Модуль:** `user_services.py`
   - **Тип:** Запись/Перезапись
   - **Функция:** `create_or_update_user()`
   - **Описание:** Создание или обновление пользователя

2. **Модуль:** `user_services.py`
   - **Тип:** Чтение
   - **Функция:** `get_user_profile()`
   - **Описание:** Получение профиля пользователя

3. **Модуль:** `user_services.py`
   - **Тип:** Перезапись
   - **Функция:** `update_user_profession()`
   - **Описание:** Обновление профессиональных данных пользователя

### Таблица `user_natal_charts`
**Поля:**
- telegram_id (PRIMARY KEY, FOREIGN KEY -> users)
- natal_data
- created_at
- updated_at

**Обращения:**
1. **Модуль:** `chart_services.py`
   - **Тип:** Запись/Перезапись
   - **Функция:** `create_and_save_natal_chart()`
   - **Описание:** Создание и сохранение натальной карты

2. **Модуль:** `chart_services.py`
   - **Тип:** Чтение
   - **Функция:** `get_user_natal_chart()`
   - **Описание:** Получение натальной карты пользователя

### Таблица `psyho_matrix`
**Поля:**
- telegram_id (PRIMARY KEY, FOREIGN KEY -> users)
- matrix_data
- created_at
- updated_at

**Обращения:**
1. **Модуль:** `matrix_services.py`
   - **Тип:** Запись/Перезапись
   - **Функция:** `calculate_and_save_psyho_matrix()`
   - **Описание:** Расчет и сохранение психоматрицы

2. **Модуль:** `matrix_services.py`
   - **Тип:** Чтение
   - **Функция:** `get_user_matrix()`
   - **Описание:** Получение психоматрицы пользователя

### Таблица `natal_predictions`
**Поля:**
- telegram_id (PRIMARY KEY, FOREIGN KEY -> users)
- predictions
- assistant_data
- created_at
- updated_at

**Обращения:**
1. **Модуль:** `prediction_services.py`
   - **Тип:** Запись/Перезапись
   - **Функция:** `generate_and_save_prediction()`
   - **Описание:** Генерация и сохранение предсказания

2. **Модуль:** `prediction_services.py`
   - **Тип:** Чтение
   - **Функция:** `get_user_predictions()`
   - **Описание:** Получение предсказаний пользователя

3. **Модуль:** `prediction_services.py`
   - **Тип:** Чтение
   - **Функция:** `get_todays_prediction()`
   - **Описание:** Получение предсказания на сегодня

### Таблица `biorhythms`
**Поля:**
- telegram_id (PRIMARY KEY, FOREIGN KEY -> users)
- biorhythm_data
- calculation_date
- created_at
- updated_at

**Обращения:**
1. **Модуль:** `biorhythm_services.py`
   - **Тип:** Запись/Перезапись
   - **Функция:** `calculate_and_save_biorhythms()`
   - **Описание:** Расчет и сохранение биоритмов

2. **Модуль:** `biorhythm_services.py`
   - **Тип:** Чтение
   - **Функция:** `get_user_biorhythms()`
   - **Описание:** Получение биоритмов пользователя

### Таблица `user_magic_profiles`
**Поля:**
- telegram_id (PRIMARY KEY, FOREIGN KEY -> users)
- ethical_framework
- social_predispositions
- emotional_architecture
- intellectual_traits
- willpower_profile
- creative_intuitive
- psychological_blueprint
- created_at
- updated_at

**Обращения:**
1. **Модуль:** `magic_profile.py`
   - **Тип:** Запись/Перезапись
   - **Функция:** `MagicProfileService._save_magic_profile_to_db()`
   - **Описание:** Сохранение magic profile в БД

2. **Модуль:** `magic_profile.py`
   - **Тип:** Чтение
   - **Функция:** `MagicProfileService._get_magic_profile_from_db()`
   - **Описание:** Получение magic profile из БД

3. **Модуль:** `magic_profile.py`
   - **Тип:** Удаление
   - **Функция:** `MagicProfileService._delete_magic_profile_from_db()`
   - **Описание:** Удаление magic profile из БД

## Примечания
1. Все операции с БД выполняются через SQLAlchemy ORM
2. Для каждой таблицы определены соответствующие модели в `database.py`
3. Все операции с БД оборачиваются в асинхронные сессии
4. При обновлении скрипта БД (`initscripts/init_db.sql`) необходимо проверить совместимость с существующими модулями