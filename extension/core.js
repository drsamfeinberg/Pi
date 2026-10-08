/* Template-fill demonstration: source text is data, never instructions or code. */
(function(root){
  const normalize=text=>text.normalize('NFKC').toLowerCase().replace(/[’']/g,'').replace(/[^a-z0-9]+/g,' ').trim();
  const aliases={
    soap_1:['Subjective','Patient-reported symptoms'],soap_2:['Objective','Examination findings'],soap_3:['Assessment','Assessment/Comments','Clinician assessment'],soap_4:['Plan','Treatment plan'],
    narrative_1:['Date of Initial Booking'],narrative_2:['Date of Last Booking'],narrative_3:['Total Treatment Number'],narrative_4:['Total Bill'],narrative_5:['Total Bill Paid'],narrative_6:['Total Outstanding'],narrative_7:['Reason for Discharge'],narrative_8:['Accident history','Statement of Injury Mechanism Details'],narrative_9:['Prior history','Statement of Pre-Existing Conditions'],narrative_10:['Other relevant history','Any other Relevant History Details'],narrative_11:['Diagnoses','List of ICD-10 Codes'],narrative_12:['Injury overview','Overview for each injury area'],narrative_13:['Diagnostic testing','Statement of Diagnostic Testing Procedures'],narrative_14:['Referrals'],narrative_15:['Regional prognosis'],narrative_16:['Daily function'],narrative_17:['Activity limitations'],narrative_18:['Permanent impairment'],narrative_19:['Disability'],narrative_20:['Prognosis and Recommendations'],narrative_21:['Future care'],narrative_22:['Closing Statement'],
    dud_loe_1:['Work responsibilities','Job and Responsibilities'],dud_loe_2:['Work limitations','Impact of Injuries on Job Duties'],dud_loe_3:['Since the collision'],dud_loe_4:['Work attendance','Forced to Stop Working / Reduced Work Capacity'],dud_loe_5:['Pain during work','Increased Pain and Discomfort During Tasks'],dud_loe_6:['Job security','Impact on Job Security and Career Progression'],dud_loe_7:['Income effects','Financial and Emotional Strain Due to Reduced Income'],dud_loe_8:['Work pain management','Increased Dependence on Pain Management for Work'],dud_loe_9:['DUD summary','Summary'],dud_loe_10:['Post Motor Vehicle Accident Repercussions'],dud_loe_11:['Work Activity Difficulty/Limitation'],dud_loe_12:['Domestic limitations','Domestic Activity Difficulty/Limitation'],dud_loe_13:['Household limitations','Household Activity Difficulty/Limitation'],dud_loe_14:['Sports limitations','Sport/Activity Difficulty/Limitation'],dud_loe_15:['Hobbies limitations'],
    physician_1:['Accident history'],physician_2:['Initial Outcome Assessments'],physician_9:['Prior treatment'],physician_10:['Causation opinion'],physician_12:['Work limitations'],physician_15:['Prognosis'],physician_16:['Examination findings'],physician_17:['Treatment plan'],physician_18:['Medical necessity'],physician_19:['Goals of care'],physician_20:['Treatment details'],
    imaging_1:['Diagnostic testing'],cover_1:['Recipient'],cover_2:['Purpose of correspondence'],cover_3:['Documents included for review'],cover_4:['Contact and closing']
  };
  function headingMap(templates){
    const map=new Map();
    for(const template of templates)for(const field of template.fields){
      for(const label of [field.label,...(aliases[field.id]||[])]){
        const key=normalize(label);if(!map.has(key))map.set(key,[]);if(!map.get(key).includes(field.id))map.get(key).push(field.id);
      }
    }
    return map;
  }
  function extract(source,templates){
    const headings=headingMap(templates),results=[];
    for(const [pageIndex,page] of source.pages.entries()){
      const lines=page.split(/\r?\n/);let current=null;
      function finish(){if(current && current.body.some(s=>s.trim())){const quote=current.body.join('\n').trim();results.push({ids:current.ids,text:quote,citation:{source_id:source.id,source_name:source.name,page:pageIndex+1,line:current.line,quote}});}current=null;}
      for(let i=0;i<lines.length;i++){
        const line=lines[i].trim(),colon=line.indexOf(':');
        const whole=headings.get(normalize(line.replace(/:$/,'')));
        const prefix=colon>=0 ? headings.get(normalize(line.slice(0,colon))) : null;
        if(whole || prefix){finish();current={ids:whole||prefix,line:i+1,body:prefix && !whole ? [line.slice(colon+1).trim()] : []};continue;}
        if(current){if(!line && current.body.some(s=>s.trim()))finish();else current.body.push(lines[i]);}
      }
      finish();
    }
    return results;
  }
  function assemble(sources,templates){
    const all=sources.flatMap(source=>extract(source,templates)),reports={};
    for(const template of templates){
      const fields={};
      for(const field of template.fields){
        const matches=all.filter(item=>item.ids.includes(field.id));
        const groups=new Map();
        for(const match of matches){const key=match.text.replace(/\s+/g,' ').trim();if(!groups.has(key))groups.set(key,{text:match.text,citations:[]});groups.get(key).citations.push(match.citation);}
        const candidates=[...groups.values()];
        fields[field.id]={text:candidates.length===1?candidates[0].text:'',citations:candidates.length===1?candidates[0].citations:[],candidates,conflict:candidates.length>1,edited:false,resolved:false};
      }
      reports[template.id]={template_id:template.id,status:'draft',fields};
    }
    return reports;
  }
  function stats(report){const values=Object.values(report.fields);return{filled:values.filter(v=>v.text.trim()).length,total:values.length,conflicts:values.filter(v=>v.conflict&&!v.resolved).length};}
  function review(report,confirmed){if(!confirmed)throw new Error('Confirm that you reviewed the report and its sources.');const s=stats(report);if(s.filled!==s.total)throw new Error('Complete missing fields or explain why they are not applicable.');if(s.conflicts)throw new Error('Resolve each conflicting source before marking the report reviewed.');return{...structuredClone(report),status:'reviewed_unsigned',reviewed_at:new Date().toISOString()};}
  function escape(text){return String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function exportHTML(template,report,label,references=true){
    const sections=template.fields.map(field=>{const value=report.fields[field.id];return`<section><h2>${escape(field.label)}</h2><p>${escape(value.text||'[MISSING — clinician completion required]').replace(/\n/g,'<br>')}</p>${value.conflict&&!value.resolved?'<p class="flag">UNRESOLVED SOURCE CONFLICT</p>':''}${references?value.citations.map(c=>`<blockquote>${escape(c.source_name)} · page ${c.page}, line ${c.line}<br>${escape(c.quote).replace(/\n/g,'<br>')}</blockquote>`).join(''):''}</section>`;}).join('');
    return`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(template.title)}</title><style>body{max-width:850px;margin:32px auto;padding:0 20px;font:16px/1.6 system-ui;color:#17352e}h2{font-size:18px}section{border-top:1px solid #ddd;padding:12px 0}blockquote{font-size:12px;color:#53626b;white-space:pre-wrap}.flag{font-weight:bold;color:#8a462b}@media print{body{margin:0}h2{break-after:avoid}}</style><body><p class="flag">${report.status==='reviewed_unsigned'?'Reviewed locally · unsigned':'DRAFT · review required'}</p><h1>${escape(template.title)}</h1><p>Case: ${escape(label||'Not specified')}</p>${sections}<footer>Proof of concept. No signature or authenticated attestation.</footer></body></html>`;
  }
  const api={normalize,extract,assemble,stats,review,exportHTML};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PiDemoCore=api;
})(globalThis);
