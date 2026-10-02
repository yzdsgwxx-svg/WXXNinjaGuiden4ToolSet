const koffi=require('koffi');
const path=require('node:path');
// Windows' version-0 GameInput COM ABI, available in the system GameInput.dll.
const sig={
 release:koffi.proto('uint32_t __stdcall release(void *self)'),
 focus:koffi.proto('void __stdcall focus(void *self, uint32_t policy)'),
 current:koffi.proto('int32_t __stdcall current(void *self, uint32_t kind, void *device, _Out_ void **reading)'),
 state:koffi.proto('bool __stdcall state(void *self, _Out_ void *state)'),
 device:koffi.proto('void __stdcall device(void *self, _Out_ void **device)'),
 status:koffi.proto('uint32_t __stdcall status(void *self)')
};
function method(object,slot,type,...args){
 const table=koffi.decode(object,'void *');
 const fn=koffi.decode(table,slot*koffi.sizeof('void *'),'void *');
 return koffi.call(fn,sig[type],object,...args);
}
function decodeGameInput(buffer){
 const masks=[4,8,16,32,1024,2048,0,0,2,1,4096,8192,64,128,256,512];
 const bits=buffer.readUInt32LE(0),buttons=masks.map(m=>({value:m&&(m&bits)?1:0}));
 buttons[6].value=buffer.readFloatLE(4);buttons[7].value=buffer.readFloatLE(8);
 return {index:0,id:'GameInput · 后台输入已启用',buttons,axes:[buffer.readFloatLE(12),-buffer.readFloatLE(16),buffer.readFloatLE(20),-buffer.readFloatLE(24)]};
}
function createGameInputReader(){
 const lib=koffi.load(path.join(process.env.SystemRoot||'C:\\Windows','System32','GameInput.dll'));
 const create=lib.func('int32_t __stdcall GameInputCreate(_Out_ void **instance)');
 const out=[null],hr=create(out);if(hr<0||!out[0])throw new Error('GameInputCreate: '+hr);
 const instance=out[0];
 // GameInputEnableBackgroundInput; do not request exclusive foreground access.
 method(instance,21,'focus',0x40);
 const buffer=Buffer.alloc(28);
 function read(){
  const reading=[null];
  if(method(instance,4,'current',0x40000,null,reading)<0||!reading[0])return [];
  try{
   const device=[null];method(reading[0],6,'device',device);
   if(device[0]){try{if(!(method(device[0],4,'status')&1))return [];}finally{method(device[0],2,'release');}}
   if(!method(reading[0],22,'state',buffer))return [];
   return [decodeGameInput(buffer)];
  }finally{method(reading[0],2,'release');}
 }
 read.close=()=>method(instance,2,'release');
 /* koffi 会在库的所有引用都消失后自动 FreeLibrary（见 koffi doc/load.md）。lib 和 create 只活在
    本函数的局部作用域里，返回后一旦被 GC 回收，GameInput.dll 就被卸载，先前 GameInputCreate 拿到的
    COM 对象 vtable 立刻变成野指针，几十秒后随机触发 0xc0000005（崩溃栈落在 koffi.node）。
    把引用挂在返回的 read 上，reader 活着库就不会被卸载。 */
 read.lib=lib;
 read.create=create;
 return read;
}
module.exports={createGameInputReader,decodeGameInput};
