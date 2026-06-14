document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const youtubeUrlInput = document.getElementById('youtube-url');
    const btnProcess = document.getElementById('btn-process');
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
            startPolling(taskId);
        })
        .catch(err => {
            showError(err.message);
        });
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
                processDesc.textContent = 'Ejecutando insanely-fast-whisper en inglés...';
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
                processDesc.textContent = 'Generando audio doblado al español con VibeVoice...';
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
        }

        globalStatus.innerHTML = `<span class="dot" style="background-color: ${statusDotColor}; box-shadow: 0 0 8px ${statusDotColor};"></span> ${statusText}`;
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
        
        // Auto play
        videoPlayer.play();
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
