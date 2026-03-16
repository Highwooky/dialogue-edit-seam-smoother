# Dialogue Edit Seam Smoother

대사 편집점의 갑작스러운 단절, 틱, 접합 이질감을 짧은 페이드와 크로스페이드로 완화하는 macOS용 도구입니다.

## 포함 파일
- `app/dialogue_edit_repair_app.py`
- `app/dialogue_edit_repair_mvp.py`
- `app/assets/icon.png`
- `.github/workflows/build-mac.yml`
- `requirements.txt`

## GitHub 업로드 구조
```text
app/
  dialogue_edit_repair_app.py
  dialogue_edit_repair_mvp.py
  assets/
    icon.png
.github/
  workflows/
    build-mac.yml
requirements.txt
README_KR.md
```

## GitHub Actions 실행 방법
1. 새 GitHub 저장소 생성
2. 위 구조 그대로 업로드
3. `Actions` 탭에서 `Build macOS App` 실행
4. 완료 후 `Artifacts`에서 `DialogueEditSeamSmoother-mac` 다운로드
5. macOS에서 압축 해제 후 `.app` 실행

## 프로그램 방향
이 프로젝트는 클릭 제거기가 아니라 **편집점 Seam Smoother**로 설계되었습니다.

핵심 개념:
- marker 기반 반자동 처리 우선
- seam score 계산
- 짧은 micro fade + short crossfade 중심 보정
- 트랜지언트 보호
- Easy Seam 노브로 간편 조정

## 권장 사용법
1. WAV/AIFF 파일 열기
2. 편집점 마커 txt/csv 불러오기
3. `Analyze`
4. seam 리스트 확인
5. `Smooth All + Save` 또는 `Smooth Selected + Save`
6. 선택 seam A/B 미리듣기

## 참고
- 아이콘은 GitHub Actions에서 `icon.icns`로 변환되어 macOS 앱 번들에 반영됩니다.
- 로컬에서 바로 실행할 때는 `icon.png`가 창 아이콘으로 사용됩니다.
