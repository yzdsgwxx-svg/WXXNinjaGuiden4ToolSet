const path=require('node:path');
const fs=require('node:fs');
const koffi=require('koffi');
function createSDLReader(){
  const bundled=path.join(process.resourcesPath||__dirname,'vendor','SDL3','SDL3.dll');
  const lib=koffi.load(fs.existsSync(bundled)?bundled:path.join(__dirname,'vendor','SDL3','SDL3.dll'));
  const hint=lib.func('bool SDL_SetHint(const char *name, const char *value)');
  hint('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS','1');
  hint('SDL_JOYSTICK_GAMEINPUT','1');
  const init=lib.func('bool SDL_Init(uint32_t flags)');
  const error=lib.func('const char *SDL_GetError()');
  lib.func('void SDL_SetMainReady()')();
  if(!init(0x2000))throw new Error(error());
  const update=lib.func('void SDL_UpdateGamepads()');
  const pump=lib.func('void SDL_PumpEvents()');
  const list=lib.func('void *SDL_GetGamepads(_Out_ int *count)');
  const free=lib.func('void SDL_free(void *ptr)');
  const open=lib.func('void *SDL_OpenGamepad(uint32_t id)');
  const close=lib.func('void SDL_CloseGamepad(void *pad)');
  const name=lib.func('const char *SDL_GetGamepadName(void *pad)');
  const axis=lib.func('int16_t SDL_GetGamepadAxis(void *pad, int axis)');
  const button=lib.func('bool SDL_GetGamepadButton(void *pad, int button)');
  const connected=lib.func('bool SDL_GamepadConnected(void *pad)');
  const pads=new Map();let scanAt=0;
  function read(){
    pump();update();
    if(Date.now()>scanAt){
      scanAt=Date.now()+1000;
      const count=[0],ptr=list(count);
      if(ptr){const ids=koffi.decode(ptr,'uint32_t',count[0]);free(ptr);for(const id of ids)if(!pads.has(id)){const pad=open(id);if(pad)pads.set(id,pad);}}
    }
    const result=[];
    for(const [id,pad] of pads){
      if(!connected(pad)){close(pad);pads.delete(id);continue;}
      const mapping=[0,1,2,3,9,10,-1,-1,4,6,7,8,11,12,13,14,5];
      const buttons=mapping.map(n=>({value:n<0?0:Number(button(pad,n))}));
      buttons[6].value=Math.max(0,axis(pad,4))/32767;buttons[7].value=Math.max(0,axis(pad,5))/32767;
      const axes=[0,1,2,3].map(n=>{const v=axis(pad,n);return v/(v<0?32768:32767);});
      result.push({index:String(id),id:`${name(pad)} · SDL 后台`,buttons,axes});
    }
    return result;
  }
  read.close=()=>{for(const pad of pads.values())close(pad);pads.clear();lib.func('void SDL_Quit()')();};
  return read;
}
module.exports={createSDLReader};
