from pathlib import Path
p=Path('src/launcher.cpp');s=p.read_text(encoding='utf-8');a=s.index('static void ImportAchievement(');b=s.index('static void RefreshModState()',a);s=s[:a]+s[b:];s=s.replace('#include <shobjidl.h>\n','').replace('#pragma comment(lib,"ole32.lib")\n','').replace('#define ID_IMPORT 126\n','').replace('        Add(w,L"BUTTON",L"导入全成就",0,48,590,130,32,ID_IMPORT);\n','').replace('        case ID_IMPORT:ImportAchievement(w);return 0;\n','').replace('||d->CtlID==ID_IMPORT','').replace('Label(dc,202,596,L"WXX  /  忍龙 4 工具集",','Label(dc,48,596,L"WXX  /  忍龙 4 工具集",')
needle='        if(d->CtlID==ID_MOD_LOAD||'
a=s.index(needle)
s=s[:a]+'''        if(d->CtlID==ID_MINIMIZE||d->CtlID==ID_CLOSE){
            if(down){HBRUSH pressed=CreateSolidBrush(d->CtlID==ID_CLOSE?RGB(133,37,54):RGB(47,43,51));FillRect(d->hDC,&d->rcItem,pressed);DeleteObject(pressed);}
            Gdiplus::Graphics graphics(d->hDC);graphics.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
            Gdiplus::Pen line(Gdiplus::Color(255,206,192,193),1.5f);
            float cx=(d->rcItem.right+d->rcItem.left)*0.5f,cy=(d->rcItem.top+d->rcItem.bottom)*0.5f;
            if(d->CtlID==ID_MINIMIZE)graphics.DrawLine(&line,cx-6,cy+2,cx+6,cy+2);
            else{graphics.DrawLine(&line,cx-5,cy-5,cx+5,cy+5);graphics.DrawLine(&line,cx+5,cy-5,cx-5,cy+5);}
            if(d->itemState&ODS_FOCUS)DrawFocusRect(d->hDC,&d->rcItem);return TRUE;
        }
''' +s[a:]
p.write_text(s,encoding='utf-8')
p=Path('overlay/style.css');s=p.read_text(encoding='utf-8')+'''
#minimize,#close{font-size:0;width:32px;height:32px;padding:0;border:0;background:transparent;align-self:center;border-radius:6px}
#minimize:hover{background:#ffffff0c}#close:hover{background:#b72a40}
#minimize::after,#close::before,#close::after{content:"";position:absolute;width:12px;height:1.5px;background:#cec0c1;left:10px;top:15px;pointer-events:none}
#minimize::after{top:18px}#close::before{transform:rotate(45deg)}#close::after{transform:rotate(-45deg)}
''';p.write_text(s,encoding='utf-8')
