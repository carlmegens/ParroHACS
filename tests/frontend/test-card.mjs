import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('playwright');
const base=process.env.PARRO_PREVIEW_URL||'http://127.0.0.1:8766/tests/frontend/index.html';
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1100,height:1000}});
let passed=0;
async function test(name,fn){try{await fn();passed++;console.log(`PASS ${name}`);}catch(error){console.error(`FAIL ${name}`);throw error;}}
async function ready(query=''){await page.goto(base+query);await page.waitForFunction(()=>window.card && !card._loading && card._started);}
const count=(selector)=>page.locator(`parro-card >> ${selector}`).count();
try {
 await test('real card renders feed, native controls, and authenticated photos',async()=>{
  for(const route of ['/README.md','/custom_components/parro/api.py','/dist/ParroHACS-publish/README.md','/tests/frontend/test-card.mjs','/tests/frontend/artifacts/desktop-light.png']) {
   assert.equal((await page.request.get(new URL(route,base).href)).status(),404);
  }
  await ready();assert.equal(await count('article'),3);await page.waitForFunction(()=>card._urls.size>=2);
  assert.match(await page.locator('parro-card >> h2').innerText(),/Parro/);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='parro/feed').length),1);
  assert.ok(await page.evaluate(()=>fixture.photoCalls.every(x=>/^\/api\/parro\/example-account\/image\/[A-Za-z0-9_-]{32}$/.test(x))));
  assert.ok(await page.locator('parro-card >> .photo img').first().getAttribute('src').then(x=>x.startsWith('blob:')));
 });
 await test('HA state updates never cause feed refetches',async()=>{
  const before=await page.evaluate(()=>fixture.calls.length);
  await page.evaluate(()=>{for(let i=0;i<100;i++)card.hass=makeHass();});
  assert.equal(await page.evaluate(()=>fixture.calls.length),before);
 });
 await test('keyboard expands message and photo, and restores focus on close',async()=>{
  const toggle=page.locator('parro-card >> .toggle').first();await toggle.focus();await page.keyboard.press('Enter');
  assert.equal(await toggle.getAttribute('aria-expanded'),'true');
  assert.ok(await page.locator('parro-card >> .body').first().innerText().then(x=>x.includes('Op vrijdag')));
  const photo=page.locator('parro-card >> .photo').first();await photo.focus();await page.keyboard.press('Enter');
  assert.equal(await count('.enlarged'),1);await page.locator('parro-card >> .close-photo').click();assert.equal(await count('.enlarged'),0);
  assert.equal(await photo.evaluate(el=>el.getRootNode().activeElement===el),true);
 });
 await test('untrusted message and title are text, never HTML',async()=>{
  await page.evaluate(async()=>{fixture.items=[{id:'attack',title:'<img src=x onerror="window.__xss=1">',contents:'<script>window.__xss=1</script><img src=x onerror="window.__xss=1">',images:[]}];await card._load(true);});
  assert.equal(await count('script'),0);assert.equal(await count('img'),0);assert.equal(await page.evaluate(()=>window.__xss),undefined);
  assert.ok(await page.locator('parro-card >> .body').innerText().then(x=>x.includes('<script>')));
 });
 await test('account switching discards pending response data',async()=>{
  await page.goto(base+'?state=loading');await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.evaluate(()=>card.setConfig({...card._config,config_entry_id:'second-account'}));await page.waitForFunction(()=>fixture.deferred.length===2);
  await page.evaluate(()=>fixture.deferred[0].resolve({items:[{id:'old',title:'OLD ACCOUNT SECRET',contents:'private old',images:[]}],groups:[]}));
  await page.waitForTimeout(30);assert.ok(!(await page.locator('parro-card >> ha-card').innerText()).includes('OLD ACCOUNT SECRET'));
  await page.evaluate(()=>fixture.deferred[1].resolve({items:[{id:'new',title:'NEW ACCOUNT',contents:'new visible',images:[]}],groups:[]}));
  await page.waitForFunction(()=>card._data?.items[0]?.id==='new');assert.ok((await page.locator('parro-card >> ha-card').innerText()).includes('NEW ACCOUNT'));
 });
 await test('permission error clears content and revokes every photo URL',async()=>{
  await ready();await page.waitForFunction(()=>card._urls.size>=2);
  await page.evaluate(async()=>{fixture.state='unauthorized';await card._load(true);});
  assert.equal(await count('article'),0);assert.equal(await page.evaluate(()=>card._urls.size),0);assert.ok(await page.evaluate(()=>fixture.revoked.length>=2));
  assert.match(await page.locator('parro-card >> ha-card').innerText(),/Geen toegang/);
 });
 await test('no account, expired login, empty and connection error are genuine states',async()=>{
  for(const [state,label] of [['noaccount','Geen toegankelijk'],['choose','Kies een'],['authentication_expired','Opnieuw aanmelden'],['empty','Geen mededelingen'],['cannot_connect','niet bereikbaar']]){
   await ready('?state='+state);assert.equal(await count('article'),0);assert.ok((await page.locator('parro-card >> ha-card').innerText()).includes(label));
   assert.ok(!(await page.locator('parro-card >> ha-card').innerText()).includes('private raw error'));
  }
 });
 await test('hidden document stops polling, drops data, and refreshes on return',async()=>{
  await ready();await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'));});
  assert.equal(await count('article'),0);const calls=await page.evaluate(()=>fixture.calls.length);
  await page.evaluate(()=>card._load(true));assert.equal(await page.evaluate(()=>fixture.calls.length),calls);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForFunction(()=>card._data?.items?.length===3);
 });
 await test('photo display and message requests remain bounded',async()=>{
  await ready();await page.evaluate(async()=>{fixture.items=Array.from({length:40},(_,i)=>({id:String(i),title:'Bounded announcement '+i,contents:'Synthetic',images:Array.from({length:100},(_,j)=>({id:`p${i}-${j}`.padEnd(32,'x'),name:'Synthetic'}))}));card.setConfig({...card._config,limit:20});});
  await page.waitForFunction(()=>card._data?.items?.length===20);assert.equal(await count('article'),20);assert.equal(await count('.photo'),12);
  assert.ok(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='parro/feed').every(x=>x.limit<=20)));
 });
 await test('image access revoked clears the feed',async()=>{
  await page.goto(base+'?state=loading');await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.evaluate(()=>{fixture.imageStatus=403;fixture.deferred[0].resolve({items:fixture.items,groups:fixture.groups});});
  await page.waitForFunction(()=>card._error==='unauthorized');assert.equal(await count('article'),0);assert.equal(await page.evaluate(()=>card._urls.size),0);
  const requests=await page.evaluate(()=>fixture.calls.length);await page.evaluate(()=>{for(let i=0;i<20;i++)card.hass=makeHass();});
  assert.equal(await page.evaluate(()=>fixture.calls.length),requests);
 });
 await test('visual editor changes account/group/settings through HA event contract',async()=>{
  await ready('?editor=1');await page.waitForFunction(()=>editor._groups.length===2);
  const editor=page.locator('parro-card-editor');await editor.locator('select#group_id').selectOption('20');await page.waitForFunction(()=>card._data?.items.length===1);
  assert.equal(await page.evaluate(()=>fixture.lastConfig.group_id),'20');
  await editor.locator('input#title').fill('Mijn school');await editor.locator('input#title').blur();
  assert.equal(await page.locator('parro-card >> h2').innerText(),'Mijn school');
  await editor.locator('input#limit').fill('7');await editor.locator('input#limit').blur();assert.equal(await page.evaluate(()=>fixture.lastConfig.limit),7);
  await editor.locator('input[type=checkbox]').uncheck();await page.waitForFunction(()=>card._config.show_images===false);assert.equal(await count('.photo'),0);
 });
 await test('clearing editor account ignores pending old group names',async()=>{
  await ready('?editor=1');await page.waitForFunction(()=>editor._groups.length===2);
  await page.evaluate(()=>{fixture.state='loading';editor._loadGroups();});await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.locator('parro-card-editor >> #config_entry_id').selectOption('');
  await page.evaluate(()=>fixture.deferred[0].resolve({items:[],groups:[{id:'old',name:'OLD ACCOUNT GROUP'}]}));
  await page.waitForTimeout(20);assert.equal(await page.evaluate(()=>editor._groups.length),0);
  assert.ok(!(await page.locator('parro-card-editor >> .editor').innerText()).includes('OLD ACCOUNT GROUP'));
 });
 await test('image fetches deduplicate while message expansion rerenders',async()=>{
  await ready('?state=empty');
  await page.evaluate(()=>{window.pendingPhotos=[];card._hass.fetchWithAuth=(url)=>new Promise(resolve=>pendingPhotos.push({url,resolve}));fixture.state='ready';card._load(true);});
  await page.waitForFunction(()=>pendingPhotos.length>=2);const requests=await page.evaluate(()=>pendingPhotos.length);
  await page.locator('parro-card >> .toggle').first().click();await page.waitForTimeout(40);
  assert.equal(await page.evaluate(()=>pendingPhotos.length),requests);
 });
 await test('disconnect aborts ownership and releases memory',async()=>{
  await ready();await page.waitForFunction(()=>card._urls.size>=2);await page.evaluate(()=>card.remove());
  assert.equal(await page.evaluate(()=>card._data),null);assert.equal(await page.evaluate(()=>card._urls.size),0);
 });
 if(!process.env.PARRO_SKIP_SCREENSHOTS) {
 // One batched visual inspection: desktop/light + mobile/dark + editor + loading/error.
 const artifacts=new URL('./artifacts/',import.meta.url);await mkdir(artifacts,{recursive:true});
 for(const shot of [
  {name:'desktop-light',width:1100,height:1050,query:''},
  {name:'mobile-dark',width:390,height:1000,query:'?theme=dark'},
  {name:'editor',width:800,height:1500,query:'?editor=1'},
  {name:'loading',width:390,height:700,query:'?state=loading'},
  {name:'error',width:390,height:700,query:'?state=authentication_expired&lang=en'},
 ]) {
  await page.setViewportSize({width:shot.width,height:shot.height});await page.goto(base+shot.query);
  if(shot.name!=='loading')await page.waitForFunction(()=>card._started&&!card._loading);
  await page.waitForTimeout(100);await page.screenshot({path:new URL(shot.name+'.png',artifacts).pathname,fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`No horizontal overflow: ${shot.name}`);
 }
 }
 console.log(`${passed} functional checks passed.`);
} finally {await browser.close();}
