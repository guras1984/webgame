#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR command, int show) {
    (void)instance; (void)previous; (void)command; (void)show;
    wchar_t root[32768], python[32768], script[32768], args[65536];
    GetModuleFileNameW(NULL, root, 32768);
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    swprintf(python, 32768, L"%ls\\Runtime\\python.exe", root);
    swprintf(script, 32768, L"%ls\\App\\app.py", root);
    swprintf(args, 65536, L"\"%ls\" \"%ls\"", python, script);
    STARTUPINFOW startup = {0}; startup.cb = sizeof(startup);
    PROCESS_INFORMATION process = {0};
    if (!CreateProcessW(python, args, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, root, &startup, &process)) {
        MessageBoxW(NULL, L"ZIP 전체를 압축 해제한 뒤 실행해 주세요. Runtime과 App 폴더가 필요합니다.", L"KJ Patch Downloader", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD status = 0; GetExitCodeProcess(process.hProcess, &status); CloseHandle(process.hProcess);
    if (status) MessageBoxW(NULL, L"프로그램 실행 중 오류가 발생했습니다. App 폴더의 app.py를 Python 3으로 실행해 상세 오류를 확인할 수 있습니다.", L"KJ Patch Downloader", MB_OK | MB_ICONERROR);
    return (int)status;
}
