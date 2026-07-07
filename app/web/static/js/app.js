// web/static/js/app.js
// Daily Tuner - Основной JavaScript код

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let currentPlatform = null;
let currentUserId = null;
let pendingUserId = null;
let pendingPlatform = null;

// ========== УТИЛИТЫ ==========

/**
 * Показать всплывающее сообщение
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;

    // Добавляем цвет в зависимости от типа
    if (type === 'error') {
        toast.style.background = '#dc3545';
    } else if (type === 'success') {
        toast.style.background = '#28a745';
    } else if (type === 'warning') {
        toast.style.background = '#ffc107';
        toast.style.color = '#333';
    } else {
        toast.style.background = '#333';
    }

    document.body.appendChild(toast);
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 3000);
}

/**
 * Форматирование номера телефона
 */
function formatPhoneNumber(input) {
    let value = input.value.replace(/\D/g, '');
    if (value.startsWith('7') || value.startsWith('8')) {
        if (value.length > 1) {
            let formatted = '+7';
            if (value.length > 1) formatted += ' (' + value.substring(1, 4);
            if (value.length > 4) formatted += ') ' + value.substring(4, 7);
            if (value.length > 7) formatted += '-' + value.substring(7, 9);
            if (value.length > 9) formatted += '-' + value.substring(9, 11);
            input.value = formatted;
        } else if (value.length === 1) {
            input.value = '+7';
        }
    }
}

/**
 * Парсинг даты из строки
 */
function parseDate(dateStr) {
    if (!dateStr) return null;
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        return new Date(parts[0], parts[1] - 1, parts[2]);
    }
    return null;
}

/**
 * Форматирование даты для отображения
 */
function formatDateDisplay(dateStr) {
    if (!dateStr) return '';
    const date = parseDate(dateStr);
    if (!date) return dateStr;
    return date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });
}

// ========== АУТЕНТИФИКАЦИЯ ==========

/**
 * Переключение между email и телефоном
 */
function toggleAuthType() {
    const isEmail = document.querySelector('input[name="auth_type"]:checked').value === 'email';
    const emailContainer = document.getElementById('email_container');
    const phoneContainer = document.getElementById('phone_container');

    if (emailContainer) {
        emailContainer.style.display = isEmail ? 'block' : 'none';
    }
    if (phoneContainer) {
        phoneContainer.style.display = isEmail ? 'none' : 'block';
    }
}

/**
 * Вход или регистрация пользователя
 */
async function login() {
    const isEmail = document.querySelector('input[name="auth_type"]:checked').value === 'email';
    const platform = isEmail ? 'email' : 'phone';
    let userId = isEmail
        ? document.getElementById('email_input').value
        : document.getElementById('phone_input').value;

    if (!userId || userId.trim() === '') {
        showToast('Введите email или телефон', 'error');
        return;
    }

    // Нормализация телефона
    if (!isEmail) {
        userId = userId.replace(/\D/g, '');
        if (userId.startsWith('8')) userId = '7' + userId.substring(1);
        if (!userId.startsWith('7')) userId = '7' + userId;
    }

    const resultDiv = document.getElementById('auth-result');
    const loginBtn = document.getElementById('login-btn');

    loginBtn.disabled = true;
    loginBtn.textContent = '⏳ Проверка...';
    resultDiv.innerHTML = '<div class="loading">⏳ Проверка...</div>';

    try {
        const response = await fetch(`/api/validate?platform=${platform}&platform_user_id=${encodeURIComponent(userId)}`);
        const result = await response.json();

        if (result.success) {
            // Пользователь существует - проверяем пароль
            const statusResponse = await fetch(`/api/auth/status?platform=${platform}&platform_user_id=${encodeURIComponent(userId)}`);
            const status = await statusResponse.json();

            if (status.has_password) {
                // Требуем пароль
                pendingPlatform = platform;
                pendingUserId = userId;
                resultDiv.innerHTML = '';
                showPasswordModal(userId);
            } else {
                // Нет пароля - сразу входим
                authenticateUser(platform, userId);
                resultDiv.innerHTML = '';
                showToast('Добро пожаловать!', 'success');
                await loadProfile();
                await checkPasswordStatus();

                // Предлагаем установить пароль
                setTimeout(() => {
                    showSetPasswordModal();
                }, 500);
            }
        } else {
            // Новый пользователь
            authenticateUser(platform, userId);
            resultDiv.innerHTML = '';
            showToast('Добро пожаловать! Установите пароль для защиты профиля', 'info');

            // Предлагаем установить пароль
            setTimeout(() => {
                showSetPasswordModal();
            }, 500);
        }
    } catch(e) {
        resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${e.message}</div>`;
        showToast('Ошибка подключения', 'error');
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Продолжить';
    }
}

/**
 * Аутентификация пользователя (установка сессии)
 */
function authenticateUser(platform, userId) {
    currentPlatform = platform;
    currentUserId = userId;

    // Сохраняем в cookies
    document.cookie = `user_platform=${platform}; path=/; max-age=604800`;
    document.cookie = `user_platform_id=${encodeURIComponent(userId)}; path=/; max-age=604800`;
    document.cookie = `user_authenticated=true; path=/; max-age=604800`;

    // Скрываем форму входа
    document.getElementById('auth-page').classList.add('hidden');

    // Показываем профиль
    document.getElementById('profile-page').classList.remove('hidden');
    document.getElementById('profile-user-id').innerHTML = `👤 ${userId}`;
}

/**
 * Выход из системы
 */
function logout() {
    // Удаляем cookies
    document.cookie = 'user_platform=; path=/; max-age=0';
    document.cookie = 'user_platform_id=; path=/; max-age=0';
    document.cookie = 'user_authenticated=; path=/; max-age=0';
    document.cookie = 'user_name=; path=/; max-age=0';

    currentPlatform = null;
    currentUserId = null;

    // Скрываем все страницы
    document.getElementById('profile-page').classList.add('hidden');
    document.getElementById('activities-page').classList.add('hidden');
    document.getElementById('forecast-page').classList.add('hidden');

    // Показываем форму входа
    document.getElementById('auth-page').classList.remove('hidden');

    // Очищаем поля
    document.getElementById('email_input').value = '';
    const phoneInput = document.getElementById('phone_input');
    if (phoneInput) {
        phoneInput.value = '';
    }

    showToast('Вы вышли из системы', 'info');
}

// ========== ПАРОЛИ ==========

/**
 * Показать модальное окно для ввода пароля
 */
function showPasswordModal(userId) {
    const modal = document.getElementById('password-modal');
    const userInfo = document.getElementById('password-modal-user');
    if (userInfo) {
        userInfo.textContent = `Пользователь: ${userId}`;
    }
    modal.style.display = 'flex';
    document.getElementById('modal-password').value = '';
    document.getElementById('modal-error').innerHTML = '';
    document.getElementById('modal-password').focus();
}

/**
 * Закрыть модальное окно пароля
 */
function closePasswordModal() {
    document.getElementById('password-modal').style.display = 'none';
    pendingUserId = null;
    pendingPlatform = null;
}

/**
 * Показать модальное окно для установки пароля
 */
function showSetPasswordModal() {
    const modal = document.getElementById('set-password-modal');
    modal.style.display = 'flex';
    document.getElementById('set-password').value = '';
    document.getElementById('confirm-password').value = '';
    document.getElementById('set-password-error').innerHTML = '';
    document.getElementById('set-password').focus();
}

/**
 * Закрыть модальное окно установки пароля
 */
function closeSetPasswordModal() {
    document.getElementById('set-password-modal').style.display = 'none';
}

/**
 * Отправить пароль для входа
 */
async function submitPassword() {
    const password = document.getElementById('modal-password').value;
    if (!password) {
        document.getElementById('modal-error').innerHTML = '<div class="error">Введите пароль</div>';
        return;
    }

    const btn = document.getElementById('modal-submit-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Проверка...';

    try {
        const response = await fetch(`/api/validate?platform=${pendingPlatform}&platform_user_id=${encodeURIComponent(pendingUserId)}&password=${encodeURIComponent(password)}`);
        const result = await response.json();

        if (result.success) {
            closePasswordModal();
            authenticateUser(pendingPlatform, pendingUserId);
            document.getElementById('auth-result').innerHTML = '';
            showToast('Вход выполнен успешно', 'success');
            await loadProfile();
            await checkPasswordStatus();
        } else {
            document.getElementById('modal-error').innerHTML = '<div class="error">Неверный пароль</div>';
        }
    } catch(e) {
        document.getElementById('modal-error').innerHTML = `<div class="error">Ошибка: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Войти';
    }
}

/**
 * Установить новый пароль
 */
async function submitSetPassword() {
    const password = document.getElementById('set-password').value;
    const confirm = document.getElementById('confirm-password').value;

    if (password !== confirm) {
        document.getElementById('set-password-error').innerHTML = '<div class="error">Пароли не совпадают</div>';
        return;
    }

    if (password.length < 6) {
        document.getElementById('set-password-error').innerHTML = '<div class="error">Пароль должен быть минимум 6 символов</div>';
        return;
    }

    const btn = document.getElementById('set-password-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Установка...';

    try {
        const response = await fetch('/api/auth/set-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform: currentPlatform,
                platform_user_id: currentUserId,
                password: password
            })
        });
        const result = await response.json();

        if (result.success) {
            closeSetPasswordModal();
            showToast('Пароль успешно установлен', 'success');
            await checkPasswordStatus();
        } else {
            document.getElementById('set-password-error').innerHTML = `<div class="error">${result.error || 'Ошибка установки пароля'}</div>`;
        }
    } catch(e) {
        document.getElementById('set-password-error').innerHTML = `<div class="error">Ошибка: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Установить пароль';
    }
}

/**
 * Проверить статус пароля
 */
async function checkPasswordStatus() {
    try {
        const response = await fetch(`/api/auth/status?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}`);
        const result = await response.json();

        const hasPasswordInfo = document.getElementById('has-password-info');
        const noPasswordInfo = document.getElementById('no-password-info');

        if (result.has_password) {
            if (hasPasswordInfo) hasPasswordInfo.style.display = 'block';
            if (noPasswordInfo) noPasswordInfo.style.display = 'none';
        } else {
            if (hasPasswordInfo) hasPasswordInfo.style.display = 'none';
            if (noPasswordInfo) noPasswordInfo.style.display = 'block';
        }
    } catch(e) {
        console.error('Check password status error:', e);
    }
}

/**
 * Показать форму смены пароля
 */
function showChangePassword() {
    document.getElementById('change-password-form').style.display = 'block';
    document.getElementById('has-password-info').style.display = 'none';
}

/**
 * Отменить смену пароля
 */
function cancelChangePassword() {
    document.getElementById('change-password-form').style.display = 'none';
    checkPasswordStatus();
}

/**
 * Сменить пароль
 */
async function changePassword() {
    const password = document.getElementById('new-password').value;
    const confirm = document.getElementById('new-password-confirm').value;

    if (password !== confirm) {
        showToast('Пароли не совпадают', 'error');
        return;
    }

    if (password.length < 6) {
        showToast('Пароль должен быть минимум 6 символов', 'error');
        return;
    }

    try {
        const response = await fetch('/api/auth/set-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform: currentPlatform,
                platform_user_id: currentUserId,
                password: password
            })
        });
        const result = await response.json();

        if (result.success) {
            showToast('Пароль успешно изменен', 'success');
            cancelChangePassword();
            document.getElementById('new-password').value = '';
            document.getElementById('new-password-confirm').value = '';
            await checkPasswordStatus();
        } else {
            showToast(result.error || 'Ошибка изменения пароля', 'error');
        }
    } catch(e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

// ========== ПРОФИЛЬ ==========

/**
 * Загрузить профиль пользователя
 */
async function loadProfile() {
    try {
        const response = await fetch(`/api/profile?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}`);
        const result = await response.json();

        if (result.success && result.profile) {
            const p = result.profile;
            const birthDateInput = document.getElementById('birth_date');
            const birthTimeInput = document.getElementById('birth_time');
            const birthCityInput = document.getElementById('birth_city');
            const currentCityInput = document.getElementById('current_city');
            const professionInput = document.getElementById('profession');

            if (p.birth_date && birthDateInput) birthDateInput.value = p.birth_date;
            if (p.birth_time && birthTimeInput) birthTimeInput.value = p.birth_time.slice(0, 5);
            if (p.birth_city && birthCityInput) birthCityInput.value = p.birth_city;
            if (p.current_city && currentCityInput) currentCityInput.value = p.current_city;
            if (p.profession && professionInput) professionInput.value = p.profession;
        }
    } catch(e) {
        console.error('Load profile error:', e);
        showToast('Ошибка загрузки профиля', 'error');
    }
}

/**
 * Сохранить профиль
 */
async function saveProfile() {
    const birthDate = document.getElementById('birth_date').value;
    const birthTime = document.getElementById('birth_time').value;
    const birthCity = document.getElementById('birth_city').value;

    if (!birthDate || !birthTime || !birthCity) {
        showToast('Заполните все обязательные поля', 'error');
        return;
    }

    const resultDiv = document.getElementById('profile-result');
    resultDiv.innerHTML = '<div class="loading">⏳ Сохранение...</div>';

    const profile = {
        birth_date: birthDate,
        birth_time: birthTime,
        birth_city: birthCity,
        current_city: document.getElementById('current_city').value || null,
        profession: document.getElementById('profession').value || null
    };

    const requestData = {
        request: {
            platform: currentPlatform,
            platform_user_id: currentUserId
        },
        profile: profile
    };

    try {
        const response = await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        const result = await response.json();

        if (result.success) {
            resultDiv.innerHTML = '<div class="success">✅ Профиль сохранен! Расчеты запущены в фоне.</div>';
            showToast('Профиль успешно сохранен', 'success');
            setTimeout(() => {
                if (resultDiv) resultDiv.innerHTML = '';
            }, 3000);
        } else {
            const errorMsg = result.error || 'Неизвестная ошибка';
            resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${errorMsg}</div>`;
            showToast('Ошибка сохранения профиля', 'error');
        }
    } catch(e) {
        resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${e.message}</div>`;
        showToast('Ошибка сохранения профиля', 'error');
    }
}

/**
 * Проверить заполненность профиля
 */
async function checkProfile() {
    const resultDiv = document.getElementById('profile-result');
    resultDiv.innerHTML = '<div class="loading">🔍 Проверка...</div>';

    try {
        const response = await fetch(`/api/validate?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}`);
        const result = await response.json();

        if (result.success) {
            let html = '<div class="result">';
            html += '<strong>📊 Статус профиля</strong><br><br>';

            if (result.has_complete_data) {
                html += '<div class="success">✅ Данные полные</div>';
            } else {
                html += '<div class="warning">⚠️ Данные неполные</div>';
            }

            if (result.missing_fields && result.missing_fields.length) {
                html += '<br><strong>📋 Отсутствует:</strong><br>';
                html += result.missing_fields.map(f => '• ' + f).join('<br>');
            }

            html += '</div>';
            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = `<div class="error">❌ ${result.error || 'Ошибка'}</div>`;
        }
    } catch(e) {
        resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${e.message}</div>`;
    }
}

// ========== РЕКОМЕНДАЦИИ ==========

/**
 * Получить рекомендации на день
 */
async function getRecommendations() {
    const resultDiv = document.getElementById('activities-result');
    const targetDate = document.getElementById('target_date').value || new Date().toISOString().split('T')[0];

    resultDiv.innerHTML = '<div class="loading">🎯 Расчет рекомендаций...</div>';

    try {
        const response = await fetch(`/api/recommendations?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}&date=${targetDate}`);
        const result = await response.json();

        if (result.success) {
            let html = '<div class="result">';
            html += `<strong>📅 ${result.date_formatted || formatDateDisplay(targetDate)}</strong>`;

            const energyPercent = result.energy_percent || 50;
            html += '<div class="energy-bar">';
            html += `<div class="energy-fill" style="width: ${energyPercent}%">`;
            html += `${energyPercent}%`;
            html += '</div></div>';

            if (result.summary) {
                html += `<div style="margin: 10px 0;">📊 ${result.summary}</div>`;
            }

            html += '<strong>✅ Рекомендации:</strong><br>';
            html += '<div style="margin-top: 10px;">';

            const recommendationsText = result.recommendations_text || 'Нет рекомендаций на этот день';
            html += recommendationsText.replace(/\n/g, '<br>');
            html += '</div>';

            if (result.warnings && result.warnings !== '✅ Особых предостережений нет') {
                html += `<br><div class="warning">⚠️ ${result.warnings}</div>`;
            }

            html += '</div>';
            resultDiv.innerHTML = html;
        } else {
            const errorMsg = result.error || 'Ошибка получения рекомендаций';
            resultDiv.innerHTML = `<div class="error">❌ ${errorMsg}</div>`;
        }
    } catch(e) {
        resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${e.message}</div>`;
    }
}

// ========== ПРОГНОЗ ==========

/**
 * Получить прогноз на несколько дней
 */
async function getForecast() {
    const resultDiv = document.getElementById('forecast-result');
    const days = parseInt(document.getElementById('forecast_days').value);

    resultDiv.innerHTML = '<div class="loading">🔮 Генерация прогноза...</div>';

    let forecastHtml = '<div class="result">';
    forecastHtml += '<strong>📊 Энергетический прогноз</strong><br><br>';

    const today = new Date();
    let hasErrors = false;

    for (let i = 1; i <= days; i++) {
        const date = new Date(today);
        date.setDate(today.getDate() + i);
        const dateStr = date.toISOString().split('T')[0];
        const weekday = date.toLocaleDateString('ru-RU', { weekday: 'long' });
        const dayMonth = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });

        try {
            const response = await fetch(`/api/recommendations?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}&date=${dateStr}`);
            const result = await response.json();

            if (result.success) {
                const energyPercent = result.energy_percent || 50;
                let energyIcon = energyPercent > 70 ? '🚀' : (energyPercent > 40 ? '⚡' : '😴');

                forecastHtml += `<div style="margin: 15px 0; padding: 15px; background: #f5f5f5; border-radius: 10px;">`;
                forecastHtml += `<strong>${weekday}, ${dayMonth}</strong><br>`;
                forecastHtml += `${energyIcon} Энергия: ${energyPercent}%<br>`;

                // Добавляем первую рекомендацию
                const recommendationsText = result.recommendations_text || '';
                const firstRec = recommendationsText.split('\n')[0];
                if (firstRec) {
                    const shortRec = firstRec.length > 60 ? firstRec.substring(0, 60) + '...' : firstRec;
                    forecastHtml += `💡 ${shortRec}`;
                }
                forecastHtml += `</div>`;
            } else {
                forecastHtml += `<div style="margin: 15px 0; padding: 15px; background: #fee; border-radius: 10px;">❌ Ошибка для ${dayMonth}</div>`;
                hasErrors = true;
            }
        } catch(e) {
            forecastHtml += `<div style="margin: 15px 0; padding: 15px; background: #fee; border-radius: 10px;">❌ Ошибка для ${dayMonth}: ${e.message}</div>`;
            hasErrors = true;
        }
    }

    if (hasErrors) {
        forecastHtml += `<br><div class="warning">⚠️ Некоторые дни не удалось загрузить. Попробуйте позже.</div>`;
    }

    forecastHtml += '</div>';
    resultDiv.innerHTML = forecastHtml;
}

// ========== НАВИГАЦИЯ ==========

/**
 * Показать выбранную страницу
 */
function showPage(page) {
    const profilePage = document.getElementById('profile-page');
    const activitiesPage = document.getElementById('activities-page');
    const forecastPage = document.getElementById('forecast-page');

    // Скрываем все
    if (profilePage) profilePage.classList.add('hidden');
    if (activitiesPage) activitiesPage.classList.add('hidden');
    if (forecastPage) forecastPage.classList.add('hidden');

    // Показываем выбранную
    if (page === 'profile' && profilePage) {
        profilePage.classList.remove('hidden');
    } else if (page === 'activities' && activitiesPage) {
        activitiesPage.classList.remove('hidden');
    } else if (page === 'forecast' && forecastPage) {
        forecastPage.classList.remove('hidden');
    }
}

// ========== ВОССТАНОВЛЕНИЕ СЕССИИ ==========

/**
 * Восстановить сессию из cookies
 */

function restoreSession() {
    const cookies = document.cookie.split(';');
    let platform = null;
    let platformId = null;
    let authenticated = false;
    let name = null;
    let email = null;

    cookies.forEach(cookie => {
        const [key, value] = cookie.trim().split('=');
        if (key === 'user_platform') platform = decodeURIComponent(value);
        if (key === 'user_platform_id') platformId = decodeURIComponent(value);
        if (key === 'user_authenticated') authenticated = value === 'true';
        if (key === 'user_name') name = decodeURIComponent(value);
        if (key === 'user_email') email = decodeURIComponent(value);
    });

    if (authenticated && platform && platformId) {
        currentPlatform = platform;
        currentUserId = platformId;  // ← Это yandex_id для Яндекса!

        // Для отображения используем email если это Яндекс
        let displayName = name || platformId;
        if (platform === 'yandex' && email) {
            displayName = email;  // Показываем email, а не yandex_id
        }

        document.getElementById('auth-page').classList.add('hidden');
        document.getElementById('profile-page').classList.remove('hidden');
        document.getElementById('profile-user-id').innerHTML = `👤 ${displayName}`;

        loadProfile();
        checkPasswordStatus();
        showToast('Сессия восстановлена', 'success');
        return true;
    }
    return false;
}

// ========== ИНИЦИАЛИЗАЦИЯ ==========

/**
 * Инициализация приложения
 */
function initApp() {
    // Устанавливаем сегодняшнюю дату для поля даты
    const today = new Date();
    const formattedDate = today.toISOString().split('T')[0];
    const targetDateInput = document.getElementById('target_date');
    if (targetDateInput) {
        targetDateInput.value = formattedDate;
    }

    // Настройка переключения типа аутентификации
    toggleAuthType();

    // Настройка форматирования телефона
    const phoneInput = document.getElementById('phone_input');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            formatPhoneNumber(this);
        });
    }

    // Восстановление сессии
    const sessionRestored = restoreSession();

    // Если сессия не восстановлена, показываем форму входа
    if (!sessionRestored) {
        document.getElementById('auth-page').classList.remove('hidden');
    }

    // Обработка Enter в полях ввода
    const emailInput = document.getElementById('email_input');
    if (emailInput) {
        emailInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') login();
        });
    }

    if (phoneInput) {
        phoneInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') login();
        });
    }

    // Обработка Enter в модальных окнах
    const modalPassword = document.getElementById('modal-password');
    if (modalPassword) {
        modalPassword.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') submitPassword();
        });
    }

    const setPassword = document.getElementById('set-password');
    if (setPassword) {
        setPassword.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') submitSetPassword();
        });
    }

    console.log('Daily Tuner initialized');
    console.log('Authenticated:', !!currentUserId);
}

// Запускаем инициализацию после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Экспортируем функции для использования в HTML
window.showToast = showToast;
window.toggleAuthType = toggleAuthType;
window.login = login;
window.logout = logout;
window.showPage = showPage;
window.saveProfile = saveProfile;
window.checkProfile = checkProfile;
window.getRecommendations = getRecommendations;
window.getForecast = getForecast;
window.submitPassword = submitPassword;
window.closePasswordModal = closePasswordModal;
window.submitSetPassword = submitSetPassword;
window.closeSetPasswordModal = closeSetPasswordModal;
window.showChangePassword = showChangePassword;
window.cancelChangePassword = cancelChangePassword;
window.changePassword = changePassword;
window.showSetPasswordForm = showSetPasswordModal;
window.formatPhoneNumber = formatPhoneNumber;
window.loadProfile = loadProfile;
window.checkPasswordStatus = checkPasswordStatus;
