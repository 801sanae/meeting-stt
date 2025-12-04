let mediaRecorder; // 더 이상 사용하지 않지만, 기존 코드와의 호환을 위해 선언 유지
let chunks = [];
let startTime = null;
let currentStream = null; // 현재 녹음에 사용 중인 MediaStream
let currentMeetingId = null; // 현재 상세 뷰에 표시 중인 회의 ID

// Web Audio API 를 사용해 WAV(PCM) 데이터를 수집하기 위한 상태
let audioContext = null;
let audioSource = null;
let audioProcessor = null;
let audioChunks = [];
let audioSampleRate = 44100;

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusEl = document.getElementById('status');

console.log('[Meeting-STT] 페이지 로드 완료');

// 브라우저 기능 체크
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
  console.warn('[Meeting-STT] 이 브라우저는 getUserMedia를 지원하지 않습니다.');
  statusEl.textContent = '이 브라우저는 오디오 녹음을 지원하지 않습니다.';
  if (startBtn) startBtn.disabled = true;
  if (stopBtn) stopBtn.disabled = true;
} else if (typeof MediaRecorder === 'undefined') {
  statusEl.textContent = '이 브라우저에서는 MediaRecorder가 지원되지 않습니다. Chrome/Edge를 사용해 주세요.';
  startBtn.disabled = true;
  stopBtn.disabled = true;
} else {
  statusEl.textContent = '녹음 준비 완료. "녹음 시작" 버튼을 눌러 주세요.';
}

// (회의 리스트, 탭, 쿼터 관련 로직은 meetings_ui.js 로 이전)

function writeWavString(view, offset, string) {
  for (let i = 0; i < string.length; i += 1) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

function floatTo16BitPCM(view, offset, input) {
  for (let i = 0; i < input.length; i += 1, offset += 2) {
    let s = input[i];
    if (s < -1) s = -1;
    if (s > 1) s = 1;
    s *= s < 0 ? 0x8000 : 0x7fff;
    view.setInt16(offset, s, true);
  }
}

function encodeWAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  writeWavString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeWavString(view, 8, 'WAVE');
  writeWavString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (1 = PCM)
  view.setUint16(22, 1, true); // NumChannels (mono)
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, sampleRate * 2, true); // ByteRate (SampleRate * NumChannels * BytesPerSample)
  view.setUint16(32, 2, true); // BlockAlign (NumChannels * BytesPerSample)
  view.setUint16(34, 16, true); // BitsPerSample
  writeWavString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true); // Subchunk2Size

  floatTo16BitPCM(view, 44, samples);

  return new Blob([view], { type: 'audio/wav' });
}

async function stopRecordingAndUpload() {
  console.log('[Meeting-STT] 녹음 stop 이벤트, WAV 생성');

  const durationSeconds = (Date.now() - startTime) / 1000.0;

  let length = 0;
  for (const chunk of audioChunks) {
    length += chunk.length;
  }

  const samples = new Float32Array(length);
  let offset = 0;
  for (const chunk of audioChunks) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }

  const wavBlob = encodeWAV(samples, audioSampleRate);

  console.log('[Meeting-STT] blob size(bytes)=', wavBlob.size, 'durationSeconds=', durationSeconds);

  statusEl.textContent = '서버로 업로드 중...';

  const formData = new FormData();
  formData.append('audio', wavBlob, 'recording.wav');
  formData.append('duration_seconds', String(durationSeconds));

  try {
    const resp = await fetch('/meetings/record', {
      method: 'POST',
      body: formData,
    });

    if (!resp.ok) {
      const text = await resp.text();
      console.error('[Meeting-STT] /meetings/record 에러', resp.status, text);
      statusEl.textContent = '에러: ' + resp.status + ' ' + text;
      return;
    }

    const data = await resp.json();
    statusEl.textContent = '완료';

    console.log('[Meeting-STT] 서버 인식 결과 transcript:', data.transcript);
    console.log('[Meeting-STT] 서버 요약 결과 summary:', data.summary);

    // 화면 갱신은 meetings_ui.js 의 전역 헬퍼에 위임
    if (window.meetingUI?.updateAfterRecord) {
      window.meetingUI.updateAfterRecord(data);
    }
  } catch (err) {
    console.error('[Meeting-STT] 요청 중 오류', err);
    statusEl.textContent = '요청 중 오류 발생';
  } finally {
    // 마이크/오디오 리소스 정리
    if (currentStream) {
      currentStream.getTracks().forEach((track) => track.stop());
      currentStream = null;
    }

    if (audioProcessor) {
      audioProcessor.disconnect();
      audioProcessor = null;
    }

    if (audioSource) {
      audioSource.disconnect();
      audioSource = null;
    }

    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }
  }
}

startBtn.onclick = async () => {
  console.log('[Meeting-STT] 녹음 시작 클릭');

  if (startBtn.disabled) {
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    currentStream = stream;
    audioChunks = [];

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioCtx();
    audioSampleRate = audioContext.sampleRate;
    audioSource = audioContext.createMediaStreamSource(stream);
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);

    audioProcessor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      audioChunks.push(new Float32Array(input));
    };

    audioSource.connect(audioProcessor);
    audioProcessor.connect(audioContext.destination);

    startTime = Date.now();
    statusEl.textContent = '녹음 중...';
    startBtn.disabled = true;
    stopBtn.disabled = false;
  } catch (err) {
    console.error('[Meeting-STT] 녹음 시작 실패', err);
    statusEl.textContent = '마이크 권한을 확인해 주세요.';
  }
};

stopBtn.onclick = () => {
  console.log('[Meeting-STT] 완료 클릭');
  if (!startTime) {
    return;
  }

  startBtn.disabled = false;
  stopBtn.disabled = true;
  statusEl.textContent = '녹음 종료';

  // Web Audio 기반 녹음 종료 및 업로드
  void stopRecordingAndUpload();
};
