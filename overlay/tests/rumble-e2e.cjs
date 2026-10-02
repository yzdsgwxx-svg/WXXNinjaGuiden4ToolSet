const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),path=require('node:path');
const source=require('../rumble-source');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const target=spawn(path.resolve(__dirname,'../native/bin/rumble-test.exe'),[],{windowsHide:true,stdio:'ignore'});
 try {
  await wait(400);const result=source.injectDll(target.pid,path.resolve(__dirname,'../native/bin/RumbleHook.dll'));assert.equal(result.ok,true,JSON.stringify(result));
  source.selectTarget(target.pid);await wait(500);
  let r=source.readRumble();assert.equal(r.pid,target.pid);assert.ok(Math.abs(r.strength-40000/65535)<0.001,JSON.stringify(r));assert.ok(r.hookedCount>0);
  assert.equal(source.setEnabled(target.pid,false),true);await wait(300);r=source.readRumble();assert.equal(r.hookedCount,0);assert.equal(r.strength,0);
  assert.equal(source.setEnabled(target.pid,true),true);await wait(300);r=source.readRumble();assert.ok(r.strength>0.6);assert.ok(r.hookedCount>0);
  console.log('PASS: native injection, selected PID isolation, rumble readback, disable, re-enable');
 } finally {source.setEnabled(target.pid,false);source.closeView();target.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
