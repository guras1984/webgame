# 블록 월드

방 코드로 최대 네 명이 입장하는 브라우저 게임입니다. 방향키, WASD 또는 화면의 방향 버튼으로 이동하고 수정에 닿으면 점수를 얻습니다. 수정은 12초 뒤 다시 생깁니다.

## 로컬 실행

Node.js 22 이상에서 이 폴더를 열고 `npm start`를 실행합니다. 브라우저 탭 두 개로 http://localhost:8787 을 열어 방 생성과 참가를 확인합니다.

## 배포

- GitHub Pages는 저장소의 `block-world/index.html`을 제공합니다.
- Render에서 이 저장소로 **New → Web Service**를 만들고 아래 값을 선택합니다.
  - 이름 `kj-block-world`, 런타임 Node, 인스턴스 Free
  - Root Directory `block-world`, Build Command `npm install`, Start Command `npm start`
  - Health Check Path `/health`
- Render에서 발급된 주소가 `https://kj-block-world.onrender.com`과 다르면 HTML의 `deployed` 값을 실제 주소로 바꿉니다.
- 다른 사이트에서 클라이언트를 제공할 경우 환경 변수 `ALLOWED_ORIGINS`에 해당 출처를 쉼표로 구분해 지정합니다. 기본값은 `https://guras1984.github.io`입니다.

브라우저는 약 100ms마다 이동과 상태를 교환합니다. 방과 점수는 서버 메모리에 있으므로 서버가 재시작되면 새 방을 만들어야 합니다.
