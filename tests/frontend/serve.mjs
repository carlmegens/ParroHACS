// Local synthetic preview only. Only these three public source files are served.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..');
const port=Number(process.env.PARRO_PREVIEW_PORT||8766);
const routes=new Map([
  ['/tests/frontend/index.html','text/html'],
  ['/tests/frontend/harness.js','text/javascript'],
  ['/custom_components/parro/frontend/parro-card.js','text/javascript'],
]);
const server=http.createServer(async(req,res)=>{
  try {
    const route=new URL(req.url,'http://localhost').pathname;
    if(!['GET','HEAD'].includes(req.method)) {res.writeHead(405,{'Allow':'GET, HEAD'}).end();return;}
    if(!routes.has(route)) {res.writeHead(404).end('Not found');return;}
    const data=await readFile(resolve(root,'.'+route));
    res.writeHead(200,{'Content-Type':routes.get(route),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
    res.end(req.method==='HEAD'?undefined:data);
  }catch{res.writeHead(404).end('Not found');}
});
server.listen(port,'127.0.0.1',()=>console.log(`Parro synthetic preview: http://127.0.0.1:${port}/tests/frontend/index.html`));
