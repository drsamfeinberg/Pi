/* Injected only after a user scans the clinic tab. No network, storage, or save clicks. */
if (!globalThis.__piDraftBridgeInstalled) {
  globalThis.__piDraftBridgeInstalled = true;
  let registry = new Map(), scannedURL = '', context = null;
  function allowed() { return location.protocol === 'https:' && location.hostname === 'chiroduo.janeapp.com' && (location.pathname === '/admin' || location.pathname.startsWith('/admin/')); }
  function visible(e) { const r=e.getBoundingClientRect(); const style=getComputedStyle(e); return r.width>0 && r.height>0 && style.visibility!=='hidden' && style.display!=='none'; }
  function safePage() { if(!allowed())throw new Error('Unsupported Jane page.');if([...document.querySelectorAll('input[type=password]')].some(visible))throw new Error('Log in through Jane before using the bridge.'); }
  function value(e) { return e.isContentEditable ? e.innerText : e.value; }
  function labelFor(e) {
    const aria=e.getAttribute('aria-label');if(aria)return aria.slice(0,120);
    const ids=(e.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean);
    if(ids.length)return ids.map(id=>document.getElementById(id)?.textContent||'').join(' ').trim().slice(0,120);
    if(e.labels?.length)return [...e.labels].map(l=>l.textContent.trim()).join(' / ').slice(0,120);
    return (e.getAttribute('placeholder') || e.getAttribute('name') || e.id || 'Unlabeled editor — verify location in Jane').slice(0,120);
  }
  function editors() {
    return [...document.querySelectorAll('textarea,input[type=text],input:not([type]),[contenteditable=true]')].filter(e=>visible(e) && !e.disabled && !e.readOnly && e.getAttribute('aria-disabled')!=='true' && !e.parentElement?.closest('[contenteditable=true]'));
  }
  function scan() {
    safePage();registry=new Map();scannedURL=location.href;context={title:document.title,anchors:[...document.querySelectorAll('h1,h2,[role=heading]')].filter(visible).map(e=>({element:e,text:e.textContent}))};
    return {fields:editors().slice(0,150).map((e,i)=>{const id=`pi-${i}-${crypto.randomUUID()}`;registry.set(id,{element:e,label:labelFor(e)});return{id,label:`${i+1}. ${labelFor(e)}`,empty:!value(e).trim()};})};
  }
  async function fill(assignments) {
    safePage();
    if(location.href!==scannedURL || !context || document.title!==context.title || context.anchors.some(a=>!a.element.isConnected || a.element.textContent!==a.text))throw new Error('Page context changed. Scan again before filling.');
    if(!Array.isArray(assignments) || !assignments.length || assignments.length>100)throw new Error('Invalid assignments.');
    const ids=assignments.map(a=>a.target);if(new Set(ids).size!==ids.length)throw new Error('A field cannot receive two sections.');
    // Validate all selected targets before starting. Some EHR editors still require a dedicated adapter.
    const targets=assignments.map(a=>{
      const saved=registry.get(a.target),e=saved?.element;
      if(!e || !e.isConnected || !visible(e) || e.disabled || e.readOnly || e.getAttribute('aria-disabled')==='true' || labelFor(e)!==saved.label)throw new Error('A mapped field changed. Scan again.');
      if(typeof a.text!=='string' || !a.text.trim() || a.text.length>30000)throw new Error('Invalid section text.');
      return{assignment:a,element:e};
    });
    const results=[];
    for(const {assignment:a,element:e} of targets){
      if(value(e).trim()){results.push({section:a.section,status:'skipped',detail:'Field contains existing text.'});continue;}
      try {
        e.focus();
        if(e.isContentEditable){
          const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(e);selection.removeAllRanges();selection.addRange(range);
          if(!document.execCommand('insertText',false,a.text))throw new Error('Rich-text editor needs a tested adapter.');
        }else{
          const prototype=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
          const setter=Object.getOwnPropertyDescriptor(prototype,'value').set;setter.call(e,a.text);
          e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));
        }
        await new Promise(resolve=>setTimeout(resolve,150));
        const normalized=s=>s.replace(/\r\n/g,'\n').trim();
        if(normalized(value(e))!==normalized(a.text))throw new Error('Editor did not retain matching text. Inspect it manually before saving.');
        results.push({section:a.section,status:'inserted',detail:'Visible text matched; Jane persistence still requires review and save.'});
      }catch(error){results.push({section:a.section,status:'needs attention',detail:error.message});break;}
    }
    if(results.length<targets.length)for(const {assignment:a} of targets.slice(results.length))results.push({section:a.section,status:'not attempted',detail:'Stopped after an editor error.'});
    return{results};
  }
  (globalThis.browser || globalThis.chrome).runtime.onMessage.addListener((message,_sender,respond)=>{
    if(!['pi-scan','pi-fill'].includes(message.action))return false;
    (async()=>{try{respond(message.action==='pi-scan'?scan():await fill(message.assignments));}catch(error){respond({error:error.message});}})();
    return true;
  });
}
