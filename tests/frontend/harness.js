import '../../custom_components/parro/frontend/parro-card.js';
// Native HA supplies these components. Minimal local mocks keep this harness offline.
const paths = {
  refresh: 'M17.65 6.35A7.95 7.95 0 0012 4a8 8 0 108 8h-2a6 6 0 11-1.76-4.24L13 11h7V4z',
  'chevron-down': 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z',
  'chevron-up': 'M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z',
  'image-outline': 'M21 19V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2zM5 5h14v14H5zm1 12h12l-4-5-3 4-2-3z',
  'clock-outline': 'M12 2a10 10 0 100 20 10 10 0 000-20zm0 18a8 8 0 110-16 8 8 0 010 16zm1-13h-2v6l5.2 3.1 1-1.7-4.2-2.5z',
  'school-outline': 'M12 3L1 9l4 2.18v6L12 21l7-3.82v-6L21 10v7h2V9zm6.82 6L12 12.72 5.18 9 12 5.28zM17 16l-5 2.72L7 16v-3.72l5 2.73 5-2.73z',
  'message-text-outline': 'M20 2H4a2 2 0 00-2 2v18l4-4h14a2 2 0 002-2V4a2 2 0 00-2-2zm0 14H5.17L4 17.17V4h16zM6 7h12v2H6zm0 4h9v2H6z',
  'lock-outline': 'M18 8h-1V6a5 5 0 00-10 0v2H6a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V10a2 2 0 00-2-2zM9 6a3 3 0 016 0v2H9zm9 14H6V10h12z',
};
customElements.define('ha-icon', class extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const root=this.attachShadow({mode:'open'});
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24'); svg.style.cssText='width:100%;height:100%;fill:currentColor';
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d',paths[this.getAttribute('icon')?.replace('mdi:','')] || paths['school-outline']);svg.append(path);root.append(svg);
  }
});
const params = new URLSearchParams(location.search);
document.documentElement.classList.toggle('dark', params.get('theme') === 'dark');
const imageBlob = () => new Promise((resolve) => {
  const canvas=document.createElement('canvas');canvas.width=800;canvas.height=600;
  const ctx=canvas.getContext('2d');ctx.fillStyle='#c8ddd5';ctx.fillRect(0,0,800,600);ctx.fillStyle='#91b8a8';ctx.fillRect(40,40,340,360);ctx.fillStyle='#e8d7a6';ctx.fillRect(420,180,340,360);ctx.fillStyle='#224c40';ctx.font='32px sans-serif';ctx.fillText('Synthetische testfoto',40,560);canvas.toBlob(resolve,'image/png');
});
const items = [
  {id:'m1',title:'Samen op ontdekking',contents:'Deze week ontdekken we wat er groeit in de schooltuin. We kijken naar de planten, tekenen wat we zien en bespreken hoe we de tuin kunnen verzorgen.\n\nOp vrijdag sluiten we het project samen af. De kinderen kunnen dan vertellen wat ze hebben ontdekt. Een jas die een beetje vies mag worden is handig.',created_at:'2026-09-08T08:30:00+02:00',group_id:'10',group_name:'Voorbeeldgroep A',sender:'Team voorbeeldschool',images:[{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',name:'Testfoto van het tuinproject'},{id:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',name:'Tweede synthetische testfoto'}]},
  {id:'m2',title:'Woensdag naar de bibliotheek',contents:'Woensdag gaan we met de groep naar de bibliotheek. We vertrekken na de ochtendkring en zijn voor de lunch weer terug. Neem de bibliotheekpas mee als je die hebt.',created_at:'2026-09-07T14:00:00+02:00',group_id:'10',group_name:'Voorbeeldgroep A',sender:'Team voorbeeldschool',images:[]},
  {id:'m3',title:'Een kijkje in de klas',contents:'De eerste schoolweek zit erop. We hebben kennisgemaakt, samen afspraken gemaakt en de hoeken in de klas ontdekt. Fijn om iedereen weer te zien!',created_at:'2026-09-04T14:00:00+02:00',group_id:'20',group_name:'Voorbeeldgroep B',sender:'Team voorbeeldschool',images:[{id:'cccccccccccccccccccccccccccccccc',name:'Derde synthetische testfoto'}]},
];
window.fixture = {
  items, calls:[], photoCalls:[], revoked:[], state:params.get('state')||'ready', deferred:[], userId:'synthetic-user', imageStatus:200,
  groups:[{id:'10',name:'Voorbeeldgroep A'},{id:'20',name:'Voorbeeldgroep B'}],
  accounts:[{config_entry_id:'example-account',title:'Voorbeeldschool'},{config_entry_id:'second-account',title:'Tweede voorbeeldaccount'}],
};
const originalRevoke=URL.revokeObjectURL.bind(URL);URL.revokeObjectURL=(url)=>{fixture.revoked.push(url);originalRevoke(url);};
window.makeHass = (userId=fixture.userId) => ({
  user:{id:userId},locale:{language:params.get('lang')||'nl'},
  async callWS(request) {
    fixture.calls.push({...request});
    if(request.type==='parro/feed' && (!Number.isInteger(request.limit) || request.limit<1 || request.limit>20 || (request.group_id && !/^[1-9][0-9]{0,19}$/.test(request.group_id)))) throw {code:'invalid_format'};
    if (request.type === 'parro/accounts') return {accounts:fixture.state==='noaccount'?[]:fixture.accounts};
    if (fixture.state === 'loading') return new Promise((resolve,reject)=>fixture.deferred.push({resolve,reject,request}));
    if (['unauthorized','not_loaded','cannot_connect','authentication_expired','unsupported_response'].includes(fixture.state)) throw {code:fixture.state,message:'Never show this private raw error'};
    const selected=fixture.state==='empty'?[]:fixture.items.filter(item=>!request.group_id || item.group_id===request.group_id).slice(0,request.limit);
    return {items:selected,groups:fixture.groups,returned:selected.length,limit:request.limit,updated_at:'2026-09-08T09:00:00+02:00',stale:fixture.state==='stale'};
  },
  async fetchWithAuth(url, options={}) {
    fixture.photoCalls.push(url);
    if(!/^\/api\/parro\/(example-account|second-account)\/image\/[A-Za-z0-9_-]{32}$/.test(url)) return new Response(null,{status:400});
    const blob=await imageBlob();
    if(options.signal?.aborted) throw new DOMException('Aborted','AbortError');
    return new Response(blob,{status:fixture.imageStatus,headers:{'Content-Type':'image/png'}});
  },
});
window.card=document.createElement('parro-card');
card.setConfig({type:'custom:parro-card',config_entry_id:params.get('state')==='choose'?'':'example-account',limit:5,show_images:true});
card.hass=makeHass();document.getElementById('mount').append(card);
if(params.has('editor')) {
  document.getElementById('editor').hidden=false;
  window.editor=document.createElement('parro-card-editor');editor.setConfig(card._config);editor.hass=makeHass();
  editor.addEventListener('config-changed',(event)=>{fixture.lastConfig=event.detail.config;card.setConfig(event.detail.config);});
  document.getElementById('editor').append(editor);
}
