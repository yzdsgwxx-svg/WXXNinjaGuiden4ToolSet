const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
 for(const name of ['toolset','overlay']){
  let svg=fs.readFileSync(path.join(__dirname,'../assets',name+'.svg'),'utf8');
  for(const asset of ['sword-base.png','sword-energy.png']) svg=svg.replaceAll(asset,'data:image/png;base64,'+fs.readFileSync(path.join(__dirname,asset)).toString('base64'));
  const w=new BrowserWindow({width:256,height:256,show:false,frame:false,transparent:true,webPreferences:{offscreen:true}});
  await w.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<style>html,body{margin:0;background:transparent}svg{width:256px;height:256px}.surface{fill:url(#button);stroke:#777}.legend{fill:#ddd;text-anchor:middle;font-size:25px}</style>'+svg));
  await new Promise(r=>setTimeout(r,400));
  fs.writeFileSync(path.join(__dirname,'../assets',name+'.png'),(await w.webContents.capturePage()).toPNG());w.destroy();
 }
 app.quit();
});

