"""web_api.py Веб-интерфейс для Daily Tuner API (регистрация по email/phone)"""
import logging
from datetime import date as date_class
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .web_client import web_client, AuthPlatform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

web_app = FastAPI(title="Daily Tuner Web Interface", version="1.0.0")


@web_app.get("/", response_class=HTMLResponse)
async def index():
    """Улучшенная главная страница с поддержкой паролей"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Tuner - Персональные рекомендации</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
            }
            .card {
                background: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
            .card:hover {
                transform: translateY(-2px);
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 24px;
            }
            h2 {
                color: #555;
                margin-bottom: 15px;
                font-size: 18px;
            }
            h3 {
                color: #666;
                margin-bottom: 10px;
                font-size: 16px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            input, select {
                width: 100%;
                padding: 14px;
                margin: 8px 0 20px;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                font-size: 16px;
                transition: border-color 0.3s ease;
            }
            input:focus, select:focus {
                outline: none;
                border-color: #667eea;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 30px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                margin-top: 10px;
                transition: all 0.3s ease;
            }
            button:hover { 
                opacity: 0.9; 
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            .result {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 20px;
                margin-top: 20px;
                font-size: 14px;
                line-height: 1.5;
            }
            .nav {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            .nav-btn {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                margin: 0;
                padding: 12px;
                flex: 1;
                min-width: 100px;
            }
            .error {
                background: #fee;
                color: #c00;
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
                border-left: 4px solid #c00;
            }
            .success {
                background: #e8f5e9;
                color: #2e7d32;
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
                border-left: 4px solid #2e7d32;
            }
            .warning {
                background: #fff3e0;
                color: #e65100;
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
                border-left: 4px solid #ff9800;
            }
            .info {
                background: #e3f2fd;
                color: #1565c0;
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
                border-left: 4px solid #2196f3;
            }
            .auth-type {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
            }
            .auth-type label {
                display: flex;
                align-items: center;
                gap: 8px;
                cursor: pointer;
                padding: 10px;
                border-radius: 10px;
                transition: background 0.3s ease;
            }
            .auth-type label:hover {
                background: #f0f0f0;
            }
            .auth-type input {
                width: auto;
                margin: 0;
            }
            .toast {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #333;
                color: white;
                padding: 12px 20px;
                border-radius: 10px;
                z-index: 1000;
                animation: slideIn 0.3s ease;
            }
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            .energy-bar {
                background: #e0e0e0;
                border-radius: 10px;
                overflow: hidden;
                margin: 15px 0;
            }
            .energy-fill {
                background: linear-gradient(90deg, #4caf50, #ff9800, #f44336);
                height: 30px;
                transition: width 0.5s ease;
                display: flex;
                align-items: center;
                justify-content: flex-end;
                padding-right: 10px;
                color: white;
                font-weight: bold;
            }
            .loading {
                text-align: center;
                padding: 20px;
            }
            .modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1001;
                justify-content: center;
                align-items: center;
            }
            .modal-content {
                background: white;
                border-radius: 20px;
                padding: 30px;
                max-width: 400px;
                width: 90%;
                margin: 20px;
            }
            hr {
                margin: 20px 0;
                border: none;
                border-top: 1px solid #e0e0e0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nav">
                <button class="nav-btn" onclick="showPage('profile')">📝 Профиль</button>
                <button class="nav-btn" onclick="showPage('activities')">⭐ Рекомендации</button>
                <button class="nav-btn" onclick="showPage('forecast')">📊 Прогноз</button>
                <button class="nav-btn" onclick="logout()">🚪 Выйти</button>
            </div>

            <!-- Регистрация/Вход -->
            <div id="auth-page" class="card">
                <h1>🔐 Добро пожаловать в Daily Tuner</h1>
                <div class="subtitle">Персональные рекомендации на основе вашей натальной карты</div>

                <div class="auth-type">
                    <label>
                        <input type="radio" name="auth_type" value="email" checked onchange="toggleAuthType()">
                        📧 Email
                    </label>
                    <label>
                        <input type="radio" name="auth_type" value="phone" onchange="toggleAuthType()">
                        📱 Телефон
                    </label>
                </div>

                <div id="email_container">
                    <input type="email" id="email_input" placeholder="example@mail.com" autocomplete="email">
                </div>
                <div id="phone_container" style="display:none">
                    <input type="tel" id="phone_input" placeholder="+7 (999) 123-45-67" autocomplete="tel">
                </div>

                <button onclick="login()" id="login-btn">Продолжить</button>
                <div id="auth-result"></div>
            </div>

            <!-- Модальное окно для ввода пароля -->
            <div id="password-modal" class="modal">
                <div class="modal-content">
                    <h2>🔒 Введите пароль</h2>
                    <p id="password-modal-user" style="margin-bottom: 15px; color: #666;"></p>
                    <input type="password" id="modal-password" placeholder="Пароль" autocomplete="current-password">
                    <button onclick="submitPassword()" id="modal-submit-btn">Войти</button>
                    <button onclick="closePasswordModal()" style="background: #6c757d; margin-top: 10px;">Отмена</button>
                    <div id="modal-error" style="margin-top: 10px;"></div>
                </div>
            </div>

            <!-- Модальное окно для установки пароля -->
            <div id="set-password-modal" class="modal">
                <div class="modal-content">
                    <h2>🔐 Установите пароль</h2>
                    <p style="margin-bottom: 15px; color: #666;">Для защиты вашего профиля установите пароль</p>
                    <input type="password" id="set-password" placeholder="Новый пароль (мин. 6 символов)" autocomplete="new-password">
                    <input type="password" id="confirm-password" placeholder="Подтвердите пароль" autocomplete="new-password" style="margin-top: 10px;">
                    <button onclick="submitSetPassword()" id="set-password-btn">Установить пароль</button>
                    <button onclick="closeSetPasswordModal()" style="background: #6c757d; margin-top: 10px;">Пропустить (позже)</button>
                    <div id="set-password-error" style="margin-top: 10px;"></div>
                </div>
            </div>

            <!-- Профиль -->
            <div id="profile-page" class="card" style="display:none">
                <h1>📝 Личные данные</h1>
                <div class="subtitle" id="profile-user-id"></div>

                <label>📅 Дата рождения *</label>
                <input type="date" id="birth_date" required>

                <label>⏰ Время рождения *</label>
                <input type="time" id="birth_time" required>

                <label>🌍 Город рождения *</label>
                <input type="text" id="birth_city" placeholder="Например: Moscow" value="Moscow" required>

                <label>🏙️ Текущий город</label>
                <input type="text" id="current_city" placeholder="Необязательно">

                <label>💼 Профессия</label>
                <input type="text" id="profession" placeholder="Необязательно">

                <div style="display: flex; gap: 10px;">
                    <button onclick="saveProfile()" style="flex: 2">💾 Сохранить</button>
                    <button onclick="checkProfile()" style="flex: 1; background:#6c757d">🔍 Проверить</button>
                </div>

                <hr>

                <div id="password-section">
                    <h3>🔒 Безопасность</h3>
                    <div id="has-password-info" style="display: none;">
                        <div class="info">🔐 Пароль установлен</div>
                        <button onclick="showChangePassword()" style="background: #6c757d; margin-top: 10px;">🔄 Сменить пароль</button>
                    </div>

                    <div id="no-password-info" style="display: none;">
                        <div class="warning">⚠️ Пароль не установлен</div>
                        <button onclick="showSetPasswordForm()" style="background: #2196f3; margin-top: 10px;">🔒 Установить пароль</button>
                    </div>

                    <div id="change-password-form" style="display: none;">
                        <input type="password" id="new-password" placeholder="Новый пароль (мин. 6 символов)">
                        <input type="password" id="new-password-confirm" placeholder="Подтвердите пароль">
                        <button onclick="changePassword()">💾 Сохранить новый пароль</button>
                        <button onclick="cancelChangePassword()" style="background: #6c757d">Отмена</button>
                    </div>
                </div>

                <div id="profile-result"></div>
            </div>

            <!-- Рекомендации -->
            <div id="activities-page" class="card" style="display:none">
                <h1>⭐ Рекомендации на день</h1>
                <div class="subtitle">Активности, которые принесут максимальную пользу</div>

                <label>📅 Дата</label>
                <input type="date" id="target_date">
                <button onclick="getRecommendations()">🎯 Получить рекомендации</button>

                <div id="activities-result"></div>
            </div>

            <!-- Прогноз -->
            <div id="forecast-page" class="card" style="display:none">
                <h1>📊 Энергетический прогноз</h1>
                <div class="subtitle">Ваше состояние на ближайшие дни</div>

                <label>📅 Период</label>
                <select id="forecast_days">
                    <option value="1">Завтра</option>
                    <option value="3">Следующие 3 дня</option>
                    <option value="7">Неделя</option>
                </select>
                <button onclick="getForecast()">🔮 Показать прогноз</button>

                <div id="forecast-result"></div>
            </div>
        </div>

        <script>
            let currentPlatform = null;
            let currentUserId = null;
            let pendingUserId = null;
            let pendingPlatform = null;

            // Восстановление сессии из localStorage
            function restoreSession() {
                const savedPlatform = localStorage.getItem('daily_tuner_platform');
                const savedUserId = localStorage.getItem('daily_tuner_user_id');
                const savedAuthenticated = localStorage.getItem('daily_tuner_authenticated');

                if (savedPlatform && savedUserId && savedAuthenticated === 'true') {
                    currentPlatform = savedPlatform;
                    currentUserId = savedUserId;
                    document.getElementById('auth-page').style.display = 'none';
                    document.getElementById('profile-page').style.display = 'block';
                    document.getElementById('profile-user-id').innerHTML = `👤 ${savedUserId}`;
                    loadProfile();
                    checkPasswordStatus();
                    showToast('Сессия восстановлена', 'success');
                }
            }

            function showToast(message, type = 'info') {
                const toast = document.createElement('div');
                toast.className = 'toast';
                toast.textContent = message;
                document.body.appendChild(toast);
                setTimeout(() => toast.remove(), 3000);
            }

            function toggleAuthType() {
                const isEmail = document.querySelector('input[name="auth_type"]:checked').value === 'email';
                document.getElementById('email_container').style.display = isEmail ? 'block' : 'none';
                document.getElementById('phone_container').style.display = isEmail ? 'none' : 'block';
            }

            function formatPhoneNumber(input) {
                let value = input.value.replace(/\\D/g, '');
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

            if(document.getElementById('phone_input')) {
                document.getElementById('phone_input').addEventListener('input', function(e) {
                    formatPhoneNumber(this);
                });
            }

            function showPage(page) {
                document.getElementById('profile-page').style.display = page === 'profile' ? 'block' : 'none';
                document.getElementById('activities-page').style.display = page === 'activities' ? 'block' : 'none';
                document.getElementById('forecast-page').style.display = page === 'forecast' ? 'block' : 'none';
            }

            // Парольные модальные окна
            function showPasswordModal(userId) {
                document.getElementById('password-modal-user').textContent = `Пользователь: ${userId}`;
                document.getElementById('password-modal').style.display = 'flex';
                document.getElementById('modal-password').value = '';
                document.getElementById('modal-error').innerHTML = '';
                document.getElementById('modal-password').focus();
            }

            function closePasswordModal() {
                document.getElementById('password-modal').style.display = 'none';
                pendingUserId = null;
                pendingPlatform = null;
            }

            function showSetPasswordModal() {
                document.getElementById('set-password-modal').style.display = 'flex';
                document.getElementById('set-password').value = '';
                document.getElementById('confirm-password').value = '';
                document.getElementById('set-password-error').innerHTML = '';
                document.getElementById('set-password').focus();
            }

            function closeSetPasswordModal() {
                document.getElementById('set-password-modal').style.display = 'none';
            }

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
                        currentPlatform = pendingPlatform;
                        currentUserId = pendingUserId;

                        localStorage.setItem('daily_tuner_platform', pendingPlatform);
                        localStorage.setItem('daily_tuner_user_id', pendingUserId);
                        localStorage.setItem('daily_tuner_authenticated', 'true');

                        document.getElementById('auth-page').style.display = 'none';
                        document.getElementById('profile-page').style.display = 'block';
                        document.getElementById('profile-user-id').innerHTML = `👤 ${pendingUserId}`;
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

                if (!isEmail) {
                    userId = userId.replace(/\\D/g, '');
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
                            currentPlatform = platform;
                            currentUserId = userId;
                            localStorage.setItem('daily_tuner_platform', platform);
                            localStorage.setItem('daily_tuner_user_id', userId);
                            localStorage.setItem('daily_tuner_authenticated', 'true');

                            document.getElementById('auth-page').style.display = 'none';
                            document.getElementById('profile-page').style.display = 'block';
                            document.getElementById('profile-user-id').innerHTML = `👤 ${userId}`;
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
                        currentPlatform = platform;
                        currentUserId = userId;
                        localStorage.setItem('daily_tuner_platform', platform);
                        localStorage.setItem('daily_tuner_user_id', userId);
                        localStorage.setItem('daily_tuner_authenticated', 'true');

                        document.getElementById('auth-page').style.display = 'none';
                        document.getElementById('profile-page').style.display = 'block';
                        document.getElementById('profile-user-id').innerHTML = `🆕 Новый пользователь: ${userId}`;
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

            function logout() {
                localStorage.removeItem('daily_tuner_platform');
                localStorage.removeItem('daily_tuner_user_id');
                localStorage.removeItem('daily_tuner_authenticated');
                currentPlatform = null;
                currentUserId = null;

                document.getElementById('profile-page').style.display = 'none';
                document.getElementById('activities-page').style.display = 'none';
                document.getElementById('forecast-page').style.display = 'none';
                document.getElementById('auth-page').style.display = 'block';

                document.getElementById('email_input').value = '';
                if(document.getElementById('phone_input')) {
                    document.getElementById('phone_input').value = '';
                }

                showToast('Вы вышли из системы', 'info');
            }

            async function checkPasswordStatus() {
                try {
                    const response = await fetch(`/api/auth/status?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}`);
                    const result = await response.json();

                    if (result.has_password) {
                        document.getElementById('has-password-info').style.display = 'block';
                        document.getElementById('no-password-info').style.display = 'none';
                    } else {
                        document.getElementById('has-password-info').style.display = 'none';
                        document.getElementById('no-password-info').style.display = 'block';
                    }
                } catch(e) {
                    console.error('Check password status error:', e);
                }
            }

            function showSetPasswordForm() {
                showSetPasswordModal();
            }

            function showChangePassword() {
                document.getElementById('change-password-form').style.display = 'block';
                document.getElementById('has-password-info').style.display = 'none';
            }

            function cancelChangePassword() {
                document.getElementById('change-password-form').style.display = 'none';
                checkPasswordStatus();
            }

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
                        
                        // Обновляем статус после смены пароля
                        await checkPasswordStatus();
                    } else {
                        showToast(result.error || 'Ошибка изменения пароля', 'error');
                    }
                } catch(e) {
                    showToast('Ошибка: ' + e.message, 'error');
                }
            }

            async function loadProfile() {
                try {
                    const response = await fetch(`/api/profile?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}`);
                    const result = await response.json();

                    if (result.success && result.profile) {
                        const p = result.profile;
                        if (p.birth_date) document.getElementById('birth_date').value = p.birth_date;
                        if (p.birth_time) document.getElementById('birth_time').value = p.birth_time.slice(0,5);
                        if (p.birth_city) document.getElementById('birth_city').value = p.birth_city;
                        if (p.current_city) document.getElementById('current_city').value = p.current_city;
                        if (p.profession) document.getElementById('profession').value = p.profession;
                    }
                } catch(e) {
                    console.error('Load profile error:', e);
                }
            }

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
                        setTimeout(() => resultDiv.innerHTML = '', 3000);
                    } else {
                        resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + (result.error || 'Неизвестная ошибка') + '</div>';
                    }
                } catch(e) {
                    resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + e.message + '</div>';
                }
            }

            async function checkProfile() {
                const resultDiv = document.getElementById('profile-result');
                resultDiv.innerHTML = '<div class="loading">🔍 Проверка...</div>';

                try {
                    const response = await fetch(`/api/validate?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}`);
                    const result = await response.json();

                    if (result.success) {
                        let html = '<div class="result">';
                        html += '<strong>📊 Статус профиля</strong><br><br>';
                        html += result.has_complete_data ? '<div class="success">✅ Данные полные</div>' : '<div class="warning">⚠️ Данные неполные</div>';
                        if (result.missing_fields && result.missing_fields.length) {
                            html += '<br><strong>📋 Отсутствует:</strong><br>';
                            html += result.missing_fields.map(f => '• ' + f).join('<br>');
                        }
                        html += '</div>';
                        resultDiv.innerHTML = html;
                    } else {
                        resultDiv.innerHTML = '<div class="error">❌ ' + (result.error || 'Ошибка') + '</div>';
                    }
                } catch(e) {
                    resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + e.message + '</div>';
                }
            }

            async function getRecommendations() {
                const resultDiv = document.getElementById('activities-result');
                const targetDate = document.getElementById('target_date').value || new Date().toISOString().split('T')[0];

                resultDiv.innerHTML = '<div class="loading">🎯 Расчет рекомендаций...</div>';

                try {
                    const response = await fetch(`/api/recommendations?platform=${currentPlatform}&platform_user_id=${encodeURIComponent(currentUserId)}&date=${targetDate}`);
                    const result = await response.json();

                    if (result.success) {
                        let html = '<div class="result">';
                        html += '<strong>📅 ' + result.date_formatted + '</strong>';

                        const energyPercent = result.energy_percent || 50;
                        html += '<div class="energy-bar">';
                        html += `<div class="energy-fill" style="width: ${energyPercent}%">`;
                        html += `${energyPercent}%`;
                        html += '</div></div>';

                        html += '<strong>✅ Рекомендации:</strong><br>';
                        html += '<div style="margin-top: 10px;">';
                        html += (result.recommendations_text || 'Нет рекомендаций').replace(/\\n/g, '<br>');
                        html += '</div>';

                        if (result.warnings) {
                            html += '<br><div class="warning">⚠️ ' + result.warnings + '</div>';
                        }

                        html += '</div>';
                        resultDiv.innerHTML = html;
                    } else {
                        resultDiv.innerHTML = '<div class="error">❌ ' + (result.error || 'Ошибка') + '</div>';
                    }
                } catch(e) {
                    resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + e.message + '</div>';
                }
            }

            async function getForecast() {
                const resultDiv = document.getElementById('forecast-result');
                const days = parseInt(document.getElementById('forecast_days').value);

                resultDiv.innerHTML = '<div class="loading">🔮 Генерация прогноза...</div>';

                let forecastHtml = '<div class="result">';
                forecastHtml += '<strong>📊 Энергетический прогноз</strong><br><br>';

                const today = new Date();

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

                            forecastHtml += `<div style="margin: 15px 0; padding: 10px; background: #f5f5f5; border-radius: 10px;">`;
                            forecastHtml += `<strong>${weekday}, ${dayMonth}</strong><br>`;
                            forecastHtml += `${energyIcon} Энергия: ${energyPercent}%<br>`;

                            const firstRec = (result.recommendations_text || '').split('\\n')[0];
                            if (firstRec) {
                                forecastHtml += `💡 ${firstRec.substring(0, 60)}${firstRec.length > 60 ? '...' : ''}`;
                            }
                            forecastHtml += `</div>`;
                        }
                    } catch(e) {
                        forecastHtml += `<div style="margin: 15px 0; padding: 10px; background: #fee; border-radius: 10px;">❌ Ошибка для ${dayMonth}</div>`;
                    }
                }

                forecastHtml += '</div>';
                resultDiv.innerHTML = forecastHtml;
            }

            // Инициализация
            const today = new Date();
            const formattedDate = today.toISOString().split('T')[0];
            if(document.getElementById('target_date')) {
                document.getElementById('target_date').value = formattedDate;
            }
            toggleAuthType();
            restoreSession();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# ========== API ЭНДПОИНТЫ (прокси к backend) ==========

@web_app.post("/api/profile")
async def save_profile(request: Request):
    """Сохранение профиля"""
    try:
        data = await request.json()
        req_data = data.get("request", {})
        profile_data = data.get("profile", {})

        platform = req_data.get("platform")
        platform_user_id = req_data.get("platform_user_id")

        if not platform or not platform_user_id:
            return JSONResponse({"success": False, "error": "platform and platform_user_id required"})

        try:
            auth_platform = AuthPlatform(platform)
        except ValueError:
            return JSONResponse({"success": False, "error": f"Invalid platform: {platform}"})

        result = await web_client.save_user_profile(
            platform=auth_platform,
            platform_user_id=platform_user_id,
            **profile_data
        )
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Save profile error: {e}")
        return JSONResponse({"success": False, "error": str(e)})


@web_app.get("/api/validate")
async def validate_user(platform: str, platform_user_id: str, password: str = None):
    """Проверка профиля (с опциональной проверкой пароля)"""
    try:
        auth_platform = AuthPlatform(platform)
        result = await web_client.validate_user(auth_platform, platform_user_id, password)
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@web_app.get("/api/profile")
async def get_profile(platform: str, platform_user_id: str):
    """Получение профиля"""
    try:
        auth_platform = AuthPlatform(platform)
        result = await web_client.get_user_profile(auth_platform, platform_user_id)
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@web_app.get("/api/recommendations")
async def get_recommendations(platform: str, platform_user_id: str, date: str = None):
    """Получение рекомендаций"""
    try:
        auth_platform = AuthPlatform(platform)
        target_date = date_class.fromisoformat(date) if date else None

        result = await web_client.get_recommendations(
            platform=auth_platform,
            platform_user_id=platform_user_id,
            target_date=target_date
        )
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@web_app.get("/api/forecast")
async def get_forecast(
        platform: str,
        platform_user_id: str,
        forecast_date: str = None,
        force_recalculate: bool = False
):
    """Получение прогноза на указанную дату"""
    try:
        auth_platform = AuthPlatform(platform)
        target_date = date_class.fromisoformat(forecast_date) if forecast_date else None

        result = await web_client.get_recommendations(
            platform=auth_platform,
            platform_user_id=platform_user_id,
            target_date=target_date
        )
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


# ========== ПРОКСИ ДЛЯ ПАРОЛЬНЫХ ЭНДПОИНТОВ ==========

@web_app.post("/api/auth/set-password")
async def set_password(request: Request):
    """Установка пароля (прокси к backend)"""
    try:
        data = await request.json()
        result = await web_client.set_password(
            platform=AuthPlatform(data.get("platform")),
            platform_user_id=data.get("platform_user_id"),
            password=data.get("password")
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@web_app.post("/api/auth/login")
async def login(request: Request):
    """Вход с паролем (прокси к backend)"""
    try:
        data = await request.json()
        result = await web_client.login(
            platform=AuthPlatform(data.get("platform")),
            platform_user_id=data.get("platform_user_id"),
            password=data.get("password")
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@web_app.get("/api/auth/status")
async def auth_status(platform: str, platform_user_id: str):
    """Статус аутентификации (прокси к backend)"""
    try:
        result = await web_client.get_auth_status(
            platform=AuthPlatform(platform),
            platform_user_id=platform_user_id
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@web_app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("web_api:web_app", host="0.0.0.0", port=8080, reload=True)