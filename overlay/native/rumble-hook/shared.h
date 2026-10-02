/* 共享内存协议：RumbleHook.dll 写入，Electron 主进程读取。
   C++ 与 JS 两侧的字段偏移必须一致（JS 侧按偏移读，结构总长 56 字节）。 */
#pragma once
#include <stdint.h>

#define RUMBLE_SHARED_NAME    L"Local\\NinjaGaidenRumble"
#define RUMBLE_SHARED_MAGIC   0x4C424D52u   /* 'RMBL' (小端) */
#define RUMBLE_SHARED_VERSION 1u

#pragma pack(push, 8)
typedef struct RumbleShared {
    uint32_t magic;       /* +0  必须等于 RUMBLE_SHARED_MAGIC */
    uint32_t version;     /* +4  */
    uint32_t seq;         /* +8  每次写入自增，用于判断是否有新数据 */
    uint32_t pid;         /* +12 写入者进程 id */
    float    left;        /* +16 左马达 0~1（低频/重震动） */
    float    right;       /* +20 右马达 0~1（高频/细震动） */
    float    strength;    /* +24 max(left,right) */
    uint32_t userIndex;   /* +28 最后一次调用的手柄索引 */
    uint64_t tickMs;      /* +32 GetTickCount64() */
    uint64_t writeCount;  /* +40 累计写入次数 */
    uint32_t hookedCount; /* +48 已 hook 的 XInputSetState 数量 */
    uint32_t reserved;    /* +52 */
} RumbleShared;           /* 总长 56 */
#pragma pack(pop)
