const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const version = (() => { try { return require('./package.json').version; } catch { return '0.0.0'; } })();
function startServer(port = 17845) {
  let latest = { buttons: Array(23).fill(0), left: [0,0], right: [0,0], connected: false }, updated = 0;
  const clients = new Set();
  const files = { '/': 'index.html', '/overlay': 'index.html', '/style.css': 'style.css', '/renderer.js': 'renderer.js', '/input.js': 'input.js', '/controller.svg': 'controller.svg', '/sword-base.png':'sword-base.png', '/sword-energy.png':'sword-energy.png' };
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    if(url.pathname==='/status'){
      res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});
      res.end(JSON.stringify({version,backend:'GameInput',updated,clients:clients.size,state:latest}));return;
    }
    if (url.pathname === '/events') {
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Content-Type-Options': 'nosniff' });
      res.write(`data: ${JSON.stringify(latest)}\n\n`); clients.add(res);
      req.on('close', () => clients.delete(res)); return;
    }
    const file = files[url.pathname];
    if (!file) { res.writeHead(404); res.end(); return; }
    const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.png':'image/png' };
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)], 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    fs.createReadStream(path.join(__dirname, file)).pipe(res);
  });
  function publish(state) { latest = state; updated = Date.now(); for (const client of clients) client.write(`data: ${JSON.stringify(state)}\n\n`); }
  const heartbeat = setInterval(() => {
    if (Date.now() - updated > 1000 && latest.connected) publish({ ...latest, connected: false, buttons: Array(23).fill(0), left:[0,0], right:[0,0] });
    for(const client of clients) client.write(': heartbeat\n\n');
  }, 1000);
  server.on('close', () => { clearInterval(heartbeat); for(const client of clients) client.end(); });
  return new Promise((resolve, reject) => { server.once('error', error => { clearInterval(heartbeat); reject(error); }); server.listen(port, '127.0.0.1', () => resolve({ server, publish, port: server.address().port })); });
}
module.exports = { startServer };
