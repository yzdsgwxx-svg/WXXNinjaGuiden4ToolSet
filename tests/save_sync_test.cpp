#define wWinMain launcherEntryForTest
#include "../src/launcher.cpp"
#include <cassert>
#include <filesystem>
static void Write(const std::wstring& dir,const wchar_t* name,const char* data){
    CreateDirectoryW(dir.c_str(),nullptr);FILE* f=nullptr;_wfopen_s(&f,Join(dir,name).c_str(),L"wb");assert(f);fputs(data,f);fclose(f);
}
int main(){
    if(FindGame()){puts("SKIP: close game before isolated save tests");return 2;}
    wchar_t tmp[MAX_PATH],root[MAX_PATH];GetTempPathW(MAX_PATH,tmp);swprintf_s(root,L"%sWXXSaveTests_%lu",tmp,GetCurrentProcessId());
    CreateDirectoryW(root,nullptr);gSavesRoot=Join(root,L"saves");gSaveDir=Join(root,L"game");CreateDirectoryW(gSavesRoot.c_str(),nullptr);
    gCurrentProfile=L"原始存档";auto dst=Join(gSavesRoot,gCurrentProfile.c_str());
    Write(dst,L"SlotData_2.dat","stale");Write(gSaveDir,L"GameData.dat","fresh");Write(gSaveDir,L"SlotData_0.dat","progress");Write(gSaveDir,L"steam_autocloud.vdf","cloud");
    assert(SyncCurrentProfile());assert(!Exists(Join(dst,L"SlotData_2.dat")));assert(!Exists(Join(dst,L"steam_autocloud.vdf")));
    std::string a,b;assert(Sha256(Join(gSaveDir,L"SlotData_0.dat"),a));assert(Sha256(Join(dst,L"SlotData_0.dat"),b));assert(a==b);
    assert(SyncCurrentProfile());assert(ListDirs(gSavesRoot).size()==1);
    Write(Join(gSavesRoot,L".pending"),L"GameData.dat","interrupted");Write(gSaveDir,L"SlotData_0.dat","newer");assert(!SyncCurrentProfile());assert(Sha256(Join(dst,L"SlotData_0.dat"),a)&&a==b);
    assert(ClearSaveFiles(gSaveDir));assert(Exists(Join(gSaveDir,L"steam_autocloud.vdf")));assert(!Exists(Join(gSaveDir,L"GameData.dat")));
    assert(!CopyVerified(Join(root,L"absent"),Join(root,L"copy")));
    puts("PASS: verified sync, stale-file cleanup, no snapshot growth, interrupted transaction protection, cloud preservation, empty-source rejection");
    // Test-owned directory only; no production save path is used.
    std::filesystem::remove_all(root);return 0;
}
