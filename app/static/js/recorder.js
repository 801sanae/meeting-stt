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
const meetingListEl = document.getElementById('meetingList');
const sttViewEl = document.getElementById('sttView');
const summaryViewEl = document.getElementById('summaryView');
const tabSttEl = document.getElementById('tabStt');
const tabSummaryEl = document.getElementById('tabSummary');

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

// 탭 전환: STT / SUMMARY
function activateTab(tab) {
  const isStt = tab === 'stt';
  if (!tabSttEl || !tabSummaryEl || !sttViewEl || !summaryViewEl) return;

  if (isStt) {
    tabSttEl.classList.add('bg-slate-900', 'font-semibold');
    tabSummaryEl.classList.remove('bg-slate-900', 'font-semibold');
    sttViewEl.classList.remove('hidden');
    summaryViewEl.classList.add('hidden');
  } else {
    tabSummaryEl.classList.add('bg-slate-900', 'font-semibold');
    tabSttEl.classList.remove('bg-slate-900', 'font-semibold');
    summaryViewEl.classList.remove('hidden');
    sttViewEl.classList.add('hidden');
  }
}

tabSttEl?.addEventListener('click', () => activateTab('stt'));
tabSummaryEl?.addEventListener('click', () => activateTab('summary'));

// 회의 리스트 렌더링
function renderMeetingList(items) {
  if (!meetingListEl) return;
  meetingListEl.innerHTML = '';

  if (!items || items.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'text-slate-300 text-xs';
    empty.textContent = '아직 저장된 회의가 없습니다.';
    meetingListEl.appendChild(empty);
    return;
  }

  items.forEach((m) => {
    const row = document.createElement('div');
    row.className =
      'group flex items-center px-3 py-2 rounded-lg bg-sky-800 hover:bg-sky-700 text-slate-50 text-xs cursor-pointer';

    const created = new Date(m.created_at);
    const label = created.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    const labelSpan = document.createElement('span');
    labelSpan.className = 'flex-1';
    labelSpan.textContent = label;

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className =
      'ml-2 w-4 h-4 flex items-center justify-center text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity';
    deleteBtn.textContent = '✕';

    row.addEventListener('click', () => {
      loadMeetingDetail(m.id);
    });

    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteMeeting(m.id);
    });

    row.appendChild(labelSpan);
    row.appendChild(deleteBtn);
    meetingListEl.appendChild(row);
  });
}

async function fetchMeetingList() {
  try {
    const resp = await fetch('/meetings');
    if (!resp.ok) {
      console.error('[Meeting-STT] 회의 리스트 조회 실패', resp.status);
      return;
    }
    const data = await resp.json();
    renderMeetingList(data);
  } catch (err) {
    console.error('[Meeting-STT] 회의 리스트 조회 에러', err);
  }
}

async function loadMeetingDetail(id) {
  try {
    const resp = await fetch(`/meetings/${id}`);
    if (!resp.ok) {
      console.error('[Meeting-STT] 회의 상세 조회 실패', resp.status);
      return;
    }
    const data = await resp.json();
    console.log('[Meeting-STT] 회의 상세 transcript:', data.full_transcript);
    console.log('[Meeting-STT] 회의 상세 summary:', data.summary);
    currentMeetingId = id;
    sttViewEl.textContent = data.full_transcript || '';
    summaryViewEl.textContent = data.summary || '';
  } catch (err) {
    console.error('[Meeting-STT] 회의 상세 조회 에러', err);
  }
}

async function deleteMeeting(id) {
  if (!confirm('이 회의 기록을 삭제하시겠습니까?')) return;

  try {
    const resp = await fetch(`/meetings/${id}`, { method: 'DELETE' });
    if (!resp.ok && resp.status !== 404) {
      console.error('[Meeting-STT] 회의 삭제 실패', resp.status);
      return;
    }

    // 현재 보고 있던 회의를 삭제했다면 오른쪽 뷰 초기화
    if (currentMeetingId === id) {
      currentMeetingId = null;
      sttViewEl.textContent = '';
      summaryViewEl.textContent = '';
    }

    fetchMeetingList();
  } catch (err) {
    console.error('[Meeting-STT] 회의 삭제 에러', err);
  }
}

// 초기 진입 시 회의 리스트 불러오기
fetchMeetingList();
activateTab('stt');

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

    // 최신 회의 상세 조회로 오른쪽 뷰 업데이트
    sttViewEl.textContent = data.transcript || '';
    summaryViewEl.textContent = data.summary || '';

    // 리스트 갱신 (새로 저장된 회의 포함)
    fetchMeetingList();
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
