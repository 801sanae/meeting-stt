// Meetings UI 및 STT/요약 표시, 쿼터 조회 담당
// 녹음(Web Audio, 업로드)은 recorder.js 에서만 처리하고,
// 이 파일은 회의 리스트/상세/삭제, 탭 전환, STT 쿼터 표시를 담당한다.

const meetingListEl = document.getElementById('meetingList');
const sttViewEl = document.getElementById('sttView');
const summaryViewEl = document.getElementById('summaryView');
const tabSttEl = document.getElementById('tabStt');
const tabSummaryEl = document.getElementById('tabSummary');
const quotaBtn = document.getElementById('quotaBtn');
const sttQuotaInfoEl = document.getElementById('sttQuotaInfo');

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
      void loadMeetingDetail(m.id);
    });

    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      void deleteMeeting(m.id);
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
    if (sttViewEl) sttViewEl.textContent = data.full_transcript || '';
    if (summaryViewEl) summaryViewEl.textContent = data.summary || '';
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

    if (sttViewEl) sttViewEl.textContent = '';
    if (summaryViewEl) summaryViewEl.textContent = '';

    void fetchMeetingList();
  } catch (err) {
    console.error('[Meeting-STT] 회의 삭제 에러', err);
  }
}

async function fetchSttUsage() {
  if (!sttQuotaInfoEl) return;

  sttQuotaInfoEl.textContent = 'STT 사용량 조회 중...';

  try {
    const resp = await fetch('/admin/stt/usage');
    if (!resp.ok) {
      const text = await resp.text();
      console.error('[Meeting-STT] STT usage 조회 실패', resp.status, text);
      sttQuotaInfoEl.textContent = 'STT 사용량 조회 실패: ' + resp.status;
      return;
    }

    const data = await resp.json();
    const used = Number(data.used_hours_this_month ?? 0);
    const quota = Number(data.quota_hours_per_month ?? 0);
    const remaining = Number(data.remaining_hours ?? Math.max(quota - used, 0));

    sttQuotaInfoEl.textContent = `이번 달 Azure STT 사용량: ${used.toFixed(2)}h / ${quota.toFixed(2)}h (잔여 ${remaining.toFixed(2)}h)`;
  } catch (err) {
    console.error('[Meeting-STT] STT usage 조회 에러', err);
    sttQuotaInfoEl.textContent = 'STT 사용량 조회 중 오류 발생';
  }
}

quotaBtn?.addEventListener('click', () => {
  void fetchSttUsage();
});

// recorder.js 가 사용할 수 있도록 전역 객체로 노출
window.meetingUI = {
  fetchMeetingList,
  activateTab,
  updateAfterRecord(data) {
    if (sttViewEl) sttViewEl.textContent = data.transcript || '';
    if (summaryViewEl) summaryViewEl.textContent = data.summary || '';
    void fetchMeetingList();
  },
};

// 초기 진입 시 리스트/탭 상태 설정
void fetchMeetingList();
activateTab('stt');
