# 게임 목록 개인화 — 2026-11-04

[CrazyGames](https://www.crazygames.com/)의 최근 게임·장르 분류와 [Poki](https://poki.com/)의 빠른 게임 진입 흐름을 참고해 이 목록에 맞는 기능을 추가했다.

- 카드의 하트로 좋아요를 저장하고, 전체·최근 게임·좋아요를 전환한다.
- 최근 게임은 실행 링크를 누른 시각순이다. 실제 진행률이나 플레이 시간을 수집하지 않는다. 홈의 마지막 게임 링크로 바로 다시 열 수 있다.
- 장르와 여러 단어 검색을 동시에 적용하며, 결과가 없으면 전체 목록으로 되돌릴 수 있다.
- 좋아요·최근 목록은 `my-world:library:v1`에, 현재 탭의 검색·분류·스크롤은 `my-world:library-view:v1`에 저장한다. 원격 서버로 보내지 않는다. 기존 게임 저장 데이터는 수정하지 않는다.
- 저장 차단과 손상된 목록을 처리하고 다른 탭의 변경을 반영한다.
- 소스는 `library.js`, `library.css`로 분리했다. 새 카드에 고유한 `data-game`과 `data-genre`(puzzle/adventure/arcade/rhythm)를 지정한다.

`tests/library-browser.cjs`의 9개 검사(동작·저장 복구·5개 화면 크기)가 통과했다. Chrome 자동화 결과이며 실제 기기 장시간 플레이는 별도다.

정적 서버를 실행하고 `TEST_URL=http://127.0.0.1:8000/ node tests/library-browser.cjs`로 재검사한다. Playwright 설치가 필요하며 `PLAYWRIGHT_MODULE`, `BROWSER_EXECUTABLE`, `TEST_ARTIFACTS`로 환경을 지정할 수 있다.
