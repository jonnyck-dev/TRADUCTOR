document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const youtubeUrlInput = document.getElementById('youtube-url');
    const localVideoFile = document.getElementById('local-video-file');
    const btnUploadLocal = document.getElementById('btn-upload-local');
    const btnProcess = document.getElementById('btn-process');
    const btnStopTask = document.getElementById('btn-stop-task');
    const btnNew = document.getElementById('btn-new');
    const startOverlay = document.getElementById('start-overlay');
    const processingOverlay = document.getElementById('processing-overlay');
    const videoPlayer = document.getElementById('video-player');
    
    const selectModel = document.getElementById('select-model');
    const selectSpeaker = document.getElementById('select-speaker');
    const selectTtsModel = document.getElementById('select-tts-model');
    const selectWhisperModel = document.getElementById('select-whisper-model');
    const inputTtsCfg = document.getElementById('input-tts-cfg');
    const inputTtsSteps = document.getElementById('input-tts-steps');
    const chkUseEnhance = document.getElementById('chk-use-enhance');
    const chkUsePhonetic = document.getElementById('chk-use-phonetic');
    const chkUseSync = document.getElementById('chk-use-sync');
    const valTtsCfg = document.getElementById('val-tts-cfg');
    const valTtsSteps = document.getElementById('val-tts-steps');
    const inputBatchSize = document.getElementById('input-batch-size');
    const valBatchSize = document.getElementById('val-batch-size');
    const inputSyncSize = document.getElementById('input-sync-size');
    const valSyncSize = document.getElementById('val-sync-size');
    const selectTtsMode = document.getElementById('select-tts-mode');
    const batchSizeGroup = document.getElementById('batch-size-group');
    const syncSizeGroup = document.getElementById('sync-size-group');
    const btnReloadModels = document.getElementById('btn-reload-models');
    const ollamaStatus = document.getElementById('ollama-status');
    const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const selectSourceLang = document.getElementById('select-source-lang');
    const selectTargetLang = document.getElementById('select-target-lang');

    // Sidebar toggle for mobile
    btnToggleSidebar.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        sidebarOverlay.style.display = sidebar.classList.contains('collapsed') ? 'none' : 'block';
    });

    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        sidebarOverlay.style.display = 'none';
    });

    // Collapse sidebar by default on mobile
    if (window.innerWidth <= 768) {
        sidebar.classList.add('collapsed');
    }

    // --- TTS Model/Speaker Binding ---
    function getModelForSpeaker(speakerValue) {
        if (speakerValue.startsWith('es-')) return 'edge';
        if (speakerValue.startsWith('en-')) return 'VibeVoice-1.5B';
        if (speakerValue === 'cloned_speaker') return 'openbmb/VoxCPM2';
        if (speakerValue === 'windows_native') return null;
        if (speakerValue.includes('young adult') || speakerValue.includes('middle-aged') ||
            speakerValue.includes('low pitch') || speakerValue.includes('high pitch')) {
            return 'k2-fsa/OmniVoice';
        }
        return null;
    }

    function isSpeakerCompatible(speaker, model) {
        if (!speaker || !model) return true;
        if (speaker === 'windows_native') return true;
        if (speaker === 'cloned_speaker') return true;
        if (speaker.startsWith('es-')) return model === 'edge';
        if (speaker.startsWith('en-')) return model.startsWith('VibeVoice') || model === 'openbmb/VoxCPM2';
        if (speaker.includes('young adult') || speaker.includes('middle-aged') ||
            speaker.includes('low pitch') || speaker.includes('high pitch')) {
            return model === 'k2-fsa/OmniVoice';
        }
        return true;
    }

    function updateSpeakerWarning(speakerSelect, ttsModelSelect, warningEl) {
        if (!warningEl) return;
        const compatible = isSpeakerCompatible(speakerSelect.value, ttsModelSelect.value);
        warningEl.classList.toggle('hidden', compatible);
    }

    function updateCfgStepsLabels() {
        const cfgLabel = document.getElementById('cfg-label-value');
        const stepsLabel = document.getElementById('steps-label-value');
        if (cfgLabel && inputTtsCfg) cfgLabel.textContent = inputTtsCfg.value;
        if (stepsLabel && inputTtsSteps) stepsLabel.textContent = inputTtsSteps.value;
    }
    if (inputTtsCfg) inputTtsCfg.addEventListener('input', updateCfgStepsLabels);
    if (inputTtsSteps) inputTtsSteps.addEventListener('input', updateCfgStepsLabels);

    selectSpeaker.addEventListener('change', () => {
        const model = getModelForSpeaker(selectSpeaker.value);
        if (model) {
            selectTtsModel.value = model;
        }
        updateSpeakerWarning(selectSpeaker, selectTtsModel, document.getElementById('speaker-compat-warning'));
    });

    selectTtsModel.addEventListener('change', () => {
        updateSpeakerWarning(selectSpeaker, selectTtsModel, document.getElementById('speaker-compat-warning'));
        // Auto-set recommended CFG and Steps for each TTS model
        if (selectTtsModel.value === 'k2-fsa/OmniVoice') {
            if (inputTtsCfg) inputTtsCfg.value = 2.0;
            if (inputTtsSteps) inputTtsSteps.value = 16;
            if (chkUsePhonetic) { chkUsePhonetic.checked = false; chkUsePhonetic.parentElement.style.opacity = '0.5'; }
        } else if (selectTtsModel.value === 'edge') {
            if (chkUsePhonetic) { chkUsePhonetic.checked = false; chkUsePhonetic.parentElement.style.opacity = '0.5'; }
        } else if (selectTtsModel.value === 'openbmb/VoxCPM2') {
            if (inputTtsCfg) inputTtsCfg.value = 2.0;
            if (inputTtsSteps) inputTtsSteps.value = 10;
            if (chkUsePhonetic && !chkUsePhonetic.checked) { chkUsePhonetic.checked = true; chkUsePhonetic.parentElement.style.opacity = '1'; }
        } else {
            if (chkUsePhonetic) { chkUsePhonetic.checked = true; chkUsePhonetic.parentElement.style.opacity = '1'; }
        }
        updateCfgStepsLabels();
    });

    // --- Notification System ---
    let notificationPermission = 'default';

    function requestNotificationPermission() {
        if (!('Notification' in window)) return;
        Notification.requestPermission().then(perm => {
            notificationPermission = perm;
        });
    }

    function notifyCompleted() {
        if (!('Notification' in window)) return;
        if (Notification.permission === 'granted') {
            new Notification('JANUS Dubber', {
                body: 'Tu video ya está listo',
                icon: '/favicon.ico',
                badge: '/favicon.ico',
                vibrate: [200, 100, 200],
                requireInteraction: true
            });
        }
        document.title = 'Listo! - JANUS Dubber';
    }

    function notifyFailed(msg) {
        if (!('Notification' in window)) return;
        if (Notification.permission === 'granted') {
            new Notification('JANUS Dubber', {
                body: `Error: ${msg}`,
                icon: '/favicon.ico',
                vibrate: [300, 100, 300]
            });
        }
    }

    // Update range slider labels on input
    inputTtsCfg.addEventListener('input', () => {
        valTtsCfg.textContent = inputTtsCfg.value;
    });
    inputTtsSteps.addEventListener('input', () => {
        valTtsSteps.textContent = inputTtsSteps.value;
    });
    inputBatchSize.addEventListener('input', () => {
        valBatchSize.textContent = inputBatchSize.value;
        // Link Sync Size constraint to Batch Size to prevent redundant processing
        inputSyncSize.max = inputBatchSize.value;
        if (parseInt(inputSyncSize.value) > parseInt(inputBatchSize.value)) {
            inputSyncSize.value = inputBatchSize.value;
            valSyncSize.textContent = inputSyncSize.value;
        }
    });
    inputSyncSize.addEventListener('input', () => {
        valSyncSize.textContent = inputSyncSize.value;
    });
    
    // Toggle batch size and sync size visibility based on TTS mode
    selectTtsMode.addEventListener('change', () => {
        if (selectTtsMode.value === 'oneshot') {
            batchSizeGroup.style.display = 'none';
            syncSizeGroup.style.display = 'none';
        } else {
            batchSizeGroup.style.display = 'flex';
            batchSizeGroup.style.flexDirection = 'column';
            syncSizeGroup.style.display = 'flex';
            syncSizeGroup.style.flexDirection = 'column';
        }
    });
    
    // Update subtitle labels when languages change
    function updateSubtitleLabels() {
        const sourceLabel = selectSourceLang.options[selectSourceLang.selectedIndex].text.replace(/^[^\s]+\s/, '');
        const targetLabel = selectTargetLang.options[selectTargetLang.selectedIndex].text.replace(/^[^\s]+\s/, '');
        btnShowOriginal.textContent = sourceLabel;
        btnShowTranslated.textContent = targetLabel;
    }

    selectSourceLang.addEventListener('change', updateSubtitleLabels);
    selectTargetLang.addEventListener('change', updateSubtitleLabels);

    const chkUseCache = document.getElementById('chk-use-cache');
    const cacheSelectWrapper = document.getElementById('cache-select-wrapper');
    const selectCache = document.getElementById('select-cache');
    
    const processTitle = document.getElementById('process-title');
    const processDesc = document.getElementById('process-description');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const globalStatus = document.getElementById('global-status');
    
    const subtitlesViewport = document.getElementById('subtitles-viewport');
    const btnShowOriginal = document.getElementById('btn-show-original');
    const btnShowTranslated = document.getElementById('btn-show-translated');
    const btnTogglePanel = document.getElementById('btn-toggle-panel');

    let pollInterval = null;
    let subtitleData = [];
    let activeSubIndex = -1;
    let currentTaskId = null;

    // --- Recuperar estado de tarea al recargar página ---
    const savedTaskId = localStorage.getItem('janus_taskId');
    const savedTaskUrl = localStorage.getItem('janus_taskUrl');
    if (savedTaskId) {
        fetch(`/api/status/${savedTaskId}`)
        .then(res => {
            if (!res.ok) { localStorage.removeItem('janus_taskId'); return; }
            return res.json();
        })
        .then(data => {
            if (!data) return;
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
                localStorage.removeItem('janus_taskId');
                localStorage.removeItem('janus_taskUrl');
                return;
            }
            // Tarea sigue activa, restaurar UI
            currentTaskId = savedTaskId;
            startOverlay.classList.add('hidden');
            processingOverlay.classList.remove('hidden');
            videoPlayer.classList.add('hidden');
            btnNew.classList.add('hidden');
            subtitlesViewport.innerHTML = '<p class="empty-subs-msg">Recuperando progreso del renderizado...</p>';
            const timersSection = document.getElementById('timers-section');
            if (timersSection) timersSection.classList.add('hidden');
            updateStatus(data.status, data.progress);
            requestNotificationPermission();
            startPolling(savedTaskId);
        })
        .catch(() => {
            localStorage.removeItem('janus_taskId');
            localStorage.removeItem('janus_taskUrl');
        });
    }

    // Helper: format time in MM:SS
    function formatTime(seconds) {
        if (!seconds && seconds !== 0) return '00:00';
        const m = Math.floor(seconds / 60).toString().padStart(2, '0');
        const s = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }

    // Toggle Subtitles Viewport Visibility
    btnTogglePanel.addEventListener('click', () => {
        const isHidden = subtitlesViewport.classList.contains('hidden');
        if (isHidden) {
            subtitlesViewport.classList.remove('hidden');
            btnTogglePanel.classList.add('active');
            btnTogglePanel.innerHTML = '<i class="fa-solid fa-eye"></i>';
        } else {
            subtitlesViewport.classList.add('hidden');
            btnTogglePanel.classList.remove('active');
            btnTogglePanel.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
        }
    });

    // Toggle Source/Translated displays
    btnShowOriginal.addEventListener('click', () => {
        btnShowOriginal.classList.toggle('active');
        const lines = document.querySelectorAll('.subtitle-line');
        lines.forEach(line => {
            line.classList.toggle('hide-source', !btnShowOriginal.classList.contains('active'));
        });
    });

    btnShowTranslated.addEventListener('click', () => {
        btnShowTranslated.classList.toggle('active');
        const lines = document.querySelectorAll('.subtitle-line');
        lines.forEach(line => {
            line.classList.toggle('hide-target', !btnShowTranslated.classList.contains('active'));
        });
    });

    // Fetch caches
    function loadAvailableCaches() {
        fetch('/api/caches')
        .then(res => res.json())
        .then(data => {
            selectCache.innerHTML = '';
            if (!data.caches || data.caches.length === 0) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = '(Ninguna caché disponible)';
                selectCache.appendChild(opt);
                return;
            }
            data.caches.forEach(cache => {
                const opt = document.createElement('option');
                opt.value = cache.id;
                // Mostrar metadatos si existen
                if (cache.meta) {
                    const srcLang = cache.meta.source_language || 'English';
                    const tgtLang = cache.meta.target_language || 'Spanish';
                    opt.textContent = `${cache.id} (${srcLang} → ${tgtLang})`;
                } else {
                    opt.textContent = cache.id;
                }
                // Guardar metadatos como data attribute
                opt.dataset.meta = JSON.stringify(cache.meta || {});
                selectCache.appendChild(opt);
            });
        })
        .catch(err => {
            console.error('Error fetching caches:', err);
            selectCache.innerHTML = '<option value="">Error al cargar cachés</option>';
        });
    }
    
    // Auto-poblar parámetros al seleccionar una caché
    selectCache.addEventListener('change', () => {
        const selectedOption = selectCache.options[selectCache.selectedIndex];
        if (!selectedOption || !selectedOption.dataset.meta) return;
        
        try {
            const meta = JSON.parse(selectedOption.dataset.meta);
            if (!meta || Object.keys(meta).length === 0) return;
            
            // Auto-poblar idiomas
            if (meta.source_language && selectSourceLang) {
                selectSourceLang.value = meta.source_language;
            }
            if (meta.target_language && selectTargetLang) {
                selectTargetLang.value = meta.target_language;
            }
            
            // Auto-poblar modelo Ollama
            if (meta.model && selectModel) {
                selectModel.value = meta.model;
            }
            
            // Auto-poblar modelo Whisper
            if (meta.whisper_model && selectWhisperModel) {
                selectWhisperModel.value = meta.whisper_model;
            }
            
            // Auto-poblar modelo TTS
            if (meta.tts_model && selectTtsModel) {
                selectTtsModel.value = meta.tts_model;
            }
            
            // Auto-poblar speaker
            if (meta.speaker && selectSpeaker) {
                selectSpeaker.value = meta.speaker;
            }
            
            // Auto-poblar batch_size
            if (meta.batch_size !== undefined && inputBatchSize) {
                inputBatchSize.value = meta.batch_size;
                if (valBatchSize) valBatchSize.textContent = meta.batch_size;
            }
            
            // Auto-poblar sync_size
            if (meta.sync_size !== undefined && inputSyncSize) {
                inputSyncSize.value = meta.sync_size;
                if (valSyncSize) valSyncSize.textContent = meta.sync_size;
            }
            
            // Auto-poblar tts_cfg
            if (meta.tts_cfg !== undefined && inputTtsCfg) {
                inputTtsCfg.value = meta.tts_cfg;
                if (valTtsCfg) valTtsCfg.textContent = meta.tts_cfg;
            }
            
            // Auto-poblar tts_steps
            if (meta.tts_steps !== undefined && inputTtsSteps) {
                inputTtsSteps.value = meta.tts_steps;
                if (valTtsSteps) valTtsSteps.textContent = meta.tts_steps;
            }
            
            // Auto-poblar tts_mode
            if (meta.tts_mode && selectTtsMode) {
                selectTtsMode.value = meta.tts_mode;
            }
            
            console.log('[Cache] Parámetros auto-poblados desde caché:', meta);
        } catch (e) {
            console.error('[Cache] Error al parsear metadatos:', e);
        }
    });

    // Fetch Ollama models dynamically and group them
    function loadOllamaModels() {
        fetch('/api/models')
        .then(res => res.json())
        .then(data => {
            selectModel.innerHTML = '';
            
            const models = data.models || [];
            if (models.length === 0) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = '(No se encontraron modelos de Ollama)';
                selectModel.appendChild(opt);
                if (ollamaStatus) ollamaStatus.style.display = 'block';
                return;
            }
            
            if (ollamaStatus) ollamaStatus.style.display = 'none';
            
            const localGroup = document.createElement('optgroup');
            localGroup.label = 'Modelos Locales (Ollama)';
            
            const cloudGroup = document.createElement('optgroup');
            cloudGroup.label = 'Modelos Cloud (Requiere Suscripción)';
            
            let hasLocal = false;
            let hasCloud = false;
            
            models.forEach(modelName => {
                const opt = document.createElement('option');
                opt.value = modelName;
                
                if (modelName.includes('cloud')) {
                    opt.textContent = `☁️ ${modelName}`;
                    cloudGroup.appendChild(opt);
                    hasCloud = true;
                } else {
                    if (modelName === 'gemma4:e2b-it-qat') {
                        opt.textContent = `⭐ (Recomendado) ${modelName}`;
                        opt.selected = true;
                    } else {
                        opt.textContent = modelName;
                    }
                    localGroup.appendChild(opt);
                    hasLocal = true;
                }
            });
            
            if (hasLocal) selectModel.appendChild(localGroup);
            if (hasCloud) selectModel.appendChild(cloudGroup);
        })
        .catch(err => {
            console.error('Error fetching Ollama models:', err);
            selectModel.innerHTML = '<option value="">Error al cargar modelos de Ollama</option>';
        });
    }

    chkUseCache.addEventListener('change', () => {
        if (chkUseCache.checked) {
            cacheSelectWrapper.classList.remove('hidden');
            youtubeUrlInput.disabled = true;
            youtubeUrlInput.placeholder = 'Usando caché local...';
            loadAvailableCaches();
        } else {
            cacheSelectWrapper.classList.add('hidden');
            youtubeUrlInput.disabled = false;
            youtubeUrlInput.placeholder = 'https://www.youtube.com/watch?v=...';
        }
    });

    btnNew.addEventListener('click', () => {
        // Stop playback
        videoPlayer.pause();
        videoPlayer.src = '';
        
        // Hide video elements
        videoPlayer.classList.add('hidden');
        btnNew.classList.add('hidden');
        
        // Hide timers
        const timersSection = document.getElementById('timers-section');
        if (timersSection) timersSection.classList.add('hidden');
        
        // Reset subtitles
        subtitlesViewport.innerHTML = '<p class="empty-subs-msg">Las subtítulos aparecerán aquí una vez procesado el video.</p>';
        
        // Show initial form
        startOverlay.classList.remove('hidden');
        youtubeUrlInput.value = '';
        
        // Reset status
        globalStatus.innerHTML = '<span class="dot"></span> Listo para doblar';
        currentTaskId = null;
        localStorage.removeItem('janus_taskId');
        localStorage.removeItem('janus_taskUrl');
    });

    // Reload models button
    if (btnReloadModels) {
        btnReloadModels.addEventListener('click', () => {
            btnReloadModels.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            btnReloadModels.disabled = true;
            loadOllamaModels();
            // Re-enable after a short delay
            setTimeout(() => {
                btnReloadModels.innerHTML = '<i class="fa-solid fa-rotate"></i>';
                btnReloadModels.disabled = false;
            }, 3000);
        });
    }

    // Initial calls
    loadOllamaModels();

    let openStudioOnLoad = false;
    // Flag para distinguir un finalize del Studio (reensamblado) de un process inicial,
    // de modo que al terminar el polling podamos restaurar el botón "Ensamblar Video Final".
    let studioFinalizing = false;
    const btnProcessStudio = document.getElementById('btn-process-studio');
    if (btnProcessStudio) {
        btnProcessStudio.addEventListener('click', () => {
            if (chkUseCache.checked && selectCache.value) {
                window.open(`/studio?task_id=${selectCache.value}`, '_blank');
            } else {
                alert("Por favor selecciona una caché de video existente para abrir en el Modo Estudio.");
            }
        });
    }

    // Local File Upload Logic
    const localFileIndicator = document.getElementById('local-file-indicator');
    const localFileName = document.getElementById('local-file-name');
    const btnClearLocalFile = document.getElementById('btn-clear-local-file');
    
    if (btnUploadLocal && localVideoFile) {
        btnUploadLocal.addEventListener('click', () => {
            localVideoFile.click();
        });

        localVideoFile.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // Update UI to show selected file
            if (localFileIndicator) localFileIndicator.classList.remove('hidden');
            if (localFileName) localFileName.textContent = `${file.name} (Subiendo...)`;

            const formData = new FormData();
            formData.append("file", file);

            const originalBtnHtml = btnUploadLocal.innerHTML;
            btnUploadLocal.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Procesando...';
            btnUploadLocal.disabled = true;

            fetch('/api/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                btnUploadLocal.innerHTML = originalBtnHtml;
                btnUploadLocal.disabled = false;
                
                if (data.status === 'ok' && data.task_id) {
                    youtubeUrlInput.value = 'cache:' + data.task_id;
                    if (chkUseCache) chkUseCache.checked = false;
                    if (localFileName) localFileName.textContent = `${file.name} (Listo para comenzar)`;
                } else {
                    alert("Error subiendo archivo: " + JSON.stringify(data));
                    if (localFileIndicator) localFileIndicator.classList.add('hidden');
                }
            })
            .catch(error => {
                console.error("Error al subir:", error);
                alert("Error de red al subir el archivo.");
                btnUploadLocal.innerHTML = originalBtnHtml;
                btnUploadLocal.disabled = false;
                if (localFileIndicator) localFileIndicator.classList.add('hidden');
            });
        });
        
        if (btnClearLocalFile) {
            btnClearLocalFile.addEventListener('click', () => {
                localVideoFile.value = '';
                youtubeUrlInput.value = '';
                if (localFileIndicator) localFileIndicator.classList.add('hidden');
            });
        }
    }

    btnProcess.addEventListener('click', () => {
        // Bloquear si ya hay un renderizado activo
        if (currentTaskId) {
            alert('Ya hay un video renderizándose. Espera a que termine antes de iniciar otro.');
            return;
        }

        let url = '';
        if (chkUseCache.checked) {
            const cacheVal = selectCache.value;
            if (!cacheVal) {
                alert('Por favor, selecciona una caché de desarrollo.');
                return;
            }
            url = `cache:${cacheVal}`;
        } else {
            url = youtubeUrlInput.value.trim();
            if (!url) {
                alert('Por favor, ingresa una URL válida de YouTube.');
                return;
            }
        }

        const payload = {
            url: url,
            model: selectModel.value,
            speaker: selectSpeaker.value,
            tts_model: selectTtsModel.value,
            whisper_model: selectWhisperModel ? selectWhisperModel.value : 'large-v3-turbo',
            tts_cfg: parseFloat(inputTtsCfg.value),
            tts_steps: parseInt(inputTtsSteps.value),
            tts_mode: selectTtsMode.value,
            batch_size: parseInt(inputBatchSize.value),
            sync_size: parseInt(inputSyncSize.value),
            source_language: selectSourceLang ? selectSourceLang.value : 'English',
            target_language: selectTargetLang ? selectTargetLang.value : 'Spanish',
            use_enhance: chkUseEnhance ? chkUseEnhance.checked : true,
            use_phonetic: chkUsePhonetic ? chkUsePhonetic.checked : true,
            use_sync: chkUseSync ? chkUseSync.checked : true
        };
        console.log('[DEBUG] Payload:', JSON.stringify(payload, null, 2));

        // Reset view states
        startOverlay.classList.add('hidden');
        processingOverlay.classList.remove('hidden');
        videoPlayer.classList.add('hidden');
        btnNew.classList.add('hidden');
        subtitlesViewport.innerHTML = '<p class="empty-subs-msg">El video está siendo procesado...</p>';
        
        const timersSection = document.getElementById('timers-section');
        if (timersSection) {
            timersSection.classList.add('hidden');
        }
        
        updateStatus('queued', 0);

        fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (!res.ok) throw new Error('Error al iniciar la tarea.');
            return res.json();
        })
        .then(data => {
            const taskId = data.task_id;
            currentTaskId = taskId;
            localStorage.setItem('janus_taskId', taskId);
            localStorage.setItem('janus_taskUrl', url);
            requestNotificationPermission();
            startPolling(taskId);
        })
        .catch(err => {
            showError(err.message);
        });
    });

    // Stop button event listener
    btnStopTask.addEventListener('click', () => {
        if (!currentTaskId) return;
        if (confirm('¿Estás seguro de que deseas detener el doblaje? Podrás continuar desde esta misma frase más tarde usando la misma caché.')) {
            // Cancelar inmediatamente el polling del cliente y restaurar la vista
            if (pollInterval) clearInterval(pollInterval);
            const stoppingTaskId = currentTaskId;
            currentTaskId = null;
            localStorage.removeItem('janus_taskId');
            localStorage.removeItem('janus_taskUrl');
            
            processingOverlay.classList.add('hidden');
            startOverlay.classList.remove('hidden');
            globalStatus.innerHTML = `<span class="dot" style="background-color: #ff4757; box-shadow: 0 0 8px #ff4757;"></span> Deteniendo...`;
            
            fetch(`/api/cancel/${stoppingTaskId}`, {
                method: 'POST'
            })
            .then(res => {
                if (!res.ok) throw new Error('Error al solicitar detener la tarea.');
                return res.json();
            })
            .then(data => {
                console.log('Task cancellation requested:', data);
                globalStatus.innerHTML = `<span class="dot" style="background-color: #ff4757; box-shadow: 0 0 8px #ff4757;"></span> Detenido por usuario`;
            })
            .catch(err => {
                console.error('Error in cancellation request:', err);
                alert(`Error al detener la tarea: ${err.message}`);
            });
        }
    });

    // Polling function
    function startPolling(taskId) {
        if (pollInterval) clearInterval(pollInterval);
        
        pollInterval = setInterval(() => {
            fetch(`/api/status/${taskId}`)
            .then(res => {
                if (!res.ok) throw new Error('Error al consultar el estado.');
                return res.json();
            })
            .then(data => {
                updateStatus(data.status, data.progress, data.error);
                
                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    localStorage.removeItem('janus_taskId');
                    localStorage.removeItem('janus_taskUrl');
                    notifyCompleted();
                    loadVideo(data.result);
                    // Si venía de un reensamblado del Studio, restaurar el botón
                    // y refrescar el timeline para que quede usable de inmediato.
                    if (studioFinalizing) {
                        studioFinalizing = false;
                        resetStudioFinalizeButton();
                        if (currentTaskId && typeof loadStudioData === 'function') {
                            loadStudioData(currentTaskId);
                        }
                    }
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    localStorage.removeItem('janus_taskId');
                    localStorage.removeItem('janus_taskUrl');
                    currentTaskId = null;
                    if (studioFinalizing) {
                        studioFinalizing = false;
                        resetStudioFinalizeButton();
                    }
                    notifyFailed(data.error || 'Ocurrió un error desconocido.');
                    showError(data.error || 'Ocurrió un error desconocido.');
                } else if (data.status === 'stopped') {
                    clearInterval(pollInterval);
                    localStorage.removeItem('janus_taskId');
                    localStorage.removeItem('janus_taskUrl');
                    currentTaskId = null;
                    if (studioFinalizing) {
                        studioFinalizing = false;
                        resetStudioFinalizeButton();
                    }
                    notifyFailed(data.error || 'Doblaje detenido por el usuario.');
                    showStopped(data.error || 'Doblaje detenido por el usuario.');
                }
            })
            .catch(err => {
                clearInterval(pollInterval);
                localStorage.removeItem('janus_taskId');
                localStorage.removeItem('janus_taskUrl');
                currentTaskId = null;
                if (studioFinalizing) {
                    studioFinalizing = false;
                    resetStudioFinalizeButton();
                }
                showError(err.message);
            });
        }, 2000);
    }

    // Update the processing overlay status and progress
    function updateStatus(status, progress, errorMsg = '') {
        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
        
        let statusDotColor = '#10b981'; // Green
        let statusText = 'Procesando...';

        switch (status) {
            case 'queued':
                processTitle.textContent = 'En cola';
                processDesc.textContent = 'Esperando recursos del servidor...';
                statusText = 'En cola';
                statusDotColor = '#6b7280';
                break;
            case 'downloading':
                processTitle.textContent = 'Descargando Video';
                processDesc.textContent = 'Descargando desde YouTube en el servidor...';
                statusText = 'Descargando...';
                statusDotColor = '#3b82f6';
                break;
            case 'separating':
                processTitle.textContent = 'Separando Voces (Demucs)';
                processDesc.textContent = 'Separando el speaker del fondo usando Demucs offline (Aceleración GPU)...';
                statusText = 'Separando voces...';
                statusDotColor = '#60a5fa';
                break;
            case 'transcribing':
                processTitle.textContent = 'Transcribiendo Audio';
                processDesc.textContent = 'Ejecutando WhisperX...';
                statusText = 'Transcribiendo...';
                statusDotColor = '#f59e0b';
                break;
            case 'translating':
                processTitle.textContent = 'Traduciendo Diálogos';
                processDesc.textContent = 'Traduciendo JSON de transcripción con Ollama...';
                statusText = 'Traduciendo...';
                statusDotColor = '#8b5cf6';
                break;
            case 'synthesizing':
                processTitle.textContent = 'Sintetizando Voz';
                processDesc.textContent = selectSpeaker.value === 'windows_native' 
                    ? `Generando audio doblado al ${selectTargetLang.value === 'Spanish' ? 'español' : 'inglés'} con TTS Nativo de Windows...` 
                    : `Generando audio doblado al ${selectTargetLang.value === 'Spanish' ? 'español' : 'inglés'} con el modelo de síntesis (TTS)...`;
                statusText = 'Generando TTS...';
                statusDotColor = '#d946ef';
                break;
            case 'transcribing_dub':
                processTitle.textContent = 'Alineando Doblaje';
                processDesc.textContent = 'Transcribiendo audio doblado para obtener tiempos...';
                statusText = 'Alineando...';
                statusDotColor = '#ec4899';
                break;
            case 'synchronizing':
                processTitle.textContent = 'Sincronizando Voces';
                processDesc.textContent = 'Estirando y reacomodando pedazos de voz en la línea de tiempo...';
                statusText = 'Sincronizando...';
                statusDotColor = '#06b6d4';
                break;
            case 'merging':
                processTitle.textContent = 'Mezclando Video y Audio';
                processDesc.textContent = 'Incrustando audio sincronizado mediante Ffmpeg...';
                statusText = 'Mezclando...';
                statusDotColor = '#14b8a6';
                break;
            case 'completed':
                statusText = 'Doblaje Completado';
                statusDotColor = '#10b981';
                break;
            case 'failed':
                statusText = 'Error en el doblaje';
                statusDotColor = '#ef4444';
                break;
            case 'stopped':
                statusText = 'Detenido';
                statusDotColor = '#ff4757';
                break;
        }

        globalStatus.innerHTML = `<span class="dot" style="background-color: ${statusDotColor}; box-shadow: 0 0 8px ${statusDotColor};"></span> ${statusText}`;
    }

    // Show stopped message
    function showStopped(message) {
        processingOverlay.classList.add('hidden');
        startOverlay.classList.remove('hidden');
        alert(`El doblaje se ha detenido: ${message}`);
        globalStatus.innerHTML = `<span class="dot" style="background-color: #ff4757; box-shadow: 0 0 8px #ff4757;"></span> Detenido`;
    }

    // Show error message
    function showError(message) {
        processingOverlay.classList.add('hidden');
        startOverlay.classList.remove('hidden');
        alert(`Error: ${message}`);
        globalStatus.innerHTML = `<span class="dot" style="background-color: #ef4444; box-shadow: 0 0 8px #ef4444;"></span> Error`;
    }

    // Load video and setup subtitles
    function loadVideo(result) {
        processingOverlay.classList.add('hidden');
        videoPlayer.classList.remove('hidden');
        btnNew.classList.remove('hidden');
        
        videoPlayer.src = result.video_url;
        videoPlayer.load();
        
        // Build subtitle alignment data
        subtitleData = [];
        const origChunks = result.original_json.chunks || [];
        const transChunks = result.translated_json.chunks || [];
        
        for (let i = 0; i < origChunks.length; i++) {
            const orig = origChunks[i];
            const trans = transChunks[i] || { text: '' };
            
            if (orig.timestamp) {
                subtitleData.push({
                    start: orig.timestamp[0],
                    end: orig.timestamp[1],
                    source: orig.text,
                    target: trans.text
                });
            }
        }
        
        renderSubtitles();
        
        // Render execution timers
        const timersSection = document.getElementById('timers-section');
        const timersList = document.getElementById('timers-list');
        if (timersSection && timersList && result.timing_report) {
            timersSection.classList.remove('hidden');
            renderTimersReport(result.timing_report, timersList);
        } else if (timersSection) {
            timersSection.classList.add('hidden');
        }
        
        // Auto play or redirect to Studio
        if (openStudioOnLoad) {
            openStudioOnLoad = false;
            openStudioView();
        } else {
            videoPlayer.play();
        }
    }

    // Render execution times bar graph
    function renderTimersReport(timingReport, container) {
        container.innerHTML = '';
        const totalDuration = timingReport.total_duration || 1;
        
        const stepLabels = {
            "1_download_and_extract": { name: "Descarga de Video", icon: "fa-download", color: "var(--accent-teal)" },
            "1b_demucs_separation": { name: "Separación Vocal (Demucs)", icon: "fa-scissors", color: "#60a5fa" },
            "2_transcription": { name: "Transcripción (WhisperX)", icon: "fa-closed-captioning", color: "#f59e0b" },
            "3_translation": { name: "Traducción (Ollama)", icon: "fa-language", color: "#8b5cf6" },
            "4_tts_synthesis": { name: selectSpeaker.value === 'windows_native' ? "Doblaje (Windows TTS)" : "Doblaje (TTS)", icon: "fa-microphone", color: "#d946ef" },
            "5_synchronization": { name: "Sincronización Temporal", icon: "fa-clock", color: "#06b6d4" },
            "5b_audio_mixing": { name: "Mezcla de Audio", icon: "fa-sliders", color: "#14b8a6" },
            "6_video_merging": { name: "Ensamble de Video", icon: "fa-film", color: "#10b981" },
            "7_qa_verification": { name: "Verificación de Calidad QA", icon: "fa-clipboard-check", color: "#ec4899" }
        };
        
        for (const [key, duration] of Object.entries(timingReport)) {
            if (key === 'total_duration' || !stepLabels[key]) continue;
            
            const stepInfo = stepLabels[key];
            const pct = ((duration / totalDuration) * 100).toFixed(1);
            
            const timerItem = document.createElement('div');
            timerItem.className = 'timer-item';
            timerItem.innerHTML = `
                <div class="timer-item-header">
                    <span class="timer-item-title">
                        <i class="fa-solid ${stepInfo.icon}" style="color: ${stepInfo.color}"></i> 
                        ${stepInfo.name}
                    </span>
                    <span class="timer-item-val">${duration.toFixed(1)}s</span>
                </div>
                <div class="timer-bar-container">
                    <div class="timer-bar" style="width: ${pct}%; background-color: ${stepInfo.color}"></div>
                </div>
                <div class="timer-item-footer">
                    <span>${pct}% del total</span>
                </div>
            `;
            container.appendChild(timerItem);
        }
        
        const totalItem = document.createElement('div');
        totalItem.className = 'timer-total-summary';
        totalItem.innerHTML = `
            <div class="total-label">Tiempo Total de Ejecución</div>
            <div class="total-value">${totalDuration.toFixed(1)}s</div>
        `;
        container.appendChild(totalItem);
    }

    // Render subtitle lines into the viewport
    function renderSubtitles() {
        subtitlesViewport.innerHTML = '';
        
        if (subtitleData.length === 0) {
            subtitlesViewport.innerHTML = '<p class="empty-subs-msg">No se encontraron subtítulos.</p>';
            return;
        }

        subtitleData.forEach((sub, index) => {
            const line = document.createElement('div');
            line.className = 'subtitle-line';
            line.dataset.index = index;
            
            // Apply language filter visibility classes
            if (!btnShowOriginal.classList.contains('active')) line.classList.add('hide-source');
            if (!btnShowTranslated.classList.contains('active')) line.classList.add('hide-target');
            
            line.innerHTML = `
                <div class="timestamp">${formatTime(sub.start)}</div>
                <div class="text-pair">
                    <div class="text-source">${sub.source}</div>
                    <div class="text-target">${sub.target}</div>
                </div>
            `;
            
            // Jump video to this subtitle's start time on click
            line.addEventListener('click', () => {
                videoPlayer.currentTime = sub.start;
                videoPlayer.play();
            });
            
            subtitlesViewport.appendChild(line);
        });
    }

    // Highlight current subtitle line based on player playback time
    videoPlayer.addEventListener('timeupdate', () => {
        const currentTime = videoPlayer.currentTime;
        let activeIndex = -1;
        
        for (let i = 0; i < subtitleData.length; i++) {
            if (currentTime >= subtitleData[i].start && currentTime <= subtitleData[i].end) {
                activeIndex = i;
                break;
            }
        }
        
        if (activeIndex !== activeSubIndex) {
            // Remove previous active highlights
            const lines = document.querySelectorAll('.subtitle-line');
            lines.forEach(line => line.classList.remove('active'));
            
            if (activeIndex !== -1) {
                const activeLine = lines[activeIndex];
                if (activeLine) {
                    activeLine.classList.add('active');
                    
                    // Scroll safely inside the viewport without jumping the main page
                    const subtitlesViewport = document.getElementById('subtitles-viewport');
                    const offset = activeLine.offsetTop - subtitlesViewport.offsetTop;
                    
                    subtitlesViewport.scrollTo({
                        top: Math.max(0, offset - 40), // 40px padding from the top
                        behavior: 'smooth'
                    });
                }
            }
            activeSubIndex = activeIndex;
        }
    });

    // ==========================================
    // STUDIO v3.0 LOGIC
    // ==========================================
    const btnCloseStudio = document.getElementById('btn-close-studio');
    const selectStudioCache = document.getElementById('select-studio-cache');
    const btnStudioLoadCache = document.getElementById('btn-studio-load-cache');
    const btnMuteDubbed = document.getElementById('btn-mute-dubbed');
    const btnMuteOriginal = document.getElementById('btn-mute-original');
    const btnMutePhrase = document.getElementById('btn-mute-phrase');
    const btnVisDubbed = document.getElementById('btn-vis-dubbed');
    const btnVisOriginal = document.getElementById('btn-vis-original');
    
    let isDubbedMuted = false;
    let isOriginalMuted = false;
    let isPhraseMuted = false;
    
    let isV2Visible = true; // Dubbed
    let isV1Visible = false;  // Original
    
    const homeView = document.getElementById('home-view');
    const studioView = document.getElementById('studio-view');
    const studioVideoWrapper = document.getElementById('studio-video-wrapper');
    const playerWrapper = document.querySelector('.player-wrapper');
    
    // Nav elements
    const navHome = document.getElementById('nav-home');
    const navStudio = document.getElementById('nav-studio');
    
    // Timeline elements
    const trackEnglish = document.getElementById('track-english');
    const trackDubbed = document.getElementById('track-dubbed');
    const timelineRuler = document.getElementById('timeline-ruler');
    const trackVideoDubbed = document.getElementById('track-video-dubbed');
    const trackVideoOrig = document.getElementById('track-video-orig');
    const blockVideoDubbed = document.getElementById('block-video-dubbed');
    const blockVideoOrig = document.getElementById('block-video-orig');
    
    // Inspector elements
    const inspectorBlockName = document.getElementById('inspector-block-name');
    const inspectorContent = document.getElementById('inspector-content');
    const studioTextarea = document.getElementById('studio-textarea');
    const btnStudioPlayOrig = document.getElementById('btn-studio-play-orig');
    const btnStudioPlayDub = document.getElementById('btn-studio-play-dub');
    const btnStudioRegenerate = document.getElementById('btn-studio-regenerate');
    const btnStudioDelete = document.getElementById('btn-studio-delete');
    const studioAudioPlayer = document.getElementById('studio-audio-player');
    const btnStudioFinalize = document.getElementById('btn-studio-finalize');
    const btnStudioSplit = document.getElementById('btn-studio-split');
    const btnStudioLoadOther = document.getElementById('btn-studio-load-other');

    let studioActiveBlock = null;
    let studioData = null;
    const PIXELS_PER_SECOND = 40;
    let studioSourceLanguage = 'English';
    let studioTargetLanguage = 'Spanish';
    const btnRetranscribeSingle = document.getElementById('btn-studio-retranscribe-single');
    const lblTranscript = document.getElementById('lbl-transcript');
    const selectStudioSourceLang = document.getElementById('select-studio-source-lang');
    const selectStudioTargetLang = document.getElementById('select-studio-target-lang');
    const selectStudioModel = document.getElementById('select-studio-model');
    const selectStudioWhisperModel = document.getElementById('select-studio-whisper-model');
    const btnStudioTranslate = document.getElementById('btn-studio-translate');
    
    // Range selection state for gap re-transcription
    let rangeStartPhrase = null;
    let rangeEndPhrase = null;
    const rangeSelectionPanel = document.getElementById('range-selection-panel');
    const rangeInfo = document.getElementById('range-info');
    const rangeGapInfo = document.getElementById('range-gap-info');
    const btnRetranscribe = document.getElementById('btn-studio-retranscribe');
    const btnClearRange = document.getElementById('btn-clear-range');

    function loadStudioModels() {
        if (!selectStudioModel) return;
        fetch('/api/models')
            .then(res => res.json())
            .then(data => {
                const models = data.models || [];
                selectStudioModel.innerHTML = '<option value="">(Usar modelo del inicio)</option>';
                models.forEach(modelName => {
                    const opt = document.createElement('option');
                    opt.value = modelName;
                    if (modelName.includes('cloud')) {
                        opt.textContent = `☁️ ${modelName}`;
                    } else if (modelName === 'gemma4:e2b-it-qat') {
                        opt.textContent = `⭐ (Recomendado) ${modelName}`;
                    } else {
                        opt.textContent = modelName;
                    }
                    selectStudioModel.appendChild(opt);
                });
                // Inherit from "papá" by default
                if (selectModel && selectModel.value) {
                    for (let i = 0; i < selectStudioModel.options.length; i++) {
                        if (selectStudioModel.options[i].value === selectModel.value) {
                            selectStudioModel.selectedIndex = i;
                            break;
                        }
                    }
                }
            })
            .catch(() => {
                selectStudioModel.innerHTML = '<option value="">(Error al cargar modelos)</option>';
            });
    }

    function fetchStudioMeta() {
        if (!currentTaskId) return;
        fetch(`/api/studio/${currentTaskId}/meta`)
            .then(res => res.json())
            .then(meta => {
                if (meta.status === 'ok') {
                    studioSourceLanguage = meta.source_language || 'English';
                    studioTargetLanguage = meta.target_language || 'Spanish';
                    updateStudioInspectorLabels();
                }
            })
            .catch(() => {});
    }

    function updateStudioInspectorLabels() {
        if (btnStudioPlayOrig) btnStudioPlayOrig.innerHTML = `<i class="fa-solid fa-ear-listen"></i> ${studioSourceLanguage}`;
        if (btnStudioPlayDub) btnStudioPlayDub.innerHTML = `<i class="fa-solid fa-play"></i> ${studioTargetLanguage}`;
        if (lblTranscript) lblTranscript.textContent = `TRANSCRIPT (${studioTargetLanguage})`;
        if (selectStudioSourceLang) selectStudioSourceLang.value = studioSourceLanguage;
        if (selectStudioTargetLang) selectStudioTargetLang.value = studioTargetLanguage;
        const dubbedLabel = document.querySelector('.dubbed-track');
        const origLabel = document.querySelector('.english-track');
        if (dubbedLabel) dubbedLabel.textContent = `A1 | Doblaje (${studioTargetLanguage})`;
        if (origLabel) origLabel.textContent = `A2 | Original (${studioSourceLanguage})`;
    }

    function openStudioView() {
        // Reset button states (they may be stuck from a previous render)
        studioFinalizing = false;
        if (btnStudioFinalize) {
            btnStudioFinalize.disabled = false;
            btnStudioFinalize.innerHTML = '<i class="fa-solid fa-film"></i> Ensamblar Video Final';
        }
        if (btnStudioSplit) {
            btnStudioSplit.disabled = false;
            btnStudioSplit.innerHTML = '<i class="fa-solid fa-scissors"></i> Split Frase';
        }

        homeView.classList.add('hidden');
        studioView.classList.remove('hidden');
        studioVideoWrapper.appendChild(videoPlayer);
        videoPlayer.classList.remove('hidden');
        if (navHome) navHome.classList.remove('active');
        if (navStudio) navStudio.classList.add('active');
        
        loadStudioCaches(); // Populate the top right dropdown
        loadStudioModels(); // Load Ollama models into inspector
        
        // Inherit whisper model from "papá"
        if (selectStudioWhisperModel && selectWhisperModel && selectWhisperModel.value) {
            selectStudioWhisperModel.value = selectWhisperModel.value;
        }
        
        const cacheOverlay = document.getElementById('studio-cache-overlay');
        
        if (currentTaskId) {
            if (cacheOverlay) cacheOverlay.classList.add('hidden');
            videoPlayer.classList.remove('hidden');
            // In Studio, we always use the original video so previews work correctly over it
            if (btnVisDubbed) btnVisDubbed.closest('.track-label').classList.remove('hidden');
            
            // Apply priority logic (V2 over V1)
            isV2Visible = true;
            isV1Visible = false;
            
            loadStudioData();
            updateVideoSource();
        } else {
            if (cacheOverlay) cacheOverlay.classList.remove('hidden');
            videoPlayer.classList.add('hidden');

            
            // Reset inspector and wait for user to select a cache
            studioActiveBlock = null;
            document.getElementById('inspector-block-name').innerHTML = 'Cargando sesión...';
            document.getElementById('inspector-content').classList.add('hidden');
            
            // Clear timelines
            document.getElementById('track-english').innerHTML = '';
            document.getElementById('track-dubbed').innerHTML = '';
            document.getElementById('track-video-dubbed').innerHTML = '<div class="timeline-block video-block" style="width: 100%;"></div>';
        }
    }

    function openHomeView() {
        playerWrapper.appendChild(videoPlayer);
        studioView.classList.add('hidden');
        homeView.classList.remove('hidden');
        if (navHome) navHome.classList.add('active');
        if (navStudio) navStudio.classList.remove('active');
        
        // In Home view, we always show the finalized dubbed video
        if (currentTaskId) {
            if (!videoPlayer.src.includes(`/api/stream/${currentTaskId}`)) {
                videoPlayer.src = `/api/stream/${currentTaskId}?t=${new Date().getTime()}`;
            }
        }
    }

    function loadStudioCaches() {
        if (!selectStudioCache) return;
        fetch('/api/caches?studio=true')
            .then(res => res.json())
            .then(data => {
                const caches = data.caches || [];
                selectStudioCache.innerHTML = caches.length === 0
                    ? '<option value="">(Sin videos doblados — procesa uno primero)</option>'
                    : '<option value="">Seleccionar Caché para Cargar...</option>';
                caches.forEach(c => {
                    const option = document.createElement('option');
                    option.value = c.id;
                    // Mostrar metadatos si existen
                    if (c.meta) {
                        const srcLang = c.meta.source_language || 'English';
                        const tgtLang = c.meta.target_language || 'Spanish';
                        option.textContent = `${c.id} (${srcLang} → ${tgtLang})`;
                    } else {
                        option.textContent = c.id;
                    }
                    if (c.id === currentTaskId) option.selected = true;
                    selectStudioCache.appendChild(option);
                });
            })
            .catch(err => console.error("Error cargando cachés para estudio:", err));
    }

    if (navStudio) navStudio.addEventListener('click', openStudioView);
    
    if (btnCloseStudio) btnCloseStudio.addEventListener('click', openHomeView);
    if (navHome) navHome.addEventListener('click', openHomeView);

    // "Cargar Otro Video" - reset studio to cache selection
    if (btnStudioLoadOther) {
        btnStudioLoadOther.addEventListener('click', () => {
            videoPlayer.pause();
            videoPlayer.src = '';
            videoPlayer.classList.add('hidden');
            currentTaskId = null;
            localStorage.removeItem('janus_taskId');
            localStorage.removeItem('janus_taskUrl');
            studioActiveBlock = null;
            document.getElementById('inspector-block-name').innerHTML = 'Selecciona un bloque de audio en la línea de tiempo inferior...';
            document.getElementById('inspector-content').classList.add('hidden');
            document.getElementById('track-english').innerHTML = '';
            document.getElementById('track-dubbed').innerHTML = '';
            document.getElementById('track-video-dubbed').innerHTML = '<div class="timeline-block video-block" style="width: 100%;"></div>';
            const cacheOverlay = document.getElementById('studio-cache-overlay');
            if (cacheOverlay) cacheOverlay.classList.remove('hidden');
            loadStudioCaches();
        });
    }

    if (btnStudioLoadCache) {
        btnStudioLoadCache.addEventListener('click', () => {
            const selectedCache = selectStudioCache.value;
            if (!selectedCache) {
                alert('Por favor, selecciona un caché de la lista.');
                return;
            }
            currentTaskId = selectedCache;
            const cacheOverlay = document.getElementById('studio-cache-overlay');
            if (cacheOverlay) cacheOverlay.classList.add('hidden');
            videoPlayer.classList.remove('hidden');

            
            isV2Visible = true;
            isV1Visible = false;
            
            loadStudioData();
            updateVideoSource();
        });
    }

    function updateVideoSource() {
        if (!currentTaskId) return;
        const wasPlaying = !videoPlayer.paused;
        const currentTime = videoPlayer.currentTime || 0;
        
        if (isV2Visible) {
            // Force re-assignment to ensure it loads even if it was moved in the DOM
            videoPlayer.src = `/api/stream/${currentTaskId}?t=${new Date().getTime()}`;
            videoPlayer.muted = isDubbedMuted;
        } else if (isV1Visible) {
            videoPlayer.src = `/api/stream_original/${currentTaskId}?t=${new Date().getTime()}`;
            videoPlayer.muted = isOriginalMuted;
        }
        
        // Force the video element to load to prevent blank screen
        videoPlayer.load();
        
        if (btnVisDubbed) {
            btnVisDubbed.innerHTML = isV2Visible ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash text-gray"></i>';
            btnVisDubbed.style.color = isV2Visible ? '#b8860b' : '';
        }
        if (btnVisOriginal) {
            btnVisOriginal.innerHTML = isV1Visible ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash text-gray"></i>';
            btnVisOriginal.style.color = isV1Visible ? 'white' : '';
        }
        
        if (blockVideoDubbed) blockVideoDubbed.style.opacity = isV2Visible ? '1' : '0.2';
        if (blockVideoOrig) blockVideoOrig.style.opacity = isV1Visible ? '1' : '0.2';
        
        if (videoPlayer.readyState > 0) {
            try {
                videoPlayer.currentTime = currentTime;
                if (wasPlaying) videoPlayer.play();
            } catch(e) {}
        } else {
            videoPlayer.addEventListener('loadedmetadata', function onMeta() {
                try {
                    videoPlayer.currentTime = currentTime;
                    if (wasPlaying) videoPlayer.play();
                } catch(e) {}
                // Re-render timeline now that we have the real duration
                if (studioData && studioData.length > 0) {
                    console.log('[Studio] Video metadata loaded, re-rendering timeline with duration:', videoPlayer.duration);
                    renderTimeline();
                }
                videoPlayer.removeEventListener('loadedmetadata', onMeta);
            });
        }
    }

    if (btnVisDubbed) {
        btnVisDubbed.addEventListener('click', () => {
            isV2Visible = !isV2Visible;
            updateVideoSource();
        });
    }

    if (btnVisOriginal) {
        btnVisOriginal.addEventListener('click', () => {
            isV1Visible = !isV1Visible;
            updateVideoSource();
        });
    }

    function updateMuteUI(btn, isMuted) {
        if (!btn) return;
        btn.innerHTML = isMuted ? '<i class="fa-solid fa-volume-xmark" style="color: #ff4d4d;"></i>' : '<i class="fa-solid fa-volume-high"></i>';
    }

    if (btnMuteDubbed) {
        btnMuteDubbed.addEventListener('click', () => {
            isDubbedMuted = !isDubbedMuted;
            updateMuteUI(btnMuteDubbed, isDubbedMuted);
            if (isV2Visible) {
                videoPlayer.muted = isDubbedMuted;
            }
        });
    }

    if (btnMuteOriginal) {
        btnMuteOriginal.addEventListener('click', () => {
            isOriginalMuted = !isOriginalMuted;
            updateMuteUI(btnMuteOriginal, isOriginalMuted);
            if (!isV2Visible && isV1Visible) {
                videoPlayer.muted = isOriginalMuted;
            }
        });
    }

    if (btnMutePhrase) {
        btnMutePhrase.addEventListener('click', () => {
            isPhraseMuted = !isPhraseMuted;
            updateMuteUI(btnMutePhrase, isPhraseMuted);
            if (studioAudioPlayer) {
                studioAudioPlayer.muted = isPhraseMuted;
            }
        });
    }

    function loadStudioData() {
        console.log('[Studio] loadStudioData called for task:', currentTaskId);
        fetchStudioMeta();
        fetch(`/api/studio/${currentTaskId}/data`)
            .then(res => {
                console.log('[Studio] API response status:', res.status);
                if (res.status === 404) {
                    alert('Esta caché no tiene datos del editor. Procesa el video hasta el final antes de abrir el Estudio.');
                    return null;
                }
                return res.json();
            })
            .then(data => {
                if (!data) return;
                console.log('[Studio] API data received:', data.status, 'phrases:', data.phrases ? data.phrases.length : 0);
                if (data.status === 'ok') {
                    studioData = data.phrases;
                    renderTimeline();
                } else {
                    console.error('[Studio] API returned non-ok status:', data);
                    alert("Error loading studio data.");
                }
            })
            .catch(err => {
                console.error("Studio error:", err);
                alert("No se pudo cargar el editor. Asegúrate de que el video haya sido completamente procesado.");
            });
    }

    function renderTimeline() {
        console.log('[Studio] renderTimeline called. studioData length:', studioData ? studioData.length : 'null');
        console.log('[Studio] trackEnglish:', trackEnglish, 'trackDubbed:', trackDubbed);
        
        if (!trackEnglish || !trackDubbed) {
            console.error('[Studio] CRITICAL: track DOM elements are null!');
            return;
        }
        
        trackEnglish.innerHTML = '';
        trackDubbed.innerHTML = '';
        timelineRuler.innerHTML = '';
        
        if (!studioData || studioData.length === 0) {
            console.warn('[Studio] No studioData to render');
            return;
        }
        
        let totalDuration = videoPlayer.duration || studioData[studioData.length - 1].end_time;
        if (isNaN(totalDuration) || totalDuration <= 0) totalDuration = 100; // fallback
        console.log('[Studio] totalDuration:', totalDuration, '(video.duration:', videoPlayer.duration, ')');
        
        const totalWidth = totalDuration * PIXELS_PER_SECOND;
        
        // Set track widths
        trackEnglish.style.width = `${totalWidth}px`;
        trackDubbed.style.width = `${totalWidth}px`;
        timelineRuler.style.width = `${totalWidth}px`;
        if (blockVideoDubbed) {
            blockVideoDubbed.style.width = `${totalWidth}px`;
            blockVideoDubbed.innerHTML = `<span style="position:relative; z-index:1; font-weight:bold; color: white;">Video Doblado (${formatTime(totalDuration)})</span>`;
        }
        if (blockVideoOrig) {
            blockVideoOrig.style.width = `${totalWidth}px`;
            blockVideoOrig.innerHTML = `<span style="position:relative; z-index:1; font-weight:bold; color: white;">Video Original (${formatTime(totalDuration)})</span>`;
        }
        
        // Build Ruler Marks
        for (let s = 0; s <= totalDuration; s += 10) {
            const mark = document.createElement('div');
            mark.style.position = 'absolute';
            mark.style.left = `${s * PIXELS_PER_SECOND}px`;
            mark.style.bottom = '0';
            mark.style.borderLeft = '1px solid rgba(0,0,0,0.15)';
            mark.style.height = '10px';
            mark.style.paddingLeft = '5px';
            mark.style.fontSize = '10px';
            mark.style.color = 'rgba(0,0,0,0.3)';
            mark.textContent = formatTime(s);
            timelineRuler.appendChild(mark);
        }
        
        // Render Blocks
        studioData.forEach(phrase => {
            const left = phrase.start_time * PIXELS_PER_SECOND;
            const width = (phrase.end_time - phrase.start_time) * PIXELS_PER_SECOND;
            
            // English Block
            const engBlock = document.createElement('div');
            engBlock.className = 'timeline-block english-block';
            engBlock.style.left = `${left}px`;
            engBlock.style.width = `${Math.max(width, 30)}px`;
            engBlock.innerHTML = `<div class="waveform-bg"></div><span style="position:relative; z-index:1;">${phrase.text}</span>`;
            trackEnglish.appendChild(engBlock);
            
            // Dubbed Block (Interactive)
            const dubBlock = document.createElement('div');
            dubBlock.className = 'timeline-block dubbed-block';
            dubBlock.style.left = `${left}px`;
            dubBlock.style.width = `${Math.max(width, 30)}px`;
            dubBlock.innerHTML = `<div class="waveform-bg"></div><span style="position:relative; z-index:1;">${phrase.text}</span>`;
            
            dubBlock.addEventListener('click', (e) => {
                if (e.shiftKey && studioActiveBlock) {
                    // Shift+Click = select range end
                    const startIdx = studioActiveBlock.phrase_index;
                    const endIdx = phrase.phrase_index;
                    
                    // Allow same phrase = single-phrase retranscribe
                    if (startIdx === endIdx) {
                        rangeStartPhrase = phrase;
                        rangeEndPhrase = phrase;
                        const rangePhraseDuration = phrase.end_time - phrase.start_time;
                        rangeInfo.innerHTML = `<i class="fa-solid fa-rotate"></i> Frase #${phrase.phrase_index} [${formatTime(phrase.start_time)} → ${formatTime(phrase.end_time)}]`;
                        rangeGapInfo.textContent = `Audio: ${rangePhraseDuration.toFixed(2)}s para re-transcribir`;
                        document.querySelectorAll('.dubbed-block').forEach(b => b.classList.remove('selected', 'range-selected'));
                        dubBlock.classList.add('selected');
                        if (rangeSelectionPanel) rangeSelectionPanel.classList.remove('hidden');
                        inspectorBlockName.innerHTML = `<i class="fa-solid fa-language" style="color: #ffa500;"></i> Re-transcribir: Frase #${phrase.phrase_index}`;
                        return;
                    }
                    
                    // Ensure start < end
                    if (startIdx < endIdx) {
                        rangeStartPhrase = studioData.find(p => p.phrase_index === startIdx);
                        rangeEndPhrase = phrase;
                    } else {
                        rangeStartPhrase = phrase;
                        rangeEndPhrase = studioData.find(p => p.phrase_index === startIdx);
                    }
                    
                    // Highlight range
                    document.querySelectorAll('.dubbed-block').forEach(b => b.classList.remove('selected', 'range-selected'));
                    const allDubBlocks = document.querySelectorAll('.dubbed-block');
                    const minIdx = rangeStartPhrase.phrase_index;
                    const maxIdx = rangeEndPhrase.phrase_index;
                    allDubBlocks.forEach((b, i) => {
                        const phraseForBlock = studioData[i];
                        if (phraseForBlock && phraseForBlock.phrase_index >= minIdx && phraseForBlock.phrase_index <= maxIdx) {
                            b.classList.add('range-selected');
                        }
                    });
                    
                    // Show range panel
                    const gapDuration = rangeEndPhrase.start_time - rangeStartPhrase.end_time;
                    rangeInfo.innerHTML = `<i class="fa-solid fa-arrow-right"></i> Frase #${rangeStartPhrase.phrase_index} [${formatTime(rangeStartPhrase.end_time)}] → Frase #${rangeEndPhrase.phrase_index} [${formatTime(rangeEndPhrase.start_time)}]`;
                    rangeGapInfo.textContent = `Gap: ${gapDuration.toFixed(2)}s de audio sin transcribir`;
                    if (rangeSelectionPanel) rangeSelectionPanel.classList.remove('hidden');
                    inspectorBlockName.innerHTML = `<i class="fa-solid fa-arrows-left-right-to-line" style="color: #ffa500;"></i> Rango: Frase #${rangeStartPhrase.phrase_index} → #${rangeEndPhrase.phrase_index}`;
                    
                } else {
                    // Normal click = select single block
                    clearRangeSelection();
                    document.querySelectorAll('.dubbed-block').forEach(b => b.classList.remove('selected', 'range-selected'));
                    dubBlock.classList.add('selected');
                    
                    selectStudioBlock(phrase);
                    videoPlayer.currentTime = phrase.start_time;
                }
            });
            
            trackDubbed.appendChild(dubBlock);
        });
    }
    
    function clearRangeSelection() {
        rangeStartPhrase = null;
        rangeEndPhrase = null;
        document.querySelectorAll('.dubbed-block').forEach(b => b.classList.remove('range-selected'));
        if (rangeSelectionPanel) rangeSelectionPanel.classList.add('hidden');
    }

    function selectStudioBlock(phrase) {
        studioActiveBlock = phrase;
        inspectorBlockName.innerHTML = `<i class="fa-solid fa-cube text-teal"></i> Frase #${phrase.phrase_index} [${formatTime(phrase.start_time)} - ${formatTime(phrase.end_time)}]`;
        studioTextarea.value = phrase.text;
        inspectorContent.classList.remove('hidden');
    }

    btnStudioPlayOrig.addEventListener('click', () => {
        if (!studioActiveBlock) return;
        studioAudioPlayer.src = `/api/studio/${currentTaskId}/audio/original?start=${studioActiveBlock.start_time}&end=${studioActiveBlock.end_time}`;
        studioAudioPlayer.play();
        
        if (typeof videoPlayer !== 'undefined' && videoPlayer) {
            videoPlayer.currentTime = studioActiveBlock.start_time;
            videoPlayer.play();
            studioAudioPlayer.onended = () => videoPlayer.pause();
        }
    });

    btnStudioPlayDub.addEventListener('click', () => {
        if (!studioActiveBlock) return;
        // Anti-cache string
        studioAudioPlayer.src = `/api/studio/${currentTaskId}/audio/dubbed/${studioActiveBlock.phrase_index}?t=${new Date().getTime()}`;
        studioAudioPlayer.play();
        
        if (typeof videoPlayer !== 'undefined' && videoPlayer) {
            videoPlayer.currentTime = studioActiveBlock.start_time;
            videoPlayer.play();
            studioAudioPlayer.onended = () => videoPlayer.pause();
        }
    });

    btnStudioRegenerate.addEventListener('click', () => {
        if (!studioActiveBlock) return;
        
        btnStudioRegenerate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Regenerando (Toma ~5s)...';
        btnStudioRegenerate.disabled = true;
        
        const selectStudioSpeaker = document.getElementById('select-studio-speaker');
        const selectStudioTtsModel = document.getElementById('select-studio-tts-model');

        const payload = {
            phrase_index: studioActiveBlock.phrase_index,
            text: studioTextarea.value,
            speaker: selectStudioSpeaker ? selectStudioSpeaker.value : selectSpeaker.value,
            tts_model: selectStudioTtsModel ? selectStudioTtsModel.value : selectTtsModel.value,
            tts_cfg: parseFloat(inputTtsCfg.value),
            tts_steps: parseInt(inputTtsSteps.value)
        };
        
        fetch(`/api/studio/${currentTaskId}/reprocess`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            btnStudioRegenerate.innerHTML = '<i class="fa-solid fa-check"></i> ¡Éxito! Reproduce el Español.';
            studioActiveBlock.text = studioTextarea.value; // Update local state for UI
            
            setTimeout(() => {
                btnStudioRegenerate.innerHTML = '<i class="fa-solid fa-rotate"></i> Regenerate Audio (5s)';
                btnStudioRegenerate.disabled = false;
            }, 3000);
            
            // Auto play the newly generated dub
            btnStudioPlayDub.click();
        })
        .catch(err => {
            alert('Error regenerando audio: ' + err.message);
            btnStudioRegenerate.innerHTML = '<i class="fa-solid fa-rotate"></i> Regenerate Audio (5s)';
            btnStudioRegenerate.disabled = false;
        });
    });

    btnStudioDelete.addEventListener('click', () => {
        if (!studioActiveBlock || !currentTaskId) return;
        if (confirm(`¿Estás seguro de que quieres eliminar la frase ${studioActiveBlock.phrase_index}? Esto re-indexará las frases y no se puede deshacer.`)) {
            
            btnStudioDelete.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Eliminando...';
            btnStudioDelete.disabled = true;
            
            fetch(`/api/studio/${currentTaskId}/delete/${studioActiveBlock.phrase_index}`, {
                method: 'POST'
            })
            .then(res => {
                if (!res.ok) throw new Error('Network response was not ok');
                return res.json();
            })
            .then(data => {
                btnStudioDelete.innerHTML = '<i class="fa-solid fa-check"></i> ¡Frase Eliminada!';
                setTimeout(() => {
                    if (btnStudioDelete) {
                        btnStudioDelete.innerHTML = '<i class="fa-solid fa-trash"></i> Eliminar Frase';
                        btnStudioDelete.disabled = false;
                    }
                }, 2000);
                
                // Refresh the timeline data
                studioActiveBlock = null;
                studioTextarea.value = '';
                inspectorContent.innerHTML = '<p style="color: #888; text-align: center; margin-top: 50px;">Selecciona un bloque para ver los detalles.</p>';
                loadStudioData(currentTaskId);
            })
            .catch(err => {
                alert('Error eliminando frase: ' + err.message);
                btnStudioDelete.innerHTML = '<i class="fa-solid fa-trash"></i> Eliminar Frase';
                btnStudioDelete.disabled = false;
            });
        }
    });

    function resetStudioFinalizeButton() {
        if (!btnStudioFinalize) return;
        btnStudioFinalize.disabled = false;
        btnStudioFinalize.innerHTML = '<i class="fa-solid fa-film"></i> Ensamblar Video Final';
    }

    btnStudioFinalize.addEventListener('click', () => {
        if (!currentTaskId) return;
        if (confirm("Se ensamblará el video final con los cambios actuales. ¿Continuar?")) {
            btnStudioFinalize.disabled = true;
            btnStudioFinalize.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Ensamblando...';
            
            fetch(`/api/studio/${currentTaskId}/finalize`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                // Show processing overlay and start polling
                startOverlay.classList.add('hidden');
                processingOverlay.classList.remove('hidden');
                videoPlayer.classList.add('hidden');
                btnNew.classList.add('hidden');
                subtitlesViewport.innerHTML = '<p class="empty-subs-msg">Ensamblando video final...</p>';
                
                updateStatus('queued', 0);
                studioFinalizing = true;
                startPolling(data.task_id);
            })
            .catch(err => {
                alert('Error finalizando: ' + err);
                studioFinalizing = false;
                resetStudioFinalizeButton();
            });
        }
    });

    // Split phrase at current video position
    if (btnStudioSplit) {
        btnStudioSplit.addEventListener('click', () => {
            if (!studioActiveBlock || !currentTaskId) {
                alert('Selecciona una frase primero.');
                return;
            }

            const phraseIdx = studioActiveBlock.phrase_index;
            const currentTime = videoPlayer.currentTime;
            
            // Get phrase boundaries
            const phraseStart = studioActiveBlock.start;
            const phraseEnd = studioActiveBlock.end;
            
            if (currentTime <= phraseStart || currentTime >= phraseEnd) {
                alert(`Posiciona el video dentro de la frase (${phraseStart.toFixed(2)}s - ${phraseEnd.toFixed(2)}s) para dividir.`);
                return;
            }
            
            if (!confirm(`¿Dividir frase ${phraseIdx} en ${currentTime.toFixed(2)}s?`)) return;
            
            btnStudioSplit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Dividiendo...';
            btnStudioSplit.disabled = true;
            
            fetch(`/api/studio/${currentTaskId}/split`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phrase_index: phraseIdx,
                    split_time: currentTime
                })
            })
            .then(res => res.json())
            .then(data => {
                btnStudioSplit.innerHTML = '<i class="fa-solid fa-check"></i> ¡Dividido!';
                setTimeout(() => {
                    btnStudioSplit.innerHTML = '<i class="fa-solid fa-scissors"></i> Split Frase';
                    btnStudioSplit.disabled = false;
                }, 1500);
                // Reload studio data
                loadStudioData();
            })
            .catch(err => {
                console.error('[Studio] Split error:', err);
                alert('Error al dividir: ' + err.message);
                btnStudioSplit.innerHTML = '<i class="fa-solid fa-scissors"></i> Split Frase';
                btnStudioSplit.disabled = false;
            });
        });
    }

    // Range selection: Clear button
    if (btnClearRange) {
        btnClearRange.addEventListener('click', () => {
            clearRangeSelection();
            inspectorBlockName.innerHTML = '<i class="fa-solid fa-cube text-gray"></i> Selecciona un bloque de audio en la línea de tiempo inferior...';
        });
    }

    // Range selection: Re-transcribe button
    if (btnRetranscribe) {
        btnRetranscribe.addEventListener('click', () => {
            if (!currentTaskId) {
                alert('No hay tarea cargada.');
                return;
            }
            
            // Determine mode: single phrase or range
            const isSingle = (rangeStartPhrase === rangeEndPhrase) && rangeStartPhrase !== null;
            const hasRange = rangeStartPhrase && rangeEndPhrase && !isSingle;
            
            if (!rangeStartPhrase && !studioActiveBlock) {
                alert('Selecciona una frase primero (clic normal) o un rango (clic + Shift+clic en otra).');
                return;
            }
            
            // Fallback: if no explicit range selected, use the active block alone
            if (!rangeStartPhrase && studioActiveBlock) {
                rangeStartPhrase = studioActiveBlock;
                rangeEndPhrase = studioActiveBlock;
            }
            
            const startIdx = rangeStartPhrase.phrase_index;
            const endIdx = rangeEndPhrase.phrase_index;
            
            const audioDuration = isSingle
                ? rangeStartPhrase.end_time - rangeStartPhrase.start_time
                : rangeEndPhrase.start_time - rangeStartPhrase.end_time;
            
            if (audioDuration < 0.3) {
                alert(`El segmento de audio es muy corto (${audioDuration.toFixed(2)}s).`);
                return;
            }
            
            btnRetranscribe.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> WhisperX transcribiendo...';
            btnRetranscribe.disabled = true;
            
            fetch(`/api/studio/${currentTaskId}/retranscribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_phrase_index: startIdx,
                    end_phrase_index: endIdx,
                    source_language: selectStudioSourceLang ? selectStudioSourceLang.value : 'English',
                    whisper_model: selectStudioWhisperModel ? selectStudioWhisperModel.value : 'large-v3-turbo'
                })
            })
            .then(res => {
                if (!res.ok) return res.json().then(e => { throw new Error(e.detail || 'Error del servidor'); });
                return res.json();
            })
            .then(data => {
                console.log('[Studio] Retranscribe result:', data);
                const newCount = data.new_phrases ? data.new_phrases.length : 0;
                btnRetranscribe.innerHTML = `<i class="fa-solid fa-check"></i> ¡${newCount} frase(s) encontrada(s)!`;
                
                // Clear range and reload timeline
                clearRangeSelection();
                loadStudioData();
                
                setTimeout(() => {
                    btnRetranscribe.innerHTML = '<i class="fa-solid fa-magnifying-glass-plus"></i> Re-transcribir con WhisperX';
                    btnRetranscribe.disabled = false;
                }, 3000);
            })
            .catch(err => {
                console.error('[Studio] Retranscribe error:', err);
                alert('Error re-transcribiendo: ' + err.message);
                btnRetranscribe.innerHTML = '<i class="fa-solid fa-magnifying-glass-plus"></i> Re-transcribir con WhisperX';
                btnRetranscribe.disabled = false;
            });
        });
    }

    // Single-phrase retranscribe (from inspector)
    if (btnRetranscribeSingle) {
        btnRetranscribeSingle.addEventListener('click', () => {
            if (!studioActiveBlock || !currentTaskId) {
                alert('Selecciona una frase primero.');
                return;
            }

            const sourceLang = selectStudioSourceLang ? selectStudioSourceLang.value : 'English';
            const phraseIdx = studioActiveBlock.phrase_index;

            btnRetranscribeSingle.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> WhisperX transcribiendo...';
            btnRetranscribeSingle.disabled = true;

            fetch(`/api/studio/${currentTaskId}/retranscribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_phrase_index: phraseIdx,
                    end_phrase_index: phraseIdx,
                    source_language: sourceLang,
                    whisper_model: selectStudioWhisperModel ? selectStudioWhisperModel.value : 'large-v3-turbo'
                })
            })
            .then(res => {
                if (!res.ok) return res.json().then(e => { throw new Error(e.detail || 'Error del servidor'); });
                return res.json();
            })
            .then(data => {
                const newCount = data.new_phrases ? data.new_phrases.length : 0;
                btnRetranscribeSingle.innerHTML = `<i class="fa-solid fa-check"></i> ¡${newCount} frase(s) encontrada(s)!`;
                loadStudioData();
                setTimeout(() => {
                    btnRetranscribeSingle.innerHTML = '<i class="fa-solid fa-magnifying-glass-plus"></i> Re-transcribir con WhisperX';
                    btnRetranscribeSingle.disabled = false;
                }, 3000);
            })
            .catch(err => {
                console.error('[Studio] Single retranscribe error:', err);
                alert('Error re-transcribiendo: ' + err.message);
                btnRetranscribeSingle.innerHTML = '<i class="fa-solid fa-magnifying-glass-plus"></i> Re-transcribir con WhisperX';
                btnRetranscribeSingle.disabled = false;
            });
        });
    }

    // Translate single phrase with AI (from inspector)
    if (btnStudioTranslate) {
        btnStudioTranslate.addEventListener('click', () => {
            if (!studioActiveBlock || !currentTaskId) {
                alert('Selecciona una frase primero.');
                return;
            }

            const sourceLang = selectStudioSourceLang ? selectStudioSourceLang.value : 'English';
            const targetLang = selectStudioTargetLang ? selectStudioTargetLang.value : 'Spanish';
            const model = selectStudioModel && selectStudioModel.value ? selectStudioModel.value : (selectModel ? selectModel.value : 'gemma4:e2b-it-qat');
            const phraseIdx = studioActiveBlock.phrase_index;

            btnStudioTranslate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Traduciendo...';
            btnStudioTranslate.disabled = true;

            fetch(`/api/studio/${currentTaskId}/translate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phrase_index: phraseIdx,
                    source_language: sourceLang,
                    target_language: targetLang,
                    model: model,
                    whisper_model: selectStudioWhisperModel ? selectStudioWhisperModel.value : 'large-v3-turbo'
                })
            })
            .then(res => {
                if (!res.ok) return res.json().then(e => { const msg = Array.isArray(e.detail) ? e.detail.map(d => d.msg).join('; ') : (e.detail || 'Error del servidor'); throw new Error(msg); });
                return res.json();
            })
            .then(data => {
                btnStudioTranslate.innerHTML = `<i class="fa-solid fa-check"></i> ¡Traducido!`;
                // Update textarea with translated text
                if (studioTextarea) studioTextarea.value = data.translated_text;
                studioActiveBlock.text = data.translated_text;
                // Reload studio data to update timeline
                loadStudioData();
                setTimeout(() => {
                    btnStudioTranslate.innerHTML = '<i class="fa-solid fa-language"></i> Traducir con IA';
                    btnStudioTranslate.disabled = false;
                }, 3000);
            })
            .catch(err => {
                console.error('[Studio] Translate error:', err);
                alert('Error traduciendo: ' + err.message);
                btnStudioTranslate.innerHTML = '<i class="fa-solid fa-language"></i> Traducir con IA';
                btnStudioTranslate.disabled = false;
            });
        });
    }

});
