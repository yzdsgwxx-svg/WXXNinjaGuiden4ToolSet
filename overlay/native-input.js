const { normalize, demo } = require('./input');
const masks = [0x1000,0x2000,0x4000,0x8000,0x100,0x200,0,0,0x20,0x10,0x40,0x80,1,2,4,8];
function decodeState(buffer, index) {
  const bits=buffer.readUInt16LE(4);
  const buttons=masks.map(mask=>({value:mask && (bits & mask)?1:0}));
  buttons[6].value=buffer[6]/255; buttons[7].value=buffer[7]/255;
  const axis=offset=>{const v=buffer.readInt16LE(offset);return v/(v<0?32768:32767);};
  return {index,id:`XInput ${index+1} · 后台采集`,buttons,axes:[axis(8),-axis(10),axis(12),-axis(14)]};
}
function createReader() {
  const koffi=require('koffi');
  const path=require('node:path');
  const lib=koffi.load(path.join(process.env.SystemRoot || 'C:\\Windows','System32','xinput1_4.dll'));
  const getState=lib.func('uint32_t __stdcall XInputGetState(uint32_t index, _Out_ void *state)');
  const buffers=Array.from({length:4},()=>Buffer.alloc(16));
  const nextScan=Array(4).fill(0), connected=Array(4).fill(false);
  const read=()=>{
    const pads=[],now=Date.now();
    for(let i=0;i<4;i++){
      if(!connected[i] && now<nextScan[i])continue;
      connected[i]=getState(i,buffers[i])===0;
      if(connected[i])pads.push(decodeState(buffers[i],i));
      else nextScan[i]=now+1000;
    }
    return pads;
  };
  /* 同上：挂住 koffi 库引用，避免被 GC 回收后自动 FreeLibrary。 */
  read.lib=lib;
  read.close=()=>{};
  return read;
}
function makeFrame(pads, config, time=Date.now()/1000, error='') {
  const pad=config.device==='auto'?pads[0]:pads.find(p=>String(p.index)===config.device);
  return {...(config.demo?demo(time):normalize(pad,config.deadzone/100)),
    connected:!!pad||config.demo,buttonCount:config.demo?19:pad?.buttons.length||0,
    name:config.demo?'演示模式 · 非真实手柄输入':pad?.id || error || '未检测到 XInput 手柄 · 请切换手柄至 XInput 模式',
    demo:config.demo,devices:pads.map(p=>({index:p.index,id:p.id})),
    config:{opacity:config.opacity,extras:config.extras,mapping:config.mapping}};
}
module.exports={createReader,decodeState,makeFrame};
