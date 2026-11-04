# 2026-11-04 안정성 점검

새 GURAS1984 아케이드를 등록했습니다. 홈 화면 바로가기에서 표지·목록 버전 변경도 감지하고, 오프라인에서는 주기적인 목록 요청을 쉬도록 했습니다.

기존 게임 규칙과 정상 저장 기록을 유지합니다.

## 재현 검사

Playwright와 Chromium이 준비된 환경에서 사이트를 로컬 서버로 띄운 뒤 실행합니다.

```sh
node tests/browser-regression.cjs
```

기본 주소는 `http://127.0.0.1:8000/`입니다. 다른 주소는 `TEST_URL`, 브라우저 실행 파일은 `BROWSER_EXECUTABLE`, Playwright 설치 경로는 `PLAYWRIGHT_MODULE`로 지정할 수 있습니다. GURAS1984game은 docs 폴더를 서버 루트로 사용합니다.

휴대폰 세로·가로, 태블릿, PC 크기에서 초기 로딩을 확인했습니다. 실제 iPhone·iPad·Galaxy의 기종별 장시간 플레이까지 보증하는 검사는 아닙니다.
