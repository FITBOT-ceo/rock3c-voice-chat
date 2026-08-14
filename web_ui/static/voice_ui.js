const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const playLastBtn = document.getElementById('playLastBtn');
const logList = document.getElementById('logList');
const statusBox = document.getElementById('statusBox');
const audioInfo = document.getElementById('audioInfo');
const inputDeviceSelect = document.getElementById('inputDeviceSelect');
const trackInfo = document.getElementById('trackInfo');
const runtimeMode = document.getElementById('runtimeMode');
const runtimeSummary = document.getElementById('runtimeSummary');
const runtimeChecks = document.getElementById('runtimeChecks');
const runtimeError = document.getElementById('runtimeError');
const guideTitle = document.getElementById('guideTitle');
const guideBody = document.getElementById('guideBody');

const STATUS_GUIDE = {
    checking: {
        label: '확인 중...',
        tone: 'warn',
        title: '초기 점검 중',
        body: '실행 경로와 필수 구성요소를 확인하고 있습니다.',
    },
    idle: {
        label: '대기 중',
        tone: 'ready',
        title: '녹음 대기 상태',
        body: '녹음 시작을 누른 뒤 말하고, 끝나면 중지 후 전송을 누르세요.',
    },
    recording: {
        label: '녹음 중...',
        tone: 'busy',
        title: '사용자 음성 수집 중',
        body: '마이크 가까이에서 또렷하게 말한 뒤 중지 후 전송을 눌러 주세요.',
    },
    processing: {
        label: '음성 처리 중...',
        tone: 'busy',
        title: 'STT/LLM/TTS 처리 중',
        body: '음성 인식과 응답 생성을 진행하고 있습니다. 완료될 때까지 잠시 기다려 주세요.',
    },
    playing: {
        label: '최근 녹음 재생 중...',
        tone: 'busy',
        title: '최근 녹음 확인 중',
        body: '마이크 입력이 실제로 들어왔는지 스피커 재생으로 점검하고 있습니다.',
    },
    runtimeBlocked: {
        label: '런타임 점검 필요',
        tone: 'warn',
        title: '실행 경로 점검 필요',
        body: '오류 사유를 먼저 확인한 뒤 다시 시도해 주세요. 로컬 실험 경로가 실패하면 Groq 기본 운영 경로로 복귀해 검증합니다.',
    },
    error: {
        label: '오류 발생',
        tone: 'error',
        title: '재시도 전 확인 필요',
        body: '오류 내용을 확인한 뒤 최근 녹음 재생으로 입력 상태를 점검하거나 실행 경로를 기본 운영 경로로 되돌려 주세요.',
    },
};

let recorder = null;
let mediaStream = null;
let chunks = [];
let currentTrackSettings = null;
let runtimeReady = false;

function setStatus(text) {
    statusBox.textContent = text;
}

function setStatusState(stateKey, detail) {
    const guide = STATUS_GUIDE[stateKey] || STATUS_GUIDE.idle;
    statusBox.textContent = guide.label;
    statusBox.className = `status-box status-${guide.tone}`;
    guideTitle.textContent = guide.title;
    guideBody.textContent = detail || guide.body;
}

function setRecordingEnabled(enabled) {
    runtimeReady = enabled;
    startBtn.disabled = !enabled;
    if (!enabled) {
        stopBtn.disabled = true;
    }
}

function updateAudioInfo(info) {
    if (!info) {
        audioInfo.textContent = '최근 녹음 정보 없음';
        return;
    }
    const duration = info.duration ? `${info.duration.toFixed(2)}초` : '0초';
    const size = info.size ? `${Math.round(info.size / 1024)}KB` : '0KB';
    const rate = info.sample_rate ? `${info.sample_rate}Hz` : 'unknown';
    const channels = info.channels ? `${info.channels}ch` : 'unknown';
    audioInfo.textContent = `최근 WAV: ${duration}, ${size}, ${rate}, ${channels}`;
}

function updateTrackInfo(settings) {
    if (!settings) {
        trackInfo.textContent = '브라우저 입력 장치 정보 없음';
        return;
    }
    const rate = settings.sampleRate ? `${settings.sampleRate}Hz` : 'unknown';
    const channels = settings.channelCount ? `${settings.channelCount}ch` : 'unknown';
    const id = settings.deviceId || 'default';
    trackInfo.textContent = `현재 브라우저 입력: ${id} / ${rate} / ${channels}`;
}

function renderRuntime(runtime) {
    const details = runtime?.details || {};
    const checks = details.checks || [];
    runtimeMode.textContent = runtime?.ready ? `${details.mode} 사용 가능` : `${details.mode} 점검 필요`;
    runtimeSummary.textContent = details.summary || '런타임 요약 정보 없음';
    runtimeChecks.textContent = checks.length ? `필수 구성요소: ${checks.join(' / ')}` : '필수 구성요소 정보 없음';

    if (runtime?.ready) {
        runtimeError.hidden = true;
        runtimeError.textContent = '';
        setRecordingEnabled(true);
        if (statusBox.textContent === '확인 중...' || statusBox.textContent === '런타임 점검 필요') {
            setStatusState('idle');
        }
        return;
    }

    runtimeError.hidden = false;
    runtimeError.textContent = runtime?.error || '런타임 점검 실패';
    setRecordingEnabled(false);
    setStatusState('runtimeBlocked');
}

async function loadInputDevices() {
    try {
        const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const devices = await navigator.mediaDevices.enumerateDevices();
        const currentTrack = tempStream.getAudioTracks()[0];
        currentTrackSettings = currentTrack.getSettings();
        updateTrackInfo(currentTrackSettings);

        const inputs = devices.filter((device) => device.kind === 'audioinput');
        inputDeviceSelect.innerHTML = '';
        inputs.forEach((device, index) => {
            const option = document.createElement('option');
            option.value = device.deviceId;
            option.textContent = device.label || `마이크 ${index + 1}`;
            if (currentTrackSettings.deviceId && device.deviceId === currentTrackSettings.deviceId) {
                option.selected = true;
            }
            inputDeviceSelect.appendChild(option);
        });

        tempStream.getTracks().forEach((track) => track.stop());
    } catch (error) {
        trackInfo.textContent = `마이크 장치 조회 실패: ${error.message}`;
    }
}

function renderMessages(messages) {
    logList.innerHTML = '';
    messages.forEach((msg) => {
        const item = document.createElement('div');
        item.className = `msg msg-${msg.role}`;

        const role = document.createElement('span');
        role.className = 'msg-role';
        role.textContent = msg.role === 'assistant' ? 'AI' : msg.role === 'user' ? '나' : '시스템';

        const text = document.createElement('div');
        text.textContent = msg.text;

        item.appendChild(role);
        item.appendChild(text);
        logList.appendChild(item);
    });
    logList.scrollTop = logList.scrollHeight;
}

async function loadHistory() {
    const response = await fetch('/api/history');
    const data = await response.json();
    if (data.ok) {
        renderMessages(data.messages);
    }
    await loadRuntime();
    await loadLastAudioInfo();
}

async function loadRuntime() {
    const response = await fetch('/api/runtime');
    const data = await response.json();
    if (data.ok) {
        renderRuntime(data.runtime);
    }
}

async function loadLastAudioInfo() {
    try {
        const response = await fetch('/api/debug/last-audio');
        const data = await response.json();
        if (response.ok && data.ok) {
            updateAudioInfo(data.wav);
        } else {
            updateAudioInfo(null);
        }
    } catch {
        updateAudioInfo(null);
    }
}

async function startRecording() {
    if (!runtimeReady) {
        setStatusState('runtimeBlocked');
        alert('런타임 점검이 끝나지 않았습니다. 실행 경로와 오류 메시지를 먼저 확인해 주세요.');
        return;
    }
    const selectedDeviceId = inputDeviceSelect.value;
    const audioConstraints = {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
    };
    if (selectedDeviceId) {
        audioConstraints.deviceId = { exact: selectedDeviceId };
    }
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
    currentTrackSettings = mediaStream.getAudioTracks()[0].getSettings();
    updateTrackInfo(currentTrackSettings);
    recorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });
    chunks = [];

    recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            chunks.push(event.data);
        }
    };

    recorder.start();
    startBtn.disabled = true;
    stopBtn.disabled = false;
    setStatusState('recording');
}

async function stopRecording() {
    if (!recorder) {
        return;
    }

    const stopped = new Promise((resolve) => {
        recorder.onstop = resolve;
    });

    recorder.stop();
    stopBtn.disabled = true;
    setStatusState('processing');
    await stopped;

    mediaStream.getTracks().forEach((track) => track.stop());

    const blob = new Blob(chunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            if (data.runtime) {
                renderRuntime(data.runtime);
            }
            if (data.audio_info) {
                updateAudioInfo(data.audio_info);
            }
            throw new Error(data.error || '처리에 실패했습니다.');
        }
        renderMessages(data.messages);
        if (data.runtime) {
            renderRuntime(data.runtime);
        }
        updateAudioInfo(data.audio_info);
        setStatusState('idle');
    } catch (error) {
        setStatusState('error', error.message);
        alert(error.message);
    } finally {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        recorder = null;
        mediaStream = null;
    }
}

async function playLastRecording() {
    setStatusState('playing');
    try {
        const response = await fetch('/api/debug/play-last', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || '재생 실패');
        }
        setStatusState('idle');
    } catch (error) {
        setStatusState('error', error.message);
        alert(error.message);
    }
}

startBtn.addEventListener('click', startRecording);
stopBtn.addEventListener('click', stopRecording);
playLastBtn.addEventListener('click', playLastRecording);
setStatusState('checking');
loadHistory();
loadInputDevices();
