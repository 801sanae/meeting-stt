# Azure Speech 사용 모드 개요

이 문서는 이 프로젝트에서 사용할 수 있는 Azure Speech Service 연동 방식들을 정리합니다.

- REST v1 (현재 프로젝트에서 사용 중)
- Speech SDK (실시간/대화형, 화자 분리 등 확장 가능)
- V3 Batch Transcription (비동기 대용량 처리)

각 섹션마다 간단한 사용 예시와 공식 문서 링크를 함께 정리합니다.

---

## 1. REST v1 Speech-to-Text (현재 사용 중)

### 1.1 개념

- HTTP 기반의 **간단한 STT 엔드포인트**.
- 이 프로젝트에서는 다음 URL 패턴을 사용:
  - `https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1`
- 요청 바디에 **오디오(현재는 audio/wav)** 를 그대로 넣고, 쿼리 파라미터로 `language` 를 지정.
- 응답은 보통 아래와 같이 `DisplayText` 를 포함한 JSON:

```json
{
  "RecognitionStatus": "Success",
  "Offset": 0,
  "Duration": 200000000,
  "DisplayText": "안녕하세요. 테스트 문장입니다."
}
```

> 참고: 이 REST v1 엔드포인트에서는 화자 분리(스피커 다이어라이제이션)를 지원하지 않고,
> 단일 텍스트(`DisplayText`) 위주로 사용하는 것이 일반적입니다.

### 1.2 이 프로젝트에서의 사용 예시

- 구현 위치: `app/service/stt_service.py` → `transcribe_with_azure_speech`
- 핵심 흐름(발췌):

```python
url = (
    f"https://{region}.stt.speech.microsoft.com/"
    "speech/recognition/conversation/cognitiveservices/v1"
)

headers = {
    "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
    "Content-Type": "audio/wav",  # Web Audio API 로 만든 16bit mono WAV
    "Accept": "application/json",
}

params = {"language": settings.azure_speech_language}

async with httpx.AsyncClient(timeout=30.0) as client:
    resp = await client.post(url, params=params, headers=headers, content=audio_bytes)

# resp.json() 에서 DisplayText / NBest[0].Display 등을 추출
```

### 1.3 공식 문서 링크

- REST STT 개요:  
  https://learn.microsoft.com/azure/ai-services/speech-service/rest-speech-to-text

---

## 2. Speech SDK (실시간/대화형, 화자 분리 등)

### 2.1 개념

- Azure Speech SDK(Python / JavaScript / C# 등)를 사용하면,
  - **실시간 스트리밍 인식**,
  - **Conversation Transcription**,
  - 일부 언어/시나리오에서 **화자 분리(Speaker Diarization)**
  같은 기능을 사용할 수 있습니다.
- 방식:
  - 애플리케이션에서 마이크/파일 스트림을 SDK에 넘김
  - SDK가 WebSocket 등을 통해 Azure와 통신하며 이벤트 기반으로 결과 전달

### 2.2 예시 (Python, 개략적인 pseudo 코드)

> 아래 코드는 전체 동작을 그대로 복사해서 쓰기보다는,
> **라이브러리/클래스 느낌을 이해하기 위한 참고용**입니다.

```python
import azure.cognitiveservices.speech as speechsdk

speech_config = speechsdk.SpeechConfig(
    subscription="<SPEECH_KEY>",
    region="<SPEECH_REGION>",
)
# 언어 설정
speech_config.speech_recognition_language = "ko-KR"

# 마이크 입력 사용 예시
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

speech_recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config,
    audio_config=audio_config,
)

print("Say something...")
result = speech_recognizer.recognize_once()

if result.reason == speechsdk.ResultReason.RecognizedSpeech:
    print("Recognized: {}".format(result.text))
else:
    print("No speech could be recognized")
```

### 2.3 화자 분리(Conversation Transcriber) 방향성

- 화자 분리가 필요한 경우에는 **Conversation Transcription / ConversationTranscriber** 를 사용.
- 개략적인 사용 흐름:
  - `Conversation` 객체를 만들고 참가자를 추가
  - `ConversationTranscriber` 에 `Conversation` 을 연결
  - 인식 이벤트 콜백에서 `speaker_id` / `text` 를 함께 수신
- 실제 구현 시에는 SDK 예제를 기반으로 설계가 필요하며,
  이 프로젝트에서는 아직 사용하지 않고 있습니다.

### 2.4 공식 문서 링크

- Speech SDK 개요:  
  https://learn.microsoft.com/azure/ai-services/speech-service/speech-sdk
- Conversation Transcription 및 diarization 관련:  
  https://learn.microsoft.com/azure/ai-services/speech-service/conversation-transcription

---

## 3. V3 Batch Transcription (비동기 대용량 처리)

### 3.1 개념

- 긴 오디오 파일(예: 수십 분~수 시간)이나 **여러 개의 파일을 한 번에 처리**하고 싶을 때 사용하는 모드.
- 특징:
  - REST API로 **작업(Job)** 을 생성
  - Azure가 백그라운드에서 오디오를 처리
  - 완료되면 결과를 Blob Storage 등에 저장하거나, API로 상태/결과를 조회
  - 일부 설정에서 화자 분리 옵션을 줄 수 있음 (언어/지역 별 지원 여부는 공식 문서 참고)
- 단점:
  - 지금 이 프로젝트처럼 "녹음 끝 → 곧바로 요약" 하는 UX 와는 맞지 않고,
    폴링/웹훅 기반의 비동기 아키텍처가 필요합니다.

### 3.2 개략적인 호출 흐름 예시

1. **Transcription Job 생성 (HTTP POST)**
   - 입력 오디오 파일은 일반적으로 Azure Blob Storage 에 올려둔 뒤 URL 로 지정.

```http
POST https://{region}.api.cognitive.microsoft.com/speechtotext/v3.1/transcriptions
Ocp-Apim-Subscription-Key: <SPEECH_KEY>
Content-Type: application/json

{
  "contentUrls": [
    "https://<storage-account>.blob.core.windows.net/<container>/<file>.wav"
  ],
  "properties": {
    "diarizationEnabled": true,
    "wordLevelTimestampsEnabled": true,
    "punctuationMode": "DictatedAndAutomatic",
    "profanityFilterMode": "Masked"
  },
  "locale": "ko-KR",
  "displayName": "sample-transcription-job"
}
```

2. **Job 상태 조회 (HTTP GET)**

```http
GET https://{region}.api.cognitive.microsoft.com/speechtotext/v3.1/transcriptions/{transcriptionId}
Ocp-Apim-Subscription-Key: <SPEECH_KEY>
```

- 응답의 `status` 가 `Succeeded` 가 되면, `links` 나 지정된 저장소에서 결과 JSON 을 다운로드.

### 3.3 공식 문서 링크

- Speech-to-text v3.1 REST API:  
  https://learn.microsoft.com/azure/ai-services/speech-service/batch-transcription

---

## 4. 이 프로젝트에서의 활용 방향 메모

- **현재 구현**
  - Web Audio API → 16bit mono WAV (`audio/wav`) 업로드
  - Azure Speech REST v1 로 단일 텍스트 STT 처리
- **향후 확장 아이디어**
  - 화자 분리 / 타임라인이 중요한 회의의 경우:
    - Speech SDK 기반 Conversation Transcriber + diarization 도입 검토
    - 또는 v3 Batch Transcription 을 사용하여 오프라인 분석 파이프라인 구축
  - STT 백엔드 다변화:
    - Azure Speech 실패/제한 시 Whisper API 백엔드로의 폴백 등

위 내용은 설계/토론을 위한 개요 수준이며, 실제 도입 시에는 각 모드별 요금/지원 언어/제한 사항을
Azure 공식 문서에서 다시 확인해야 합니다.
