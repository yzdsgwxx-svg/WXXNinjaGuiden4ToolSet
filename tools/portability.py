from pathlib import Path
p=Path('src/launcher.cpp');s=p.read_text(encoding='utf-8').replace('#include <windowsx.h>','#include <windowsx.h>\n#include <shobjidl.h>\n#pragma comment(lib,"ole32.lib")')
s=s.replace('#define ID_STEAM 125','#define ID_STEAM 125\n#define ID_IMPORT 126')
a=s.index('static void RefreshModState()')
s=s[:a]+'''static void InitializeOriginal(){
    if(FindGame()||!gCurrentProfile.empty()||Exists(Join(gSavesRoot,L"原始存档")))return;
    if(SaveSignature().empty())return;
    CreateDirectoryW(gSavesRoot.c_str(),nullptr);
    auto dst=Join(gSavesRoot,L"原始存档"),stage=Join(gSavesRoot,L".initial");
    if(Exists(stage)){Log(L"初始备份未完成，请检查 saves/.initial");return;}
    auto sig=SaveSignature();
    if(CopyVerified(gSaveDir,stage)&&sig==SaveSignature()&&MoveFileW(stage.c_str(),dst.c_str())){
        SaveState(L"原始存档");Log(L"已建立此 Windows 用户的原始存档");
    }
}
static void ImportAchievement(HWND w){
    if(FindGame()){Say(L"导入全成就",L"请先退出游戏。",MB_OK);return;}
    if(gCurrentProfile==L"全成就存档"){Say(L"导入全成就",L"请先切回原始存档，再导入新的全成就档案。",MB_OK);return;}
    IFileDialog* dialog=nullptr;HRESULT initialized=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
    if(SUCCEEDED(CoCreateInstance(CLSID_FileOpenDialog,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&dialog)))){
        dialog->SetOptions(FOS_PICKFOLDERS|FOS_FORCEFILESYSTEM|FOS_PATHMUSTEXIST);dialog->SetTitle(L"选择包含 GameData.dat / SlotData_*.dat 的文件夹");
        if(SUCCEEDED(dialog->Show(w))){
            IShellItem* item=nullptr;PWSTR folder=nullptr;
            if(SUCCEEDED(dialog->GetResult(&item))&&SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH,&folder))){
                auto dst=Join(gSavesRoot,L"全成就存档"),stage=Join(gSavesRoot,L".import");
                bool valid=false;for(auto& n:ListFiles(folder))if(n.find(L"SlotData_")==0&&IsSaveFile(n))valid=true;
                if(!valid||!Exists(Join(folder,L"GameData.dat")))Say(L"导入全成就",L"所选目录没有完整的游戏存档。",MB_OK|MB_ICONERROR);
                else if(Exists(dst)||Exists(stage))Say(L"导入全成就",L"全成就档案或待恢复的导入已存在，请先在档案目录中核对。",MB_OK|MB_ICONWARNING);
                else{
                    CreateDirectoryW(gSavesRoot.c_str(),nullptr);
                    if(CopyVerified(folder,stage)&&MoveFileW(stage.c_str(),dst.c_str())){RefreshProfiles();Say(L"导入全成就",L"已导入。",MB_OK);}
                    else Say(L"导入全成就",L"复制或校验失败，原始存档未改动。",MB_OK|MB_ICONERROR);
                }
                CoTaskMemFree(folder);
            }
            if(item)item->Release();
        }
        dialog->Release();
    }
    if(SUCCEEDED(initialized))CoUninitialize();
}
''' +s[a:]
s=s.replace('        Add(w,L"BUTTON",L"查看日志",0,630,590,96,32,ID_OPENSAVES);', '        Add(w,L"BUTTON",L"导入全成就",0,48,590,130,32,ID_IMPORT);\n        Add(w,L"BUTTON",L"查看日志",0,630,590,96,32,ID_OPENSAVES);')
s=s.replace('static void RefreshAll(){LoadState();RefreshProfiles();', 'static void RefreshAll(){LoadState();InitializeOriginal();RefreshProfiles();')
s=s.replace('Label(dc,48,596,L"WXX  /  忍龙 4 工具集",','Label(dc,202,596,L"WXX  /  忍龙 4 工具集",')
s=s.replace('d->CtlID==ID_OPENSAVES)?gBackground', 'd->CtlID==ID_OPENSAVES||d->CtlID==ID_IMPORT)?gBackground')
s=s.replace('        bool running=FindGame()!=0;RefreshModState();','        bool running=FindGame()!=0;RefreshModState();\n        if(!running&&gCurrentProfile.empty()){InitializeOriginal();RefreshProfiles();RefreshSaveState();}')
s=s.replace('        case ID_STEAM:{','        case ID_IMPORT:ImportAchievement(w);return 0;\n        case ID_STEAM:{')
p.write_text(s,encoding='utf-8')
p=Path('.gitignore');s=p.read_text();s+='\n/overlay/node_modules/\n/overlay/artifacts/\n/overlay/native/bin/\n/overlay/native/rumble-hook/obj/\n/overlay/native/rumble-hook/*.lib\n/overlay/native/rumble-hook/*.exp\n/artifacts/\n/dist/ControllerOverlay/\n/release/\n';p.write_text(s)
p=Path('overlay/package-lock.json');s=p.read_text().replace('"name": "ninja-gaiden-controller-overlay"','"name": "wxx-ng4-controller-overlay"').replace('"version": "1.0.3"','"version": "1.1.0"');p.write_text(s)
