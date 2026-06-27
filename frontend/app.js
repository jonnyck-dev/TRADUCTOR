document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const youtubeUrlInput = document.getElementById('youtube-url');
    const btnProcess = document.getElementById('btn-process');
    const btnStopTask = document.getElementById('btn-stop-task');
    const btnNew = document.getElementById('btn-new');
    const startOverlay = document.getElementById('start-overlay');
    const processingOverlay = document.getElementById('processing-overlay');
    const videoPlayer = document.getElementById('video-player');
    
    const selectModel = document.getElementById('select-model');
    const selectSpeaker = document.getElementById('select-speaker');
    const selectVibevoiceModel = document.getElementById('select-vibevoice-model');
    const inputVibevoiceCfg = document.getElementById('input-vibevoice-cfg');
    const inputVibevoiceSteps = document.getElementById('input-vibevoice-steps');
    const valVibevoiceCfg = document.getElementById('val-vibevoice-cfg');
    const valVibevoiceSteps = document.getElementById('val-vibevoice-steps');
    const inputBatchSize = document.getElementById('input-batch-size');
    const valBatchSize = document.getElementById('val-batch-size');
    const inputSyncSize = document.getElementById('input-sync-size');
    const valSyncSize = document.getElementById('val-sync-size');
    const selectTtsMode = document.getElementById('select-tts-mode');
    const batchSizeGroup = document.getElementById('batch-size-group');
    const syncSizeGroup = document.getElementById('sync-size-group');

    // Update range slider labels on input
    inputVibevoiceCfg.addEventListener('input', () => {
        valVibevoiceCfg.textContent = inputVibevoiceCfg.value;
    });
    inputVibevoiceSteps.addEventListener('input', () => {
        valVibevoiceSteps.textContent = inputVibevoiceSteps.value;
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

    // Toggle English/Spanish displays
    btnShowOriginal.addEventListener('click', () => {
        btnShowOriginal.classList.toggle('active');
        const lines = document.querySelectorAll('.subtitle-line');
        lines.forEach(line => {
            line.classList.toggle('hide-eng', !btnShowOriginal.classList.contains('active'));
        });
    });

    btnShowTranslated.addEventListener('click', () => {
        btnShowTranslated.classList.toggle('active');
        const lines = document.querySelectorAll('.subtitle-line');
        lines.forEach(line => {
            line.classList.toggle('hide-esp', !btnShowTranslated.classList.contains('active'));
        });
    });

    // Fetch caches
    function loadAvailableCaches() {
        fetch('/api/caches')
        .then(res => res.json())
        .then(data => {
            selectCache.innerHTML = '';
            if (data.length === 0) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = '(Ninguna caché disponible)';
                selectCache.appendChild(opt);
                return;
            }
            data.forEach(cacheId => {
                const opt = document.createElement('option');
                opt.value = cacheId;
                opt.textContent = cacheId;
                selectCache.appendChild(opt);
            });
        })
        .catch(err => {
            console.error('Error fetching caches:', err);
            selectCache.innerHTML = '<option value="">Error al cargar cachés</option>';
        });
    }

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
                return;
            }
            
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
    });

    // Initial calls
    loadOllamaModels();

    // Start processing YouTube video
    btnProcess.addEventListener('click', () => {
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
            vibevoice_model: selectVibevoiceModel.value,
            vibevoice_cfg: parseFloat(inputVibevoiceCfg.value),
            vibevoice_steps: parseInt(inputVibevoiceSteps.value),
            tts_mode: selectTtsMode.value,
            batch_size: parseInt(inputBatchSize.value),
            sync_size: parseInt(inputSyncSize.value)
        };

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
                    loadVideo(data.result);
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    showError(data.error || 'Ocurrió un error desconocido.');
                } else if (data.status === 'stopped') {
                    clearInterval(pollInterval);
                    showStopped(data.error || 'Doblaje detenido por el usuario.');
                }
            })
            .catch(err => {
                clearInterval(pollInterval);
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
                processDesc.textContent = 'Ejecutando WhisperX en inglés...';
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
                    ? 'Generando audio doblado al español con TTS Nativo de Windows...' 
                    : 'Generando audio doblado al español con el modelo de síntesis (TTS)...';
                statusText = 'Generando TTS...';
                statusDotColor = '#d946ef';
                break;
            case 'transcribing_dub':
                processTitle.textContent = 'Alineando Doblaje';
                processDesc.textContent = 'Transcribiendo audio en español para obtener tiempos...';
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
                    eng: orig.text,
                    esp: trans.text
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
        
        // Auto play
        revealStudioButton();
        videoPlayer.play();
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
            if (!btnShowOriginal.classList.contains('active')) line.classList.add('hide-eng');
            if (!btnShowTranslated.classList.contains('active')) line.classList.add('hide-esp');
            
            line.innerHTML = `
                <div class="timestamp">${formatTime(sub.start)}</div>
                <div class="text-pair">
                    <div class="text-eng">${sub.eng}</div>
                    <div class="text-esp">${sub.esp}</div>
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
    const btnOpenStudio = document.getElementById('btn-open-studio');
    const btnCloseStudio = document.getElementById('btn-close-studio');
    const homeView = document.getElementById('home-view');
    const studioView = document.getElementById('studio-view');
    const studioVideoWrapper = document.getElementById('studio-video-wrapper');
    const playerWrapper = document.querySelector('.player-wrapper');
    
    // Timeline elements
    const trackEnglish = document.getElementById('track-english');
    const trackDubbed = document.getElementById('track-dubbed');
    const timelineRuler = document.getElementById('timeline-ruler');
    const trackVideo = document.getElementById('track-video');
    const videoBlock = trackVideo.querySelector('.video-block');
    
    // Inspector elements
    const inspectorBlockName = document.getElementById('inspector-block-name');
    const inspectorContent = document.getElementById('inspector-content');
    const studioTextarea = document.getElementById('studio-textarea');
    const btnStudioPlayOrig = document.getElementById('btn-studio-play-orig');
    const btnStudioPlayDub = document.getElementById('btn-studio-play-dub');
    const btnStudioRegenerate = document.getElementById('btn-studio-regenerate');
    const studioAudioPlayer = document.getElementById('studio-audio-player');
    const btnStudioFinalize = document.getElementById('btn-studio-finalize');

    let studioActiveBlock = null;
    let studioData = null;
    const PIXELS_PER_SECOND = 40;

    // Show Studio Button when task finishes
    function revealStudioButton() {
        if (currentTaskId) {
            btnOpenStudio.classList.remove('hidden');
        }
    }

    btnOpenStudio.addEventListener('click', () => {
        if (!currentTaskId) return;
        
        // Hide Home, Show Studio
        homeView.classList.remove('view-active');
        homeView.classList.add('hidden');
        studioView.classList.remove('hidden');
        studioView.classList.add('view-active');
        
        // Move video player to Studio
        studioVideoWrapper.appendChild(videoPlayer);
        videoPlayer.classList.remove('hidden');
        
        // Load data
        loadStudioData();
    });

    btnCloseStudio.addEventListener('click', () => {
        // Move video player back
        playerWrapper.appendChild(videoPlayer);
        
        // Hide Studio, Show Home
        studioView.classList.remove('view-active');
        studioView.classList.add('hidden');
        homeView.classList.remove('hidden');
        homeView.classList.add('view-active');
    });

    function loadStudioData() {
        const batchSize = parseInt(inputBatchSize.value) || 5;
        fetch(`/api/studio/${currentTaskId}/data?batch_size=${batchSize}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    studioData = data.batches;
                    renderTimeline();
                } else {
                    alert("Error loading studio data.");
                }
            })
            .catch(err => console.error("Studio error:", err));
    }

    function renderTimeline() {
        trackEnglish.innerHTML = '';
        trackDubbed.innerHTML = '';
        timelineRuler.innerHTML = '';
        
        if (!studioData || studioData.length === 0) return;
        
        let totalDuration = videoPlayer.duration || studioData[studioData.length - 1].end_time;
        if (isNaN(totalDuration) || totalDuration <= 0) totalDuration = 100; // fallback
        
        const totalWidth = totalDuration * PIXELS_PER_SECOND;
        
        // Set track widths
        trackEnglish.style.width = `${totalWidth}px`;
        trackDubbed.style.width = `${totalWidth}px`;
        timelineRuler.style.width = `${totalWidth}px`;
        videoBlock.style.width = `${totalWidth}px`;
        videoBlock.innerHTML = `<span style="position:relative; z-index:1; font-weight:bold;">Video Original (${formatTime(totalDuration)})</span>`;
        
        // Build Ruler Marks
        for (let s = 0; s <= totalDuration; s += 10) {
            const mark = document.createElement('div');
            mark.style.position = 'absolute';
            mark.style.left = `${s * PIXELS_PER_SECOND}px`;
            mark.style.bottom = '0';
            mark.style.borderLeft = '1px solid rgba(255,255,255,0.3)';
            mark.style.height = '10px';
            mark.style.paddingLeft = '5px';
            mark.style.fontSize = '10px';
            mark.style.color = 'rgba(255,255,255,0.5)';
            mark.textContent = formatTime(s);
            timelineRuler.appendChild(mark);
        }
        
        // Render Blocks
        studioData.forEach(batch => {
            const left = batch.start_time * PIXELS_PER_SECOND;
            const width = (batch.end_time - batch.start_time) * PIXELS_PER_SECOND;
            
            // English Block
            const engBlock = document.createElement('div');
            engBlock.className = 'timeline-block english-block';
            engBlock.style.left = `${left}px`;
            engBlock.style.width = `${Math.max(width, 30)}px`;
            engBlock.innerHTML = `<div class="waveform-bg"></div><span style="position:relative; z-index:1;">${batch.text}</span>`;
            trackEnglish.appendChild(engBlock);
            
            // Dubbed Block (Interactive)
            const dubBlock = document.createElement('div');
            dubBlock.className = 'timeline-block dubbed-block';
            dubBlock.style.left = `${left}px`;
            dubBlock.style.width = `${Math.max(width, 30)}px`;
            dubBlock.innerHTML = `<div class="waveform-bg"></div><span style="position:relative; z-index:1;">${batch.text}</span>`;
            
            dubBlock.addEventListener('click', () => {
                document.querySelectorAll('.dubbed-block').forEach(b => b.classList.remove('selected'));
                dubBlock.classList.add('selected');
                
                selectStudioBlock(batch);
                videoPlayer.currentTime = batch.start_time;
            });
            
            trackDubbed.appendChild(dubBlock);
        });
    }

    function selectStudioBlock(batch) {
        studioActiveBlock = batch;
        inspectorBlockName.innerHTML = `<i class="fa-solid fa-cube text-teal"></i> Bloque #${batch.batch_index} [${formatTime(batch.start_time)} - ${formatTime(batch.end_time)}]`;
        studioTextarea.value = batch.text;
        inspectorContent.classList.remove('hidden');
    }

    btnStudioPlayOrig.addEventListener('click', () => {
        if (!studioActiveBlock) return;
        studioAudioPlayer.src = `/api/studio/${currentTaskId}/audio/original?start=${studioActiveBlock.start_time}&end=${studioActiveBlock.end_time}`;
        studioAudioPlayer.play();
    });

    btnStudioPlayDub.addEventListener('click', () => {
        if (!studioActiveBlock) return;
        // Anti-cache string
        studioAudioPlayer.src = `/api/studio/${currentTaskId}/audio/dubbed/${studioActiveBlock.batch_index}?t=${new Date().getTime()}`;
        studioAudioPlayer.play();
    });

    btnStudioRegenerate.addEventListener('click', () => {
        if (!studioActiveBlock) return;
        
        btnStudioRegenerate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Regenerando (Toma ~5s)...';
        btnStudioRegenerate.disabled = true;
        
        const payload = {
            batch_index: studioActiveBlock.batch_index,
            text: studioTextarea.value,
            speaker: selectSpeaker.value,
            vibevoice_model: selectVibevoiceModel.value,
            vibevoice_cfg: parseFloat(inputVibevoiceCfg.value),
            vibevoice_steps: parseInt(inputVibevoiceSteps.value)
        };
        
        fetch(`/api/studio/${currentTaskId}/reprocess?batch_size=${parseInt(inputBatchSize.value)||5}`, {
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

    btnStudioFinalize.addEventListener('click', () => {
        if (!currentTaskId) return;
        if (confirm("Se preparará el ensamblaje final. Deberás presionar 'Volver' y luego darle a Simular con Caché Local para que arme el video. ¿Continuar?")) {
            fetch(`/api/studio/${currentTaskId}/finalize`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                btnCloseStudio.click(); // Autoclose the studio to reveal the play button
            })
            .catch(err => alert('Error finalizing: ' + err));
        }
    });

});
