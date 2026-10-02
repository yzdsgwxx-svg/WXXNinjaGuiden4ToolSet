/* 开发期验证用目标进程：静态导入 xinput1_4，持续写入固定的震动值。
   用来验证 RumbleHook.dll 注入后能否读到 XInputSetState 的入参。
   左马达 40000/65535 = 0.610，右马达 15000/65535 = 0.229。 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <xinput.h>
#include <stdio.h>

#pragma comment(lib, "xinput.lib")

int main(void) {
    XINPUT_VIBRATION vibration;
    vibration.wLeftMotorSpeed  = 40000;
    vibration.wRightMotorSpeed = 15000;
    printf("rumble-test: left=%.3f right=%.3f pid=%lu\n", 40000.0 / 65535.0, 15000.0 / 65535.0, GetCurrentProcessId());
    fflush(stdout);
    for (int i = 0; i < 6000; i++) {
        XInputSetState(0, &vibration);
        Sleep(20);
    }
    XINPUT_VIBRATION zero = { 0, 0 };
    XInputSetState(0, &zero);
    printf("rumble-test: done\n");
    return 0;
}
