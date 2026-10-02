const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('desktop', {
  configure: config => ipcRenderer.send('input-config', config),
  sourceUrl: () => ipcRenderer.invoke('source-url'),
  copyUrl: () => ipcRenderer.send('copy-url'),
  action: name => { if (['close', 'minimize'].includes(name)) ipcRenderer.send('window-action', name); },
  startDrag: () => ipcRenderer.send('drag-start'),
  endDrag: () => ipcRenderer.send('drag-end'),
  log: message => ipcRenderer.send('renderer-log', String(message)),
  rumbleInfo: () => ipcRenderer.invoke('rumble-info'),
  rumbleProcesses: () => ipcRenderer.invoke('rumble-processes'),
  rumbleInject: pid => ipcRenderer.invoke('rumble-inject', pid),
  rumbleClear: () => ipcRenderer.invoke('rumble-clear')
});
