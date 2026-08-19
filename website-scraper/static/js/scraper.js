let activePreset = 'universal';
let fieldCounter = 0;
const loadedConfigurationId = window.initialConfiguration?.id || null;

const presetDefinitions = {
  universal: {container:'', pagination:{mode:'auto'}, fields:[]},
  books: {url:'https://books.toscrape.com/', container:'article.product_pod', pagination:{mode:'next',next_selector:'li.next a'}, fields:[
    {field_name:'Title',selector:'h3 a',extraction_type:'attribute',attribute_name:'title'},
    {field_name:'Price',selector:'.price_color',extraction_type:'text'},
    {field_name:'Availability',selector:'.availability',extraction_type:'text'},
    {field_name:'Rating',selector:'.star-rating',extraction_type:'attribute',attribute_name:'class'},
    {field_name:'Product URL',selector:'h3 a',extraction_type:'link',attribute_name:'href'}]},
  product:{container:'.product-card',pagination:{mode:'none'},fields:[
    {field_name:'Product Name',selector:'.product-title',extraction_type:'text'},
    {field_name:'Price',selector:'.price',extraction_type:'text'},
    {field_name:'Product URL',selector:'a',extraction_type:'link',attribute_name:'href'},
    {field_name:'Image',selector:'img',extraction_type:'image',attribute_name:'src'}]},
  article:{container:'article',pagination:{mode:'none'},fields:[
    {field_name:'Title',selector:'h2, h3',extraction_type:'text'},
    {field_name:'Summary',selector:'p',extraction_type:'text'},
    {field_name:'Article URL',selector:'a',extraction_type:'link',attribute_name:'href'}]},
  links:{container:'a[href]',pagination:{mode:'none'},fields:[
    {field_name:'Link Text',selector:'a, :scope',extraction_type:'text'},
    {field_name:'URL',selector:'a, :scope',extraction_type:'link',attribute_name:'href'}]},
  images:{container:'img[src]',pagination:{mode:'none'},fields:[
    {field_name:'Alt Text',selector:'img, :scope',extraction_type:'attribute',attribute_name:'alt'},
    {field_name:'Image URL',selector:'img, :scope',extraction_type:'image',attribute_name:'src'}]},
  headings:{container:'h1, h2, h3',pagination:{mode:'none'},fields:[
    {field_name:'Heading',selector:'h1, h2, h3, :scope',extraction_type:'text'}]},
  contact:{container:'',pagination:{mode:'none'},fields:[]},
  custom:{container:'',pagination:{mode:'none'},fields:[{field_name:'Title',selector:'h1',extraction_type:'text'}]}
};

function fieldRow(field={}) {
  fieldCounter++;
  const id = fieldCounter;
  return `<div class="field-row" data-field-id="${id}">
    <div><label>Field name</label><input class="form-control field-name" value="${escapeHtml(field.field_name||'')}" placeholder="Price"></div>
    <div><label>CSS selector</label><input class="form-control field-selector font-monospace" value="${escapeHtml(field.selector||'')}" placeholder=".price"></div>
    <div><label>Extraction</label><select class="form-select field-type"><option value="text">Text</option><option value="attribute">Attribute</option><option value="link">Link</option><option value="image">Image</option><option value="html">HTML</option></select></div>
    <div><label>Attribute name</label><input class="form-control field-attribute font-monospace" value="${escapeHtml(field.attribute_name||'')}" placeholder="href"></div>
    <button type="button" class="btn btn-light text-danger remove-field" title="Remove"><i class="bi bi-trash"></i></button>
  </div>`;
}

function addField(field={}) {
  $('#fieldsContainer').insertAdjacentHTML('beforeend', fieldRow(field));
  const row = $('#fieldsContainer .field-row:last-child');
  $('.field-type', row).value = field.extraction_type || 'text';
  $('.remove-field', row).addEventListener('click', () => row.remove());
  $('.field-type', row).addEventListener('change', updateAttributeState);
  updateAttributeState({target:$('.field-type', row)});
}

function updateAttributeState(event) {
  const row = event.target.closest('.field-row');
  const attribute = $('.field-attribute', row);
  const type = event.target.value;
  attribute.disabled = !['attribute','link','image'].includes(type);
  if (type === 'link' && !attribute.value) attribute.value = 'href';
  if (type === 'image' && !attribute.value) attribute.value = 'src';
}

function toggleExtractionUI() {
  const automatic = ['universal', 'contact'].includes(activePreset);
  $('#autoExtractionCard').classList.toggle('d-none', !automatic);
  $('#manualExtractionCard').classList.toggle('d-none', automatic);
}

function applyPreset(name) {
  activePreset = name;
  $$('#presetGrid button').forEach(btn => btn.classList.toggle('active', btn.dataset.preset===name));
  const preset = presetDefinitions[name];
  if (preset.url) $('#websiteUrl').value = preset.url;
  $('#containerSelector').value = preset.container || '';
  $('#fieldsContainer').innerHTML='';
  (preset.fields || []).forEach(addField);
  const pagination = preset.pagination || {mode:name === 'universal' ? 'auto' : 'none'};
  $('#paginationMode').value = pagination.mode;
  renderPaginationOptions(pagination);
  toggleExtractionUI();
}

function renderPaginationOptions(values={}) {
  const mode=$('#paginationMode').value;
  let html='';
  if (mode==='auto') html='<div class="form-text pt-4">The scraper follows a visible rel=next, Next, › or » link automatically.</div>';
  if (mode==='next') html='<label class="form-label">Next button selector</label><input class="form-control font-monospace" id="nextSelector" placeholder="li.next a">';
  if (mode==='url') html='<div class="row g-2"><div class="col-8"><label class="form-label">URL pattern</label><input class="form-control font-monospace" id="urlPattern" placeholder="https://site.com/page={page}"></div><div class="col-4"><label class="form-label">Start page</label><input type="number" class="form-control" id="startPage" value="1" min="1"></div></div>';
  if (mode==='load_more') html='<div class="row g-2"><div class="col-8"><label class="form-label">Load More selector</label><input class="form-control font-monospace" id="loadMoreSelector" placeholder="button.load-more"></div><div class="col-4"><label class="form-label">Max clicks</label><input type="number" class="form-control" id="maxClicks" value="10" min="1" max="30"></div></div>';
  if (mode==='infinite') html='<label class="form-label">Maximum scrolls</label><input type="number" class="form-control" id="maxScrolls" value="10" min="1" max="30">';
  $('#paginationOptions').innerHTML=html;
  if (values.next_selector && $('#nextSelector')) $('#nextSelector').value=values.next_selector;
  if (values.url_pattern && $('#urlPattern')) $('#urlPattern').value=values.url_pattern;
  if (values.start_page && $('#startPage')) $('#startPage').value=values.start_page;
  if (values.load_more_selector && $('#loadMoreSelector')) $('#loadMoreSelector').value=values.load_more_selector;
  if (values.max_clicks && $('#maxClicks')) $('#maxClicks').value=values.max_clicks;
  if (values.max_scrolls && $('#maxScrolls')) $('#maxScrolls').value=values.max_scrolls;
}

function defaultJobName(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    return `Auto scrape - ${host}`;
  } catch (_) {
    return 'Universal website scrape';
  }
}

function collectPayload() {
  const fields = $$('.field-row').map(row => ({
    field_name:$('.field-name',row).value.trim(),
    selector:$('.field-selector',row).value.trim(),
    extraction_type:$('.field-type',row).value,
    attribute_name:$('.field-attribute',row).value.trim()
  })).filter(field=>field.field_name);
  const mode=$('#paginationMode').value;
  const pagination={mode};
  if(mode==='next') pagination.next_selector=$('#nextSelector')?.value.trim();
  if(mode==='url') {pagination.url_pattern=$('#urlPattern')?.value.trim();pagination.start_page=Number($('#startPage')?.value||1);}
  if(mode==='load_more') {pagination.load_more_selector=$('#loadMoreSelector')?.value.trim();pagination.max_clicks=Number($('#maxClicks')?.value||10);}
  if(mode==='infinite') pagination.max_scrolls=Number($('#maxScrolls')?.value||10);
  const websiteUrl=$('#websiteUrl').value.trim();
  return {
    job_name:$('#jobName').value.trim() || defaultJobName(websiteUrl),
    website_url:websiteUrl,
    scraping_mode:$('#scrapingMode').value,
    preset:activePreset,
    container_selector:$('#containerSelector').value.trim(),
    fields,
    pagination,
    full_site: $('#fullSite')?.checked || false,
    settings:{
      max_pages:Number($('#maxPages').value),
      request_delay:Number($('#requestDelay').value),
      request_timeout:Number($('#requestTimeout').value),
      browser_timeout:60000,
      headless:$('#headless').checked
    }
  };
}

function validatePayload(payload) {
  if(!payload.website_url) throw new Error('Website URL is required.');
  if(!$('#responsibleCheck').checked) throw new Error('Confirm that you have permission to scrape this public page.');
  if(!['universal','contact'].includes(payload.preset) && !payload.fields.length) throw new Error('Add at least one extraction field or choose Universal Auto.');
}

function renderPreview(data) {
  const confidence=Math.round((data.confidence||0)*100);
  $('#previewMeta').textContent=`${data.record_count} record(s) · ${data.mode_used} mode · ${data.dataset_type || 'dataset'} · confidence ${confidence}%`;
  $('#previewWarnings').innerHTML=(data.warnings||[]).map(w=>`<div class="alert alert-warning py-2">${escapeHtml(w)}</div>`).join('');
  if(!data.records.length){$('#previewTable').innerHTML='<div class="empty-state"><p>No public records found. Try Dynamic mode or Custom selectors.</p></div>';return;}
  const columns=[...new Set(data.records.flatMap(Object.keys))];
  $('#previewTable').innerHTML=`<table class="table data-table"><thead><tr>${columns.map(c=>`<th>${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>${data.records.map(r=>`<tr>${columns.map(c=>`<td>${escapeHtml(r[c]??'Not Available')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function loadConfiguration(config) {
  activePreset=config.preset || 'universal';
  $$('#presetGrid button').forEach(btn => btn.classList.toggle('active', btn.dataset.preset===activePreset));
  $('#jobName').value=config.configuration_name || '';
  $('#websiteUrl').value=config.website_url || '';
  $('#scrapingMode').value=config.scraping_mode || 'auto';
  $('#containerSelector').value=config.container_selector || '';
  const settings=config.settings||{};
  $('#maxPages').value=settings.max_pages||3;
  $('#requestDelay').value=settings.request_delay||1;
  $('#requestTimeout').value=settings.request_timeout||20;
  $('#headless').checked=settings.headless??true;
  if($('#fullSite')) $('#fullSite').checked=config.full_site??true;
  $('#fieldsContainer').innerHTML='';
  (config.fields||[]).forEach(addField);
  const pagination=config.pagination||{mode:activePreset==='universal'?'auto':'none'};
  $('#paginationMode').value=pagination.mode||'none';
  renderPaginationOptions(pagination);
  toggleExtractionUI();
}

$('#addFieldBtn').addEventListener('click',()=>addField());
$('#paginationMode').addEventListener('change',()=>renderPaginationOptions());
$$('#presetGrid button').forEach(btn=>btn.addEventListener('click',()=>applyPreset(btn.dataset.preset)));

$('#previewBtn').addEventListener('click',async()=>{
  try {
    const payload=collectPayload();
    validatePayload(payload);
    const btn=$('#previewBtn');
    btn.disabled=true;
    btn.innerHTML='<span class="spinner-border spinner-border-sm"></span> Detecting data';
    const data=await api('/api/preview',{method:'POST',body:JSON.stringify(payload)});
    renderPreview(data);
    new bootstrap.Modal('#previewModal').show();
  } catch(e) {showToast(e.message,'error');}
  finally {$('#previewBtn').disabled=false;$('#previewBtn').innerHTML='<i class="bi bi-eye"></i>Preview first 10';}
});

$('#robotsBtn').addEventListener('click',async()=>{
  try {
    const data=await api('/api/robots',{method:'POST',body:JSON.stringify({website_url:$('#websiteUrl').value})});
    const r=data.result;
    $('#robotsResult').innerHTML=`<span class="${r.allowed===false?'text-danger':'text-success'}">${escapeHtml(r.message)}${r.allowed===null?'':` · Allowed: ${r.allowed?'Yes':'No'}`}${r.crawl_delay?` · Crawl delay: ${r.crawl_delay}s`:''}</span>`;
  } catch(e) {showToast(e.message,'error');}
});

$('#saveConfigBtn').addEventListener('click',async()=>{
  try {
    const payload=collectPayload();
    if(!payload.website_url) throw new Error('Enter a URL first.');
    payload.configuration_name=prompt('Configuration name:',window.initialConfiguration?.configuration_name||payload.job_name);
    if(!payload.configuration_name) return;
    const url=loadedConfigurationId?`/api/configurations/${loadedConfigurationId}`:'/api/configurations';
    const method=loadedConfigurationId?'PUT':'POST';
    await api(url,{method,body:JSON.stringify(payload)});
    showToast(loadedConfigurationId?'Configuration updated.':'Configuration saved.');
  } catch(e) {showToast(e.message,'error');}
});

$('#scraperForm').addEventListener('submit',async e=>{
  e.preventDefault();
  try {
    const payload=collectPayload();
    validatePayload(payload);
    const data=await api('/api/scrape',{method:'POST',body:JSON.stringify(payload)});
    location.href=`/results/${data.job_id}`;
  } catch(err) {showToast(err.message,'error');}
});

renderPaginationOptions();
const localSettings=JSON.parse(localStorage.getItem('scrapeFlowSettings')||'{}');
if(localSettings.maxPages) $('#maxPages').value=localSettings.maxPages;
if(localSettings.delay) $('#requestDelay').value=localSettings.delay;
if(localSettings.headless!==undefined) $('#headless').checked=localSettings.headless;
if(window.initialConfiguration) loadConfiguration(window.initialConfiguration); else applyPreset('universal');
