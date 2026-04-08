const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const playLastBtn = document.getElementById('playLastBtn');
const logList = document.getElementById('logList');
const statusBox = document.getElementById('statusBox');
const audioInfo = document.getElementById('audioInfo');
const inputDeviceSelect = document.getElementById('inputDeviceSelect');
const trackInfo = document.getElementById('trackInfo');

let recorder = null;
let mediaStream = null;
let chunks = [];
let currentTrackSettings = null;

function setStatus(text) {
    statusBox.textContent = text;
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
    await loadLastAudioInfo();
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
    setStatus('녹음 중...');
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
    setStatus('음성 처리 중...');
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
            if (data.audio_info) {
                updateAudioInfo(data.audio_info);
            }
            throw new Error(data.error || '처리에 실패했습니다.');
        }
        renderMessages(data.messages);
        updateAudioInfo(data.audio_info);
        setStatus('대기 중');
    } catch (error) {
        setStatus('오류 발생');
        alert(error.message);
    } finally {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        recorder = null;
        mediaStream = null;
    }
}

async function playLastRecording() {
    setStatus('최근 녹음 재생 중...');
    try {
        const response = await fetch('/api/debug/play-last', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || '재생 실패');
        }
        setStatus('대기 중');
    } catch (error) {
        setStatus('오류 발생');
        alert(error.message);
    }
}

startBtn.addEventListener('click', startRecording);
stopBtn.addEventListener('click', stopRecording);
playLastBtn.addEventListener('click', playLastRecording);
loadHistory();
loadInputDevices();
