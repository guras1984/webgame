# KJ Patch Downloader 1.1.0

Windows Server 업데이트를 조회하고 선택한 파일을 Microsoft에서 일괄 다운로드하는 로컬 프로그램입니다.

## 실행

- Windows 10/11 x64는 `KJ-Patch-Downloader-Setup.exe` 설치 프로그램을 사용합니다. Python 설치는 필요 없습니다. 설치 중 바탕화면 바로가기가 기본 선택되며 시작 메뉴 바로가기도 추가됩니다. 제거는 Windows 설정의 설치된 앱에서 할 수 있습니다.
- macOS Apple Silicon은 ZIP을 풀고 `KJ Patch Downloader.app`을 실행합니다. 최소 macOS 13을 대상으로 제작했습니다.
- Windows와 macOS 모두 앱 자체 창을 사용합니다. 별도 브라우저 창이나 localhost 주소가 뜨지 않습니다. 파일은 실행한 컴퓨터의 지정 폴더에 저장됩니다.
- 소스 실행은 Windows, macOS, Linux에서 Python 3.9 이상으로 `python app.py`를 실행합니다. GUI 앱 빌드에는 `PySide6`와 `certifi`가 필요합니다.

## 사용 순서

1. Windows Server 2016, 2019, 2022, 2025 및 기준일과 종료일을 선택합니다.
2. **업데이트 조회**를 누른 뒤 원하는 항목을 선택합니다.
3. **선택 항목 파일 확인**을 누릅니다.
4. **선행·권장 패치도 함께 다운로드** 체크박스와 파일별 체크박스로 포함 범위를 결정합니다. 기본은 포함입니다.
5. 저장 폴더를 정하고 **선택 파일 다운로드**를 누릅니다.

## 범위와 날짜

대상은 x64 일반 LTSC 서버의 카탈로그 OS 업데이트와 선택 가능한 .NET 업데이트입니다. 2022는 Microsoft server operating system 21H2, 2025는 24H2 제품명을 함께 검색합니다. 미리보기는 선택할 수 있습니다. Azure 전용 Hotpatch와 드라이버는 범위에서 제외됩니다.

기간 필터는 Microsoft 카탈로그의 **Last Updated(게시·갱신일)** 을 사용합니다. 이는 최초 출시일과 다를 수 있습니다. 기본은 기준일 다음 날부터 종료일까지이며, 기준일 당일 포함 옵션이 있습니다. 카탈로그에서 제거된 파일을 복구하는 기능은 제공하지 않습니다.

## 선행 패치 확인

Server 2025 누적 업데이트의 다운로드 목록에 포함된 체크포인트 MSU를 식별합니다. 공식 KB 문서의 설치 전 조건에 언급된 KB도 해당 서버 패키지와 대조합니다. 문서에서 조건이 붙은 권장 사항이 함께 추출될 수 있으므로 원문을 화면에서 확인할 수 있습니다. 추가 파일의 날짜는 카탈로그에서 확인한 날짜입니다.

확정할 수 없는 관계, 여러 패키지로 나뉜 KB, 읽지 못한 공식 문서는 경고로 표시됩니다. 대상 서버의 현재 설치 상태는 검사하지 않습니다. 설치 필요 여부와 순서는 대상 서버의 설치된 SSU·LCU 및 공식 KB 문서를 기준으로 결정하세요. 다운로드 작업과 설치 작업은 별개이며 이 앱은 파일 수집을 수행합니다.

## 다운로드와 재시도

Microsoft에서 제공한 SHA-256 또는 SHA-1 검증값과 대조한 뒤 완성 파일로 저장합니다. 같은 파일이 이미 있으면 검증 후 건너뜁니다. 끊긴 파일은 `.kj-partial`에 보관하며 다음 실행에서 서버가 Range를 지원하면 이어받습니다. 손상 파일은 재다운로드합니다. 최종 실패 항목만 다시 받을 수 있습니다. 같은 폴더에 대한 동시 다운로드를 잠금으로 방지합니다.

결과와 검증값은 저장 폴더에 CSV 및 JSON으로 기록됩니다. 회사 프록시는 운영체제 또는 표준 `HTTPS_PROXY` 환경변수 구성을 사용합니다. 인터넷에서 Microsoft Catalog, Microsoft Support, Microsoft 다운로드 서버에 접근할 수 있어야 합니다.

## 검증

`python -m unittest discover -s tests -v`

실제 서버 조회 및 작은 Microsoft 파일 다운로드 검사는 `python tests/live_check.py 임시저장폴더`로 실행합니다. 이 검사는 2026-11-12에 확인한 KB 사례를 사용합니다.

2026-11-12 기준 macOS에서 네 서버 버전 조회, Server 2025 체크포인트 식별, 공식 CAB 다운로드·해시 검증·기존 파일 건너뛰기를 확인했습니다. Windows 설치 파일은 Windows GitHub Actions에서 빌드하며 실제 Windows 데스크톱 실행 확인은 별도로 필요합니다. macOS 앱은 Developer ID 서명 및 공증이 포함되지 않아 처음 실행 시 보안 경고가 표시될 수 있습니다.

## 공식 자료

- [Microsoft Update Catalog](https://www.catalog.update.microsoft.com/)
- [체크포인트 누적 업데이트](https://learn.microsoft.com/windows/deployment/update/catalog-checkpoint-cumulative-updates)
- [Windows Server 릴리스 정보](https://learn.microsoft.com/windows-server/get-started/windows-server-release-info)
