// ============================================
// Daily Tuner - Основной JavaScript код
// ============================================

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
var currentPlatform = null;
var currentUserId = null;
var pendingUserId = null;
var pendingPlatform = null;

// ========== УТИЛИТЫ ==========

/**
 * Показать всплывающее сообщение
 * @param {string} message - Текст сообщения
 * @param {string} type - Тип сообщения: 'info', 'success', 'warning', 'error'
 */
function showToast(message, type) {
    if (type === undefined) {
        type = 'info';
    }
    
    var toast = document.createElement('div');
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
    
    setTimeout(function() {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 3000);
}

/**
 * Форматирование номера телефона
 * @param {HTMLElement} input - Поле ввода телефона
 */
function formatPhoneNumber(input) {
    var value = input.value.replace(/\D/g, '');
    
    if (value.startsWith('7') || value.startsWith('8')) {
        if (value.length > 1) {
            var formatted = '+7';
            if (value.length > 1) {
                formatted += ' (' + value.substring(1, 4);
            }
            if (value.length > 4) {
                formatted += ') ' + value.substring(4, 7);
            }
            if (value.length > 7) {
                formatted += '-' + value.substring(7, 9);
            }
            if (value.length > 9) {
                formatted += '-' + value.substring(9, 11);
            }
            input.value = formatted;
        } else if (value.length === 1) {
            input.value = '+7';
        }
    }
}

/**
 * Парсинг даты из строки
 * @param {string} dateStr - Строка с датой в формате YYYY-MM-DD
 * @returns {Date|null} - Объект Date или null
 */
function parseDate(dateStr) {
    if (!dateStr) {
        return null;
    }
    
    var parts = dateStr.split('-');
    if (parts.length === 3) {
        return new Date(parts[0], parts[1] - 1, parts[2]);
    }
    return null;
}

/**
 * Форматирование даты для отображения
 * @param {string} dateStr - Строка с датой в формате YYYY-MM-DD
 * @returns {string} - Отформатированная дата
 */
function formatDateDisplay(dateStr) {
    if (!dateStr) {
        return '';
    }
    
    var date = parseDate(dateStr);
    if (!date) {
        return dateStr;
    }
    
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
    var isEmail = document.querySelector('input[name="auth_type"]:checked').value === 'email';
    var emailContainer = document.getElementById('email_container');
    var phoneContainer = document.getElementById('phone_container');

    if (emailContainer) {
        if (isEmail) {
            emailContainer.style.display = 'block';
        } else {
            emailContainer.style.display = 'none';
        }
    }
    
    if (phoneContainer) {
        if (isEmail) {
            phoneContainer.style.display = 'none';
        } else {
            phoneContainer.style.display = 'block';
        }
    }
}

/**
 * Вход или регистрация пользователя
 */
async function login() {
    var isEmail = document.querySelector('input[name="auth_type"]:checked').value === 'email';
    var platform = isEmail ? 'email' : 'phone';
    var userId = '';
    
    if (isEmail) {
        userId = document.getElementById('email_input').value;
    } else {
        userId = document.getElementById('phone_input').value;
    }

    if (!userId || userId.trim() === '') {
        showToast('Введите email или телефон', 'error');
        return;
    }

    // Нормализация телефона
    if (!isEmail) {
        userId = userId.replace(/\D/g, '');
        if (userId.startsWith('8')) {
            userId = '7' + userId.substring(1);
        }
        if (!userId.startsWith('7')) {
            userId = '7' + userId;
        }
    }

    var resultDiv = document.getElementById('auth-result');
    var loginBtn = document.getElementById('login-btn');

    loginBtn.disabled = true;
    loginBtn.textContent = '⏳ Проверка...';
    
    if (resultDiv) {
        resultDiv.innerHTML = '<div class="loading">⏳ Проверка...</div>';
    }

    try {
        var response = await fetch('/api/validate?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId));
        var result = await response.json();

        if (result.success) {
            // Пользователь существует - проверяем пароль
            var statusResponse = await fetch('/api/auth/status?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId));
            var status = await statusResponse.json();

            if (status.has_password) {
                // Требуем пароль
                pendingPlatform = platform;
                pendingUserId = userId;
                if (resultDiv) {
                    resultDiv.innerHTML = '';
                }
                showPasswordModal(userId);
            } else {
                // Нет пароля - сразу входим
                authenticateUser(platform, userId);
                if (resultDiv) {
                    resultDiv.innerHTML = '';
                }
                showToast('Добро пожаловать!', 'success');
                await loadProfile();
                await checkPasswordStatus();

                // Предлагаем установить пароль
                setTimeout(function() {
                    showSetPasswordModal();
                }, 500);
            }
        } else {
            // Новый пользователь
            authenticateUser(platform, userId);
            if (resultDiv) {
                resultDiv.innerHTML = '';
            }
            showToast('Добро пожаловать! Установите пароль для защиты профиля', 'info');

            // Предлагаем установить пароль
            setTimeout(function() {
                showSetPasswordModal();
            }, 500);
        }
    } catch(error) {
        if (resultDiv) {
            resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + error.message + '</div>';
        }
        showToast('Ошибка подключения', 'error');
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Продолжить';
    }
}

/**
 * Аутентификация пользователя (установка сессии)
 * @param {string} platform - Платформа ('email', 'phone', 'yandex')
 * @param {string} userId - Идентификатор пользователя
 */
function authenticateUser(platform, userId) {
    currentPlatform = platform;
    currentUserId = userId;

    // Сохраняем в cookies
    document.cookie = 'user_platform=' + platform + '; path=/; max-age=604800';
    document.cookie = 'user_platform_id=' + encodeURIComponent(userId) + '; path=/; max-age=604800';
    document.cookie = 'user_authenticated=true; path=/; max-age=604800';

    // Скрываем форму входа
    var authPage = document.getElementById('auth-page');
    if (authPage) {
        authPage.classList.add('hidden');
    }

    // Показываем профиль
    var profilePage = document.getElementById('profile-page');
    if (profilePage) {
        profilePage.classList.remove('hidden');
    }
    
    var profileUserId = document.getElementById('profile-user-id');
    if (profileUserId) {
        profileUserId.innerHTML = '👤 ' + userId;
    }
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
    var profilePage = document.getElementById('profile-page');
    var activitiesPage = document.getElementById('activities-page');
    var forecastPage = document.getElementById('forecast-page');
    
    if (profilePage) {
        profilePage.classList.add('hidden');
    }
    if (activitiesPage) {
        activitiesPage.classList.add('hidden');
    }
    if (forecastPage) {
        forecastPage.classList.add('hidden');
    }

    // Показываем форму входа
    var authPage = document.getElementById('auth-page');
    if (authPage) {
        authPage.classList.remove('hidden');
    }

    // Очищаем поля
    var emailInput = document.getElementById('email_input');
    if (emailInput) {
        emailInput.value = '';
    }
    
    var phoneInput = document.getElementById('phone_input');
    if (phoneInput) {
        phoneInput.value = '';
    }

    showToast('Вы вышли из системы', 'info');
}

// ========== ПАРОЛИ ==========

/**
 * Показать модальное окно для ввода пароля
 * @param {string} userId - Идентификатор пользователя
 */
function showPasswordModal(userId) {
    var modal = document.getElementById('password-modal');
    var userInfo = document.getElementById('password-modal-user');
    
    if (userInfo) {
        userInfo.textContent = 'Пользователь: ' + userId;
    }
    
    if (modal) {
        modal.style.display = 'flex';
    }
    
    var passwordInput = document.getElementById('modal-password');
    if (passwordInput) {
        passwordInput.value = '';
        passwordInput.focus();
    }
    
    var errorDiv = document.getElementById('modal-error');
    if (errorDiv) {
        errorDiv.innerHTML = '';
    }
}

/**
 * Закрыть модальное окно пароля
 */
function closePasswordModal() {
    var modal = document.getElementById('password-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    pendingUserId = null;
    pendingPlatform = null;
}

/**
 * Показать модальное окно для установки пароля
 */
function showSetPasswordModal() {
    var modal = document.getElementById('set-password-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
    
    var passwordInput = document.getElementById('set-password');
    if (passwordInput) {
        passwordInput.value = '';
        passwordInput.focus();
    }
    
    var confirmInput = document.getElementById('confirm-password');
    if (confirmInput) {
        confirmInput.value = '';
    }
    
    var errorDiv = document.getElementById('set-password-error');
    if (errorDiv) {
        errorDiv.innerHTML = '';
    }
}

/**
 * Закрыть модальное окно установки пароля
 */
function closeSetPasswordModal() {
    var modal = document.getElementById('set-password-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Отправить пароль для входа
 */
async function submitPassword() {
    var password = document.getElementById('modal-password').value;
    
    if (!password) {
        var errorDiv = document.getElementById('modal-error');
        if (errorDiv) {
            errorDiv.innerHTML = '<div class="error">Введите пароль</div>';
        }
        return;
    }

    var btn = document.getElementById('modal-submit-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Проверка...';

    try {
        var response = await fetch('/api/validate?platform=' + pendingPlatform + '&platform_user_id=' + encodeURIComponent(pendingUserId) + '&password=' + encodeURIComponent(password));
        var result = await response.json();

        if (result.success) {
            closePasswordModal();
            authenticateUser(pendingPlatform, pendingUserId);
            
            var resultDiv = document.getElementById('auth-result');
            if (resultDiv) {
                resultDiv.innerHTML = '';
            }
            
            showToast('Вход выполнен успешно', 'success');
            await loadProfile();
            await checkPasswordStatus();
        } else {
            var errorDiv = document.getElementById('modal-error');
            if (errorDiv) {
                errorDiv.innerHTML = '<div class="error">Неверный пароль</div>';
            }
        }
    } catch(error) {
        var errorDiv = document.getElementById('modal-error');
        if (errorDiv) {
            errorDiv.innerHTML = '<div class="error">Ошибка: ' + error.message + '</div>';
        }
    } finally {
        btn.disabled = false;
        btn.textContent = 'Войти';
    }
}

/**
 * Установить новый пароль
 */
async function submitSetPassword() {
    var password = document.getElementById('set-password').value;
    var confirm = document.getElementById('confirm-password').value;

    if (password !== confirm) {
        var errorDiv = document.getElementById('set-password-error');
        if (errorDiv) {
            errorDiv.innerHTML = '<div class="error">Пароли не совпадают</div>';
        }
        return;
    }

    if (password.length < 6) {
        var errorDiv = document.getElementById('set-password-error');
        if (errorDiv) {
            errorDiv.innerHTML = '<div class="error">Пароль должен быть минимум 6 символов</div>';
        }
        return;
    }

    var btn = document.getElementById('set-password-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Установка...';

    try {
        var response = await fetch('/api/auth/set-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                platform: currentPlatform,
                platform_user_id: currentUserId,
                password: password
            })
        });
        var result = await response.json();

        if (result.success) {
            closeSetPasswordModal();
            showToast('Пароль успешно установлен', 'success');
            await checkPasswordStatus();
        } else {
            var errorDiv = document.getElementById('set-password-error');
            if (errorDiv) {
                errorDiv.innerHTML = '<div class="error">' + (result.error || 'Ошибка установки пароля') + '</div>';
            }
        }
    } catch(error) {
        var errorDiv = document.getElementById('set-password-error');
        if (errorDiv) {
            errorDiv.innerHTML = '<div class="error">Ошибка: ' + error.message + '</div>';
        }
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
        var platform = currentPlatform || window.userPlatform;
        var userId = currentUserId || window.userPlatformId;

        if (!platform || !userId) {
            console.warn('Нет platform или userId для checkPasswordStatus');
            return;
        }

        var response = await fetch('/api/auth/status?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId));
        var result = await response.json();

        var hasPasswordInfo = document.getElementById('has-password-info');
        var noPasswordInfo = document.getElementById('no-password-info');

        if (result.has_password) {
            if (hasPasswordInfo) {
                hasPasswordInfo.style.display = 'block';
            }
            if (noPasswordInfo) {
                noPasswordInfo.style.display = 'none';
            }
        } else {
            if (hasPasswordInfo) {
                hasPasswordInfo.style.display = 'none';
            }
            if (noPasswordInfo) {
                noPasswordInfo.style.display = 'block';
            }
        }
    } catch(error) {
        console.error('Ошибка проверки статуса пароля:', error);
    }
}

/**
 * Показать форму смены пароля
 */
function showChangePassword() {
    var form = document.getElementById('change-password-form');
    if (form) {
        form.style.display = 'block';
    }
    
    var info = document.getElementById('has-password-info');
    if (info) {
        info.style.display = 'none';
    }
}

/**
 * Отменить смену пароля
 */
function cancelChangePassword() {
    var form = document.getElementById('change-password-form');
    if (form) {
        form.style.display = 'none';
    }
    checkPasswordStatus();
}

/**
 * Сменить пароль
 */
async function changePassword() {
    var password = document.getElementById('new-password').value;
    var confirm = document.getElementById('new-password-confirm').value;

    if (password !== confirm) {
        showToast('Пароли не совпадают', 'error');
        return;
    }

    if (password.length < 6) {
        showToast('Пароль должен быть минимум 6 символов', 'error');
        return;
    }

    try {
        var response = await fetch('/api/auth/set-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                platform: currentPlatform,
                platform_user_id: currentUserId,
                password: password
            })
        });
        var result = await response.json();

        if (result.success) {
            showToast('Пароль успешно изменен', 'success');
            cancelChangePassword();
            
            var newPasswordInput = document.getElementById('new-password');
            if (newPasswordInput) {
                newPasswordInput.value = '';
            }
            
            var confirmInput = document.getElementById('new-password-confirm');
            if (confirmInput) {
                confirmInput.value = '';
            }
            
            await checkPasswordStatus();
        } else {
            showToast(result.error || 'Ошибка изменения пароля', 'error');
        }
    } catch(error) {
        showToast('Ошибка: ' + error.message, 'error');
    }
}

// ========== ПРОФИЛЬ ==========

/**
 * Загрузить профиль пользователя
 */
async function loadProfile() {
    try {
        var platform = currentPlatform || window.userPlatform;
        var userId = currentUserId || window.userPlatformId;

        if (!platform || !userId) {
            console.warn('Нет platform или userId для loadProfile');
            return;
        }

        var response = await fetch('/api/profile?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId));
        var result = await response.json();

        if (result.success && result.profile) {
            var profile = result.profile;

            // Основные поля
            var birthDateInput = document.getElementById('birth_date');
            var birthTimeInput = document.getElementById('birth_time');
            var birthCityInput = document.getElementById('birth_city');
            var currentCityInput = document.getElementById('current_city');
            var professionInput = document.getElementById('profession');
            var birthRegionInput = document.getElementById('birth_region');
            var birthCountryInput = document.getElementById('birth_country');

            if (profile.birth_date && birthDateInput) {
                birthDateInput.value = profile.birth_date;
            }
            
            if (profile.birth_time && birthTimeInput) {
                birthTimeInput.value = profile.birth_time.slice(0, 5);
            }
            
            if (profile.birth_city && birthCityInput) {
                birthCityInput.value = profile.birth_city;
            }
            
            if (profile.current_city && currentCityInput) {
                currentCityInput.value = profile.current_city;
            }
            
            if (profile.profession && professionInput) {
                professionInput.value = profile.profession;
            }

            if (profile.birth_region && birthRegionInput) {
                birthRegionInput.value = profile.birth_region;
            }
            
            if (profile.birth_country && birthCountryInput) {
                var options = birthCountryInput.options;
                var found = false;
                
                for (var i = 0; i < options.length; i++) {
                    if (options[i].value === profile.birth_country) {
                        birthCountryInput.selectedIndex = i;
                        found = true;
                        break;
                    }
                }
                
                if (!found) {
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].value === 'Other') {
                            birthCountryInput.selectedIndex = i;
                            break;
                        }
                    }
                }
            }
        }
    } catch(error) {
        console.error('Ошибка загрузки профиля:', error);
        showToast('Ошибка загрузки профиля', 'error');
    }
}

/**
 * Сохранить профиль
 */
async function saveProfile() {
    var platform = currentPlatform || window.userPlatform;
    var userId = currentUserId || window.userPlatformId;

    if (!platform || !userId) {
        showToast('Ошибка: пользователь не авторизован', 'error');
        return;
    }

    var birthDate = document.getElementById('birth_date').value;
    var birthTime = document.getElementById('birth_time').value;
    var birthCity = document.getElementById('birth_city').value;
    var birthCountry = document.getElementById('birth_country').value;

    if (!birthDate || !birthTime || !birthCity) {
        showToast('Заполните все обязательные поля', 'error');
        return;
    }

    if (!birthCountry) {
        showToast('Выберите страну рождения', 'error');
        return;
    }

    var resultDiv = document.getElementById('profile-result');
    if (resultDiv) {
        resultDiv.innerHTML = '<div class="loading">⏳ Сохранение...</div>';
    }

    var profile = {
        birth_date: birthDate,
        birth_time: birthTime,
        birth_city: birthCity,
        birth_country: birthCountry,
        birth_region: document.getElementById('birth_region').value || null,
        current_city: document.getElementById('current_city').value || null,
        profession: document.getElementById('profession').value || null
    };

    var requestData = {
        request: {
            platform: platform,
            platform_user_id: userId
        },
        profile: profile
    };

    try {
        var response = await fetch('/api/profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        var result = await response.json();

        if (result.success) {
            if (resultDiv) {
                resultDiv.innerHTML = '<div class="success">✅ Профиль сохранен! Расчеты запущены в фоне.</div>';
            }
            showToast('Профиль успешно сохранен', 'success');

            setTimeout(async function() {
                await loadProfile();
                if (resultDiv) {
                    resultDiv.innerHTML = '';
                }
            }, 3000);
        } else {
            var errorMsg = result.error || 'Неизвестная ошибка';
            if (resultDiv) {
                resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + errorMsg + '</div>';
            }
            showToast('Ошибка сохранения профиля', 'error');
        }
    } catch(error) {
        if (resultDiv) {
            resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + error.message + '</div>';
        }
        showToast('Ошибка сохранения профиля', 'error');
    }
}

/**
 * Проверить заполненность профиля
 */
async function checkProfile() {
    var platform = currentPlatform || window.userPlatform;
    var userId = currentUserId || window.userPlatformId;

    if (!platform || !userId) {
        showToast('Ошибка: пользователь не авторизован', 'error');
        return;
    }

    var resultDiv = document.getElementById('profile-result');
    if (resultDiv) {
        resultDiv.innerHTML = '<div class="loading">🔍 Проверка...</div>';
    }

    try {
        var response = await fetch('/api/validate?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId));
        var result = await response.json();

        if (result.success) {
            var html = '<div class="result">';
            html += '<strong>📊 Статус профиля</strong><br><br>';

            if (result.has_complete_data) {
                html += '<div class="success">✅ Данные полные</div>';
            } else {
                html += '<div class="warning">⚠️ Данные неполные</div>';
            }

            if (result.missing_fields && result.missing_fields.length) {
                html += '<br><strong>📋 Отсутствует:</strong><br>';
                for (var i = 0; i < result.missing_fields.length; i++) {
                    html += '• ' + result.missing_fields[i] + '<br>';
                }
            }

            html += '</div>';
            if (resultDiv) {
                resultDiv.innerHTML = html;
            }
        } else {
            if (resultDiv) {
                resultDiv.innerHTML = '<div class="error">❌ ' + (result.error || 'Ошибка') + '</div>';
            }
        }
    } catch(error) {
        if (resultDiv) {
            resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + error.message + '</div>';
        }
    }
}

// ========== ОБНОВЛЕНИЕ ЭНЕРГИИ ==========

/**
 * Обновить отображение энергии
 * @param {number} percent - Уровень энергии (0-100)
 */
function updateEnergyDisplay(percent) {
    var energy = Math.max(0, Math.min(100, percent));
    
    // Обновляем 3D аватар
    if (typeof window.updateAvatarEnergy === 'function') {
        window.updateAvatarEnergy(energy);
    }
    
    // Обновляем индикатор
    var fill = document.getElementById('energy-fill');
    var text = document.getElementById('energy-text');
    
    if (fill) {
        fill.style.width = energy + '%';
        // Меняем цвет индикатора
        var hue = 240 - (energy / 100) * 200;
        fill.style.background = 'hsl(' + hue + ', 80%, 60%)';
    }
    
    if (text) {
        text.textContent = Math.round(energy) + '%';
        // Меняем цвет текста
        var hue = 240 - (energy / 100) * 200;
        text.style.color = 'hsl(' + hue + ', 80%, 60%)';
    }
}

// ========== РЕКОМЕНДАЦИИ ==========

/**
 * Получить рекомендации на день
 */
async function getRecommendations() {
    var platform = currentPlatform || window.userPlatform;
    var userId = currentUserId || window.userPlatformId;

    if (!platform || !userId) {
        showToast('Ошибка: пользователь не авторизован', 'error');
        return;
    }

    var resultDiv = document.getElementById('activities-result');
    var targetDate = document.getElementById('target_date').value;
    
    if (!targetDate) {
        var today = new Date();
        targetDate = today.toISOString().split('T')[0];
    }

    if (resultDiv) {
        resultDiv.innerHTML = '<div class="loading">🎯 Расчет рекомендаций...</div>';
    }

    try {
        var response = await fetch('/api/recommendations?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId) + '&date=' + targetDate);
        var result = await response.json();

        if (result.success) {
            // Обновляем энергию
            var energyPercent = result.energy_percent || 50;
            updateEnergyDisplay(energyPercent);
            
            // Формируем HTML для отображения
            var html = '<div class="result">';
            html += '<strong>📅 ' + (result.date_formatted || formatDateDisplay(targetDate)) + '</strong>';

            // Энергетическая шкала
            html += '<div class="energy-bar">';
            html += '<div class="energy-fill" style="width: ' + energyPercent + '%">';
            html += energyPercent + '%';
            html += '</div></div>';

            if (result.summary) {
                html += '<div style="margin: 10px 0;">📊 ' + result.summary + '</div>';
            }

            html += '<strong>✅ Рекомендации:</strong><br>';
            html += '<div style="margin-top: 10px;">';

            var recommendationsText = result.recommendations_text || 'Нет рекомендаций на этот день';
            html += recommendationsText.replace(/\n/g, '<br>');
            html += '</div>';

            if (result.warnings && result.warnings !== '✅ Особых предостережений нет') {
                html += '<br><div class="warning">⚠️ ' + result.warnings + '</div>';
            }

            html += '</div>';
            
            if (resultDiv) {
                resultDiv.innerHTML = html;
            }
        } else {
            var errorMsg = result.error || 'Ошибка получения рекомендаций';
            if (resultDiv) {
                resultDiv.innerHTML = '<div class="error">❌ ' + errorMsg + '</div>';
            }
        }
    } catch(error) {
        if (resultDiv) {
            resultDiv.innerHTML = '<div class="error">❌ Ошибка: ' + error.message + '</div>';
        }
    }
}

// ========== ПРОГНОЗ ==========

/**
 * Получить прогноз на несколько дней
 */
async function getForecast() {
    var platform = currentPlatform || window.userPlatform;
    var userId = currentUserId || window.userPlatformId;

    if (!platform || !userId) {
        showToast('Ошибка: пользователь не авторизован', 'error');
        return;
    }

    var resultDiv = document.getElementById('forecast-result');
    var daysSelect = document.getElementById('forecast_days');
    var days = parseInt(daysSelect.value);

    if (resultDiv) {
        resultDiv.innerHTML = '<div class="loading">🔮 Генерация прогноза...</div>';
    }

    var forecastHtml = '<div class="result">';
    forecastHtml += '<strong>📊 Энергетический прогноз</strong><br><br>';

    var today = new Date();

    for (var i = 1; i <= days; i++) {
        var date = new Date(today);
        date.setDate(today.getDate() + i);
        var dateStr = date.toISOString().split('T')[0];
        var weekday = date.toLocaleDateString('ru-RU', { weekday: 'long' });
        var dayMonth = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });

        try {
            var response = await fetch('/api/recommendations?platform=' + platform + '&platform_user_id=' + encodeURIComponent(userId) + '&date=' + dateStr);
            var result = await response.json();

            if (result.success) {
                var energyPercent = result.energy_percent || 50;
                
                // Обновляем аватар по первому дню
                if (i === 1) {
                    updateEnergyDisplay(energyPercent);
                }
                
                var energyIcon = '';
                if (energyPercent > 70) {
                    energyIcon = '🚀';
                } else if (energyPercent > 40) {
                    energyIcon = '⚡';
                } else {
                    energyIcon = '😴';
                }

                forecastHtml += '<div style="margin: 15px 0; padding: 15px; background: #f5f5f5; border-radius: 10px;">';
                forecastHtml += '<strong>' + weekday + ', ' + dayMonth + '</strong><br>';
                forecastHtml += energyIcon + ' Энергия: ' + energyPercent + '%<br>';

                var recommendationsText = result.recommendations_text || '';
                var firstRec = recommendationsText.split('\n')[0];
                if (firstRec) {
                    var shortRec = firstRec;
                    if (firstRec.length > 60) {
                        shortRec = firstRec.substring(0, 60) + '...';
                    }
                    forecastHtml += '💡 ' + shortRec;
                }
                forecastHtml += '</div>';
            } else {
                forecastHtml += '<div style="margin: 15px 0; padding: 15px; background: #fee; border-radius: 10px;">❌ Ошибка для ' + dayMonth + '</div>';
            }
        } catch(error) {
            forecastHtml += '<div style="margin: 15px 0; padding: 15px; background: #fee; border-radius: 10px;">❌ Ошибка для ' + dayMonth + ': ' + error.message + '</div>';
        }
    }

    forecastHtml += '</div>';
    
    if (resultDiv) {
        resultDiv.innerHTML = forecastHtml;
    }
}

// ========== НАВИГАЦИЯ ==========

/**
 * Показать выбранную страницу
 * @param {string} page - Имя страницы: 'profile', 'activities', 'forecast'
 */
function showPage(page) {
    var profilePage = document.getElementById('profile-page');
    var activitiesPage = document.getElementById('activities-page');
    var forecastPage = document.getElementById('forecast-page');

    // Скрываем все
    if (profilePage) {
        profilePage.classList.add('hidden');
    }
    if (activitiesPage) {
        activitiesPage.classList.add('hidden');
    }
    if (forecastPage) {
        forecastPage.classList.add('hidden');
    }

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
 * @returns {boolean} - Успешно ли восстановлена сессия
 */
function restoreSession() {
    var cookies = document.cookie.split(';');
    var platform = null;
    var platformId = null;
    var authenticated = false;
    var name = null;
    var email = null;

    for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        var parts = cookie.split('=');
        var key = parts[0];
        var value = decodeURIComponent(parts[1] || '');
        
        if (key === 'user_platform') {
            platform = value;
        }
        if (key === 'user_platform_id') {
            platformId = value;
        }
        if (key === 'user_authenticated') {
            authenticated = value === 'true';
        }
        if (key === 'user_name') {
            name = value;
        }
        if (key === 'user_email') {
            email = value;
        }
    }

    if (authenticated && platform && platformId) {
        currentPlatform = platform;
        currentUserId = platformId;

        window.userAuthenticated = true;
        window.userPlatform = platform;
        window.userPlatformId = platformId;

        // Определяем отображаемое имя
        var displayName = name || platformId;
        if (platform === 'yandex' && email) {
            displayName = email;
        }

        // Скрываем форму входа
        var authPage = document.getElementById('auth-page');
        if (authPage) {
            authPage.classList.add('hidden');
        }

        // Показываем профиль
        var profilePage = document.getElementById('profile-page');
        if (profilePage) {
            profilePage.classList.remove('hidden');
        }
        
        var profileUserId = document.getElementById('profile-user-id');
        if (profileUserId) {
            profileUserId.innerHTML = '👤 ' + displayName;
        }

        // Загружаем данные
        loadProfile();
        checkPasswordStatus();
        showToast('Сессия восстановлена', 'success');

        return true;
    }

    return false;
}

// ========== СОГЛАСИЕ НА ПЕРСОНАЛЬНЫЕ ДАННЫЕ ==========

/**
 * Инициализация чекбокса согласия на обработку персональных данных
 */
function initConsentCheckbox() {
    var checkbox = document.getElementById('consent-checkbox');
    var loginBtn = document.getElementById('yandex-login-btn');

    if (!checkbox || !loginBtn) {
        console.warn('Элементы согласия не найдены');
        return;
    }

    // Восстановление состояния из localStorage
    var consentGiven = localStorage.getItem('consent_given') === 'true';
    if (consentGiven) {
        checkbox.checked = true;
        loginBtn.disabled = false;
    }

    // Обработчик изменения чекбокса
    checkbox.addEventListener('change', function() {
        var isChecked = this.checked;
        loginBtn.disabled = !isChecked;
        
        if (isChecked) {
            localStorage.setItem('consent_given', 'true');
            showToast('✅ Согласие принято', 'success');
        } else {
            localStorage.removeItem('consent_given');
            showToast('⚠️ Согласие отозвано', 'warning');
        }
    });

    // Блокировка клика по неактивной кнопке
    loginBtn.addEventListener('click', function(event) {
        if (this.disabled) {
            event.preventDefault();
            event.stopPropagation();
            showToast('Пожалуйста, дайте согласие на обработку персональных данных', 'warning');
            checkbox.focus();
            
            // Визуальная подсветка блока
            var block = document.querySelector('.consent-block');
            if (block) {
                block.style.borderLeftColor = '#ff6b6b';
                block.style.transition = 'border-left-color 0.3s ease';
                setTimeout(function() {
                    block.style.borderLeftColor = '#667eea';
                }, 1500);
            }
            return false;
        }
        return true;
    }, true);

    console.log('✅ Чекбокс согласия инициализирован');
}

// ========== ИНИЦИАЛИЗАЦИЯ ==========

/**
 * Инициализация приложения
 */
function initApp() {
    // Устанавливаем сегодняшнюю дату для поля даты
    var today = new Date();
    var formattedDate = today.toISOString().split('T')[0];
    var targetDateInput = document.getElementById('target_date');
    if (targetDateInput) {
        targetDateInput.value = formattedDate;
    }

    // Настройка переключения типа аутентификации
    toggleAuthType();

    // Настройка форматирования телефона
    var phoneInput = document.getElementById('phone_input');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(event) {
            formatPhoneNumber(this);
        });
    }

    // Инициализация чекбокса согласия
    initConsentCheckbox();

    // Восстановление сессии
    var sessionRestored = restoreSession();

    // Если сессия не восстановлена, показываем форму входа
    if (!sessionRestored) {
        var authPage = document.getElementById('auth-page');
        if (authPage) {
            authPage.classList.remove('hidden');
        }
    }

    // Обработка Enter в полях ввода
    var emailInput = document.getElementById('email_input');
    if (emailInput) {
        emailInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                login();
            }
        });
    }

    if (phoneInput) {
        phoneInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                login();
            }
        });
    }

    // Обработка Enter в модальных окнах
    var modalPassword = document.getElementById('modal-password');
    if (modalPassword) {
        modalPassword.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                submitPassword();
            }
        });
    }

    var setPassword = document.getElementById('set-password');
    if (setPassword) {
        setPassword.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                submitSetPassword();
            }
        });
    }

    console.log('Daily Tuner инициализирован');
    console.log('Аутентифицирован:', !!currentUserId);
}

// ========== ЗАПУСК ==========

// Запускаем инициализацию после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// ========== ЭКСПОРТ ФУНКЦИЙ ==========

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
window.updateEnergyDisplay = updateEnergyDisplay;
window.initConsentCheckbox = initConsentCheckbox;