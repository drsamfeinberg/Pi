/* Pure validation shared by popup and tests. Imported reports are data, never code. */
(function (root) {
  function parseReport(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid report file.');
    if (typeof value.case_label !== 'string' || !value.case_label.trim()) throw new Error('Report has no case label.');
    const report = value.report;
    if (!report || report.status !== 'reviewed_unsigned') throw new Error('Use a report marked reviewed in Pi, then export its JSON file.');
    if (typeof report.template_id !== 'string' || !report.fields || typeof report.fields !== 'object' || Array.isArray(report.fields)) throw new Error('Invalid report fields.');
    const sections = Object.entries(report.fields).map(([id, field]) => {
      if (!/^[a-z0-9_]+$/.test(id) || !field || typeof field.text !== 'string' || !field.text.trim() || field.text.length > 30000) throw new Error('Report contains an invalid or empty section.');
      return {id, text:field.text};
    });
    if (!sections.length || sections.length > 100) throw new Error('Report section count is invalid.');
    return {caseLabel:value.case_label, encounter:typeof value.encounter === 'string' ? value.encounter : '', templateId:report.template_id, sections};
  }
  function validateMapping(sections, mapping) {
    const selected = sections.filter(s => mapping[s.id]);
    if (!selected.length) throw new Error('Map at least one report section to a Jane field.');
    const targets = selected.map(s => mapping[s.id]);
    if (new Set(targets).size !== targets.length) throw new Error('Each Jane field can receive only one section in this version.');
    return selected.map(s => ({section:s.id,target:mapping[s.id],text:s.text}));
  }
  function isJaneURL(raw) {
    try { const url = new URL(raw); return url.protocol === 'https:' && url.hostname === 'chiroduo.janeapp.com' && (url.pathname === '/admin' || url.pathname.startsWith('/admin/')); } catch (_) { return false; }
  }
  const api = {parseReport,validateMapping,isJaneURL};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PiBridge = api;
})(globalThis);
