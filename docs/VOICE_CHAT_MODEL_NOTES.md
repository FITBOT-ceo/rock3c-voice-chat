# Voice Chat Model Notes

## 현재 결론

Rock 3C에서 Gemma 4를 로컬로 돌리는 1차 목표는 다음으로 잡는다.

- 모델 계열: Gemma 4
- 목표 모델: `E2B`
- 런타임: `llama.cpp`
- 포맷: GGUF
- 우선 양자화: 4-bit 계열

## 이유

- Rock 3C는 8GB RAM이지만 CPU가 Cortex-A55 4코어라서 추론 속도가 큰 병목이다.
- `E2B`가 아닌 더 큰 Gemma 4 모델은 로딩/응답 속도/메모리 측면에서 1차 검증 대상로는 부적절하다.
- `llama.cpp`는 ARM64 CPU-only 환경에서 가장 현실적인 선택지다.

## 보류 항목

- 정확한 GGUF 배포 소스 확정
- 사용할 양자화 버전 확정
- Ko/STT/TTS 조합 최종 선택
