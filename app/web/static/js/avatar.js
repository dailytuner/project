// ============================================
// 3D СИЛУЭТ ЧЕЛОВЕКА С СВЕТЯЩИМИСЯ ЛИНИЯМИ
// ============================================

var scene, camera, renderer, silhouetteGroup;
var currentEnergy = 50;
var targetEnergy = 50;
var clock = new THREE.Clock();
var isInitialized = false;

// Цвета для разных энергетических состояний
var ENERGY_COLORS = {
    low: { start: 0x4a00e0, end: 0x8e2de2 },      // Фиолетовый
    medium: { start: 0x667eea, end: 0x764ba2 },   // Сине-фиолетовый  
    high: { start: 0xf093fb, end: 0xf5576c },     // Розово-красный
    max: { start: 0xff6b6b, end: 0xee5a24 }       // Оранжево-красный
};

function initAvatar() {
    var container = document.getElementById('avatar-container');
    if (!container) {
        console.warn('Контейнер для аватара не найден');
        return;
    }

    // Предотвращаем повторную инициализацию
    if (isInitialized) {
        console.log('Аватар уже инициализирован');
        return;
    }
    isInitialized = true;

    // Очищаем контейнер
    container.innerHTML = '';

    // Создаем сцену
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);

    // Создаем камеру
    camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.set(0, 0.5, 4);
    camera.lookAt(0, 0.5, 0);

    // Создаем рендерер
    renderer = new THREE.WebGLRenderer({ 
        antialias: true, 
        alpha: true 
    });
    
    var size = Math.min(container.clientWidth, container.clientHeight, 400);
    renderer.setSize(size, size);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // Добавляем освещение
    var ambientLight = new THREE.AmbientLight(0x222244, 0.5);
    scene.add(ambientLight);

    var dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(1, 2, 3);
    scene.add(dirLight);

    var backLight = new THREE.DirectionalLight(0x667eea, 0.3);
    backLight.position.set(-1, -1, -2);
    scene.add(backLight);

    // Создаем силуэт
    createSilhouette();

    // Адаптивный размер
    window.addEventListener('resize', function() {
        var newSize = Math.min(container.clientWidth, container.clientHeight, 400);
        camera.aspect = 1;
        camera.updateProjectionMatrix();
        renderer.setSize(newSize, newSize);
    });

    // Обработчик клика по аватару
    container.addEventListener('click', function(event) {
        // Вспышка энергии
        var flash = document.createElement('div');
        flash.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(102,126,234,0.4) 0%, transparent 70%);
            pointer-events: none;
            animation: flashAnim 0.6s ease-out forwards;
            z-index: 10;
        `;
        container.appendChild(flash);
        setTimeout(function() {
            flash.remove();
        }, 700);
        
        // Обновляем рекомендации
        if (typeof window.getRecommendations === 'function') {
            window.getRecommendations();
        } else {
            console.log('🔄 Обновление энергии...');
            // Имитация обновления энергии при клике
            var newEnergy = 30 + Math.random() * 70;
            updateAvatarEnergy(newEnergy);
            if (typeof window.updateEnergyDisplay === 'function') {
                window.updateEnergyDisplay(newEnergy);
            }
        }
    });

    // Запускаем анимацию
    animate();
    
    console.log('✅ 3D Аватар инициализирован');
}

// ============================================
// СОЗДАНИЕ СИЛУЭТА
// ============================================

function createSilhouette() {
    silhouetteGroup = new THREE.Group();

    // --- 1. ПОЛУПРОЗРАЧНЫЙ СИЛУЭТ (тело) ---
    var bodyMat = new THREE.MeshPhysicalMaterial({
        color: 0x667eea,
        transparent: true,
        opacity: 0.08,
        roughness: 0.3,
        metalness: 0.1,
        wireframe: false,
        side: THREE.DoubleSide,
        depthWrite: false,
    });

    // Торс
    var torsoGeo = new THREE.CylinderGeometry(0.55, 0.7, 1.6, 12, 8);
    var torso = new THREE.Mesh(torsoGeo, bodyMat);
    torso.position.y = 0.9;
    torso.scale.set(1, 1, 0.6);
    silhouetteGroup.add(torso);

    // Голова
    var headMat = bodyMat.clone();
    headMat.opacity = 0.12;
    var headGeo = new THREE.SphereGeometry(0.32, 16, 16);
    var head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 1.85;
    head.scale.set(1, 1, 0.85);
    silhouetteGroup.add(head);

    // Левая рука
    var armMat = bodyMat.clone();
    armMat.opacity = 0.06;
    var armGeo = new THREE.CylinderGeometry(0.1, 0.12, 0.9, 8);
    
    var leftArm = new THREE.Mesh(armGeo, armMat);
    leftArm.position.set(-0.7, 1.3, 0);
    leftArm.rotation.z = 0.2;
    leftArm.rotation.x = -0.3;
    silhouetteGroup.add(leftArm);

    // Правая рука
    var rightArm = new THREE.Mesh(armGeo, armMat);
    rightArm.position.set(0.7, 1.3, 0);
    rightArm.rotation.z = -0.2;
    rightArm.rotation.x = 0.3;
    silhouetteGroup.add(rightArm);

    // Левая нога
    var legMat = bodyMat.clone();
    legMat.opacity = 0.06;
    var legGeo = new THREE.CylinderGeometry(0.12, 0.15, 0.9, 8);
    
    var leftLeg = new THREE.Mesh(legGeo, legMat);
    leftLeg.position.set(-0.2, 0.05, 0);
    leftLeg.rotation.x = 0.1;
    silhouetteGroup.add(leftLeg);

    // Правая нога
    var rightLeg = new THREE.Mesh(legGeo, legMat);
    rightLeg.position.set(0.2, 0.05, 0);
    rightLeg.rotation.x = -0.1;
    silhouetteGroup.add(rightLeg);

    // --- 2. СВЕТЯЩИЕСЯ ЛИНИИ (энергетические меридианы) ---
    
    // Основные линии (энергетические каналы)
    var linePoints = [
        // Вертикальный центральный канал
        [[0, 0.05, 0], [0, 0.4, 0], [0, 0.8, 0], [0, 1.2, 0], [0, 1.6, 0], [0, 1.85, 0]],
        
        // Левая сторона тела
        [[-0.45, 0.1, 0], [-0.5, 0.5, 0], [-0.55, 0.9, 0], [-0.5, 1.3, 0], [-0.45, 1.6, 0]],
        
        // Правая сторона тела
        [[0.45, 0.1, 0], [0.5, 0.5, 0], [0.55, 0.9, 0], [0.5, 1.3, 0], [0.45, 1.6, 0]],
        
        // Левая рука
        [[-0.45, 1.5, 0], [-0.6, 1.4, 0], [-0.7, 1.2, 0], [-0.75, 1.0, 0]],
        
        // Правая рука
        [[0.45, 1.5, 0], [0.6, 1.4, 0], [0.7, 1.2, 0], [0.75, 1.0, 0]],
        
        // Левая нога
        [[-0.2, 0.05, 0], [-0.25, -0.3, 0], [-0.3, -0.6, 0], [-0.25, -0.85, 0]],
        
        // Правая нога
        [[0.2, 0.05, 0], [0.25, -0.3, 0], [0.3, -0.6, 0], [0.25, -0.85, 0]],
        
        // Горизонтальные линии (плечи, талия)
        [[-0.5, 1.5, 0], [-0.3, 1.55, 0], [0, 1.6, 0], [0.3, 1.55, 0], [0.5, 1.5, 0]],
        [[-0.45, 0.7, 0], [-0.2, 0.75, 0], [0, 0.8, 0], [0.2, 0.75, 0], [0.45, 0.7, 0]],
    ];

    // Создаем линии
    for (var i = 0; i < linePoints.length; i++) {
        var points = linePoints[i];
        
        // Основная линия
        var line = createGlowLine(points, 0x667eea, 0.03 + Math.random() * 0.02);
        line.userData.isMainLine = true;
        line.userData.index = i;
        silhouetteGroup.add(line);

        // Дополнительная линия со смещением для объема
        if (i < 3) {
            var offsetPoints = points.map(function(p) {
                return [p[0] + 0.03, p[1], p[2] + 0.03];
            });
            var extraLine = createGlowLine(offsetPoints, 0x764ba2, 0.015);
            extraLine.userData.isMainLine = false;
            silhouetteGroup.add(extraLine);
        }
    }

    // --- 3. ЭНЕРГЕТИЧЕСКИЕ ТОЧКИ (ЧАКРЫ) ---
    var chakraPositions = [
        { y: 1.85, label: 'Сахасрара', color: 0x9b59b6 },
        { y: 1.55, label: 'Аджна', color: 0x3498db },
        { y: 1.25, label: 'Вишуддха', color: 0x2ecc71 },
        { y: 0.95, label: 'Анахата', color: 0x2ecc71 },
        { y: 0.65, label: 'Манипура', color: 0xf1c40f },
        { y: 0.35, label: 'Свадхистана', color: 0xe67e22 },
        { y: 0.05, label: 'Муладхара', color: 0xe74c3c },
    ];

    for (var i = 0; i < chakraPositions.length; i++) {
        var chakra = chakraPositions[i];
        var size = 0.04 + (7 - i) * 0.005;
        var sphereMat = new THREE.MeshPhysicalMaterial({
            color: chakra.color,
            emissive: chakra.color,
            emissiveIntensity: 0.5,
            transparent: true,
            opacity: 0.6,
            roughness: 0.1,
            metalness: 0.3,
        });
        var sphere = new THREE.Mesh(new THREE.SphereGeometry(size, 12, 12), sphereMat);
        sphere.position.set(0, chakra.y, 0);
        sphere.userData.isChakra = true;
        sphere.userData.chakraIndex = i;
        sphere.userData.baseIntensity = 0.5 + Math.random() * 0.3;
        silhouetteGroup.add(sphere);
    }

    // --- 4. ПАРЯЩИЕ ЧАСТИЦЫ ---
    var particleCount = 80;
    var particleGeo = new THREE.BufferGeometry();
    var positions = new Float32Array(particleCount * 3);
    var colors = new Float32Array(particleCount * 3);
    var sizes = new Float32Array(particleCount);

    for (var i = 0; i < particleCount; i++) {
        var theta = Math.random() * Math.PI * 2;
        var phi = Math.random() * Math.PI;
        var r = 1.2 + Math.random() * 1.8;
        
        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = 0.5 + r * Math.cos(phi) * 0.8;
        positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
        
        var color = new THREE.Color().setHSL(0.7 + Math.random() * 0.3, 0.8, 0.5);
        colors[i * 3] = color.r;
        colors[i * 3 + 1] = color.g;
        colors[i * 3 + 2] = color.b;
        
        sizes[i] = 0.01 + Math.random() * 0.02;
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    particleGeo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    var particleMat = new THREE.PointsMaterial({
        size: 0.03,
        vertexColors: true,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });
    
    var particles = new THREE.Points(particleGeo, particleMat);
    particles.userData.isParticles = true;
    silhouetteGroup.add(particles);

    scene.add(silhouetteGroup);
}

// ============================================
// СОЗДАНИЕ СВЕТЯЩЕЙСЯ ЛИНИИ
// ============================================

function createGlowLine(points, color, width) {
    if (width === undefined) {
        width = 0.02;
    }
    
    var curve = new THREE.CatmullRomCurve3(
        points.map(function(p) {
            return new THREE.Vector3(p[0], p[1], p[2] || 0);
        })
    );
    
    var tubeGeo = new THREE.TubeGeometry(curve, 20, width, 6, false);
    var tubeMat = new THREE.MeshPhysicalMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.3,
        transparent: true,
        opacity: 0.7,
        roughness: 0.2,
        metalness: 0.1,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });
    
    var mesh = new THREE.Mesh(tubeGeo, tubeMat);
    
    // Добавляем вторую, более тонкую линию для свечения
    var glowMat = tubeMat.clone();
    glowMat.opacity = 0.3;
    glowMat.emissiveIntensity = 0.6;
    var glowGeo = new THREE.TubeGeometry(curve, 20, width * 2.5, 6, false);
    var glowMesh = new THREE.Mesh(glowGeo, glowMat);
    
    var group = new THREE.Group();
    group.add(mesh);
    group.add(glowMesh);
    group.userData.mainMesh = mesh;
    group.userData.glowMesh = glowMesh;
    group.userData.curve = curve;
    
    return group;
}

// ============================================
// ОБНОВЛЕНИЕ ЭНЕРГИИ И ЦВЕТОВ
// ============================================

function updateAvatarEnergy(percent) {
    targetEnergy = Math.max(0, Math.min(100, percent));
}

function getEnergyColor(energy) {
    var t = energy / 100;
    var color;
    
    if (t < 0.33) {
        // Низкая энергия - фиолетовый
        var p = t / 0.33;
        color = new THREE.Color(ENERGY_COLORS.low.start);
        color.lerp(new THREE.Color(ENERGY_COLORS.low.end), p);
    } else if (t < 0.66) {
        // Средняя энергия - синий
        var p = (t - 0.33) / 0.33;
        color = new THREE.Color(ENERGY_COLORS.medium.start);
        color.lerp(new THREE.Color(ENERGY_COLORS.medium.end), p);
    } else if (t < 0.9) {
        // Высокая энергия - розовый
        var p = (t - 0.66) / 0.24;
        color = new THREE.Color(ENERGY_COLORS.high.start);
        color.lerp(new THREE.Color(ENERGY_COLORS.high.end), p);
    } else {
        // Максимальная энергия - оранжевый
        var p = (t - 0.9) / 0.1;
        color = new THREE.Color(ENERGY_COLORS.max.start);
        color.lerp(new THREE.Color(ENERGY_COLORS.max.end), p);
    }
    
    return color;
}

function updateSilhouetteColors(energy) {
    if (!silhouetteGroup) {
        return;
    }
    
    var color = getEnergyColor(energy);
    
    // Обновляем линии
    silhouetteGroup.children.forEach(function(child) {
        if (child.userData && child.userData.isMainLine !== undefined) {
            // Основные линии
            if (child.userData.mainMesh) {
                child.userData.mainMesh.material.color.set(color);
                child.userData.mainMesh.material.emissive.set(color);
                child.userData.mainMesh.material.emissiveIntensity = 0.2 + (energy / 100) * 0.6;
                child.userData.mainMesh.material.opacity = 0.3 + (energy / 100) * 0.5;
            }
            if (child.userData.glowMesh) {
                child.userData.glowMesh.material.color.set(color);
                child.userData.glowMesh.material.emissive.set(color);
                child.userData.glowMesh.material.emissiveIntensity = 0.4 + (energy / 100) * 0.8;
                child.userData.glowMesh.material.opacity = 0.1 + (energy / 100) * 0.3;
            }
        }
        
        // Чакры
        if (child.userData && child.userData.isChakra) {
            var chakraColor = getEnergyColor(energy + (child.userData.chakraIndex * 5) % 40);
            child.material.color.set(chakraColor);
            child.material.emissive.set(chakraColor);
            child.material.emissiveIntensity = child.userData.baseIntensity * (0.3 + (energy / 100) * 0.7);
            var scale = 0.8 + (energy / 100) * 0.6;
            child.scale.set(scale, scale, scale);
        }
    });
    
    // Обновляем полупрозрачный силуэт
    silhouetteGroup.children.forEach(function(child) {
        if (child.isMesh && child.material && child.material.opacity !== undefined) {
            if (child.material.opacity < 0.2) { // Это части силуэта
                child.material.opacity = 0.04 + (energy / 100) * 0.12;
                var c = getEnergyColor(energy);
                child.material.color.set(c);
            }
        }
    });
}

// ============================================
// АНИМАЦИЯ
// ============================================

function animate() {
    requestAnimationFrame(animate);
    
    var time = clock.getElapsedTime();
    
    // Плавное изменение энергии
    currentEnergy += (targetEnergy - currentEnergy) * 0.05;
    
    // Обновляем цвета
    updateSilhouetteColors(currentEnergy);
    
    if (silhouetteGroup) {
        // Медленное вращение
        silhouetteGroup.rotation.y += 0.003;
        silhouetteGroup.rotation.x = Math.sin(time * 0.1) * 0.05;
        
        // Пульсация
        var pulse = 1 + Math.sin(time * 1.5) * 0.005 * (currentEnergy / 100);
        silhouetteGroup.scale.set(pulse, pulse, pulse);
        
        // Анимация частиц
        silhouetteGroup.children.forEach(function(child) {
            if (child.userData && child.userData.isParticles) {
                var positions = child.geometry.attributes.position;
                var array = positions.array;
                for (var i = 0; i < array.length; i += 3) {
                    // Вращение частиц вокруг Y
                    var x = array[i];
                    var z = array[i + 2];
                    var angle = 0.002;
                    var newX = x * Math.cos(angle) - z * Math.sin(angle);
                    var newZ = x * Math.sin(angle) + z * Math.cos(angle);
                    array[i] = newX;
                    array[i + 2] = newZ;
                }
                positions.needsUpdate = true;
            }
        });
        
        // Анимация чакр (пульсация)
        silhouetteGroup.children.forEach(function(child) {
            if (child.userData && child.userData.isChakra) {
                var pulseIntensity = 1 + Math.sin(time * 2 + child.userData.chakraIndex) * 0.1;
                var baseScale = 0.8 + (currentEnergy / 100) * 0.6;
                child.scale.set(
                    baseScale * pulseIntensity,
                    baseScale * pulseIntensity,
                    baseScale * pulseIntensity
                );
            }
        });
    }
    
    renderer.render(scene, camera);
}

// ============================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // Добавляем CSS для анимации вспышки, если еще не добавлен
    if (!document.getElementById('avatar-flash-style')) {
        var style = document.createElement('style');
        style.id = 'avatar-flash-style';
        style.textContent = `
            @keyframes flashAnim {
                0% { opacity: 1; transform: scale(0.5); }
                100% { opacity: 0; transform: scale(1.5); }
            }
        `;
        document.head.appendChild(style);
    }

    // Ждем загрузки Three.js
    if (typeof THREE !== 'undefined') {
        setTimeout(initAvatar, 200);
    } else {
        console.warn('Three.js не загружен, повторная попытка...');
        var checkThree = setInterval(function() {
            if (typeof THREE !== 'undefined') {
                clearInterval(checkThree);
                initAvatar();
            }
        }, 100);
    }
});

// Экспорт для использования в app.js
window.updateAvatarEnergy = updateAvatarEnergy;
window.initAvatar = initAvatar;