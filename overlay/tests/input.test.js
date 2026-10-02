const {test}=require('node:test');
const assert=require('node:assert/strict');
const {normalize,stick,wobble}=require('../input');
const {startServer}=require('../server');
test('disconnect releases all buttons and axes',()=>{const state=normalize(null);assert.ok(state.buttons.every(v=>v===0));assert.deepEqual(state.left,[0,0]);});
test('radial deadzone removes drift and preserves diagonal direction',()=>{assert.deepEqual(stick(.04,-.03,.08),[0,0]);const s=stick(1,1,.08);assert.ok(Math.abs(Math.hypot(...s)-1)<1e-9);assert.equal(s[0],s[1]);});
test('analog triggers retain partial travel; invalid inputs are bounded',()=>{const s=normalize({buttons:[{value:.42},{value:9}],axes:[NaN,Infinity,-2,0]});assert.equal(s.buttons[0],.42);assert.equal(s.buttons[1],1);assert.deepEqual(s.left,[0,0]);assert.deepEqual(s.right,[-1,0]);});
test('broadcast URL serves transparent source and relays live state',async()=>{
 const relay=await startServer(0); const base=`http://127.0.0.1:${relay.port}`;
 try{
  assert.equal((await fetch(base+'/overlay')).status,200);
  assert.equal((await fetch(base+'/main.js')).status,404);
  const abort=new AbortController();
  const response=await fetch(base+'/events',{signal:abort.signal});const reader=response.body.getReader();await reader.read();
  relay.publish({buttons:[1],left:[.5,0],right:[0,0],connected:true});
  const {value}=await reader.read();assert.match(new TextDecoder().decode(value),/"buttons":\[1\]/);abort.abort();
 }finally{relay.server.closeAllConnections();relay.server.close();}
});
test('rumble wobble interpolates ±2.5% smoothly at 16 Hz',()=>{
 const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
 near(wobble(.5,0),.5);            // 从中位出发
 near(wobble(.5,15.625),.525);     // 1/4 周期到上限
 near(wobble(.5,46.875),.475);     // 3/4 周期到下限
 near(wobble(.5,62.5),.5);         // 一个周期回到中位
 let prev=wobble(.5,0), maxJump=0;
 for(let t=2;t<=250;t+=2){const v=wobble(.5,t);maxJump=Math.max(maxJump,Math.abs(v-prev));prev=v;}
 assert.ok(maxJump<.025,`值有跳变，说明没插值：${maxJump}`);   // 逐帧必须平滑（方波会是 0.05）
 near(wobble(0,0),0); near(wobble(.01,0),.01);               // 不震动 / 低于阈值不抖
 near(wobble(.99,15.625),1); near(wobble(.5,0,0),.5);        // 夹在 0..1；幅度 0 = 关闭
});
