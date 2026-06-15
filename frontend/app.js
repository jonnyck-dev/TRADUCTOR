document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const youtubeUrlInput = document.getElementById('youtube-url');
    const btnProcess = document.getElementById('btn-process');
    const btnStopTask = document.getElementById('btn-stop-task');
    const startOverlay = document.getElementById('start-overlay');
    const processingOverlay = document.getElementById('processing-overlay');
    const videoPlayer = document.getElementById('video-player');
    
    const selectModel = document.getElementById('select-model');
    const selectSpeaker = document.getElementById('select-speaker');
    
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
            speaker: selectSpeaker.value
        };

        // Reset view states
        startOverlay.classList.add('hidden');
        processingOverlay.classList.remove('hidden');
        videoPlayer.classList.add('hidden');
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
                    : 'Generando audio doblado al español con VibeVoice...';
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
            "4_tts_synthesis": { name: selectSpeaker.value === 'windows_native' ? "Doblaje (Windows TTS)" : "Doblaje (VibeVoice)", icon: "fa-microphone", color: "#d946ef" },
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
                    // Scroll into view inside viewport
                    activeLine.scrollIntoView({
                        behavior: 'smooth',
                        block: 'nearest'
                    });
                }
            }
            activeSubIndex = activeIndex;
        }
    });
});
