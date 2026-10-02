const {test}=require('node:test');
const assert=require('node:assert/strict');
const {decodeState,makeFrame}=require('../native-input');
test('XInput layout maps shoulders, triggers, D-pad and signed axes',()=>{
 const b=Buffer.alloc(16);b.writeUInt16LE(0x1000|0x200|0x20|1,4);b[6]=128;b[7]=255;
 b.writeInt16LE(-32768,8);b.writeInt16LE(32767,10);b.writeInt16LE(32767,12);b.writeInt16LE(-32768,14);
 const pad=decodeState(b,2);assert.equal(pad.index,2);
 for(const index of [0,5,8,12])assert.equal(pad.buttons[index].value,1);
 assert.equal(pad.buttons[4].value,0);assert.equal(pad.buttons[6].value,128/255);assert.equal(pad.buttons[7].value,1);
 assert.deepEqual(pad.axes,[-1,-1,1,1]);
});
test('main-process stream follows selection and releases on disconnect without page state',()=>{
 const cfg={device:'2',deadzone:8,demo:false,opacity:100,extras:true,mapping:{C:17,Z:18}};
 const b=Buffer.alloc(16);b.writeUInt16LE(0x2000,4);
 const state=makeFrame([decodeState(b,2)],cfg);assert.equal(state.buttons[1],1);assert.equal(state.connected,true);
 const released=makeFrame([],cfg);assert.equal(released.connected,false);assert.ok(released.buttons.every(v=>v===0));
 assert.equal(makeFrame([decodeState(b,1)],cfg).connected,false);
});
