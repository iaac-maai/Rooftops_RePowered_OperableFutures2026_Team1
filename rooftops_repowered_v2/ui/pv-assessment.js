/* Existing-PV evidence and official PVGIS sensitivity. Never actual plant generation. */
(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const node=(tag,text,className)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;};
  const number=(value,digits=2)=>Number.isFinite(value)?value.toLocaleString('en-GB',{maximumFractionDigits:digits,minimumFractionDigits:digits}):'Unknown';
  const solarCache=new Map();
  let dataset=null, callbacks=null, comparisonScenario='base', requestId=0;
  const dayFormatter=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'});
  const hourFormatter=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Madrid',hour:'2-digit',minute:'2-digit',timeZoneName:'short'});
  function download(name,payload) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function addRow(dl,label,value) {
    const row=node('div',undefined,'data-row');row.append(node('dt',label),node('dd',value));dl.append(row);
  }
  function compare() {
    const panel=byId('existing-pv-comparison');
    if(!panel||!dataset.existing_pv?.comparisons)return;
    const data=dataset.existing_pv, row=data.comparisons.find(row=>row.scenario===comparisonScenario);
    panel.querySelectorAll('[data-compare-scenario]').forEach(button=>{button.classList.toggle('selected',button.dataset.compareScenario===comparisonScenario);button.setAttribute('aria-pressed',String(button.dataset.compareScenario===comparisonScenario));});
    byId('comparison-summary').textContent=`${comparisonScenario}: predicted projected panel area ${number(row.predicted_projected_area_m2)} m² versus image reference ${number(row.observed_projected_area_m2)} m² (${row.area_difference_percent>=0?'+':''}${number(row.area_difference_percent,1)}%). Spatial IoU ${number(row.spatial_iou,3)}. This is placement agreement, not a maximum-capacity validation.`;
    const range=Object.values(data.observed.threshold_sensitivity_m2);
    const max=Math.max(row.predicted_projected_area_m2,...range)*1.12;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 720 180');svg.setAttribute('role','img');
    svg.setAttribute('aria-label',`Projected panel-area comparison. Observed ${number(row.observed_projected_area_m2)} square metres; predicted ${number(row.predicted_projected_area_m2)} square metres. Image threshold range is not a confidence interval.`);
    const scale=value=>value/max*460;
    function rect(x,y,w,h,color,opacity=1){const e=document.createElementNS(svg.namespaceURI,'rect');Object.entries({x,y,width:w,height:h,fill:color,opacity}).forEach(([key,value])=>e.setAttribute(key,value));svg.append(e);}
    function label(x,y,text){const e=document.createElementNS(svg.namespaceURI,'text');Object.entries({x,y,fill:'#31503e','font-size':15}).forEach(([key,value])=>e.setAttribute(key,value));e.textContent=text;svg.append(e);}
    label(12,35,'Image reference');rect(180,16,scale(row.observed_projected_area_m2),30,'#b78b32');
    rect(180+scale(Math.min(...range)),11,scale(Math.max(...range)-Math.min(...range)),40,'#b78b32',.23);
    label(12,100,'Predicted layout');rect(180,80,scale(row.predicted_projected_area_m2),30,'#4a86a6');
    label(180,150,'Projected panel area (m²) · threshold band, not confidence');
    byId('comparison-plot').replaceChildren(svg);
  }
  function renderExisting() {
    const existing=dataset.existing_pv;
    if(!existing?.comparisons)return;
    const overview=node('section',undefined,'card card-pad existing-pv-card');overview.id='existing-pv-dossier';
    const heading=node('div',undefined,'section-head');heading.append(node('h2','Existing A160 PV — what is established'),node('span','Installation details unknown','tag pending'));overview.append(heading);
    const grid=node('div',undefined,'three-col');
    for(const [label,value,detail] of [
      ['PV identity','Visually confirmed',`Final orthophoto captured ${existing.observed.capture_date}`],
      ['Image-interpreted panel coverage',`${number(existing.observed.projected_panel_coverage_m2)} m²`,'Projected image reference, not installed capacity'],
      ['Installed capacity / module count','Unknown','Module Wp, actual tilt/orientation and inverter configuration also unknown']]) {
      const card=node('div');card.append(node('span',label,'label'),node('div',value,'headline-num'),node('p',detail,'muted'));grid.append(card);
    }
    overview.append(grid);
    overview.append(node('p','No owner-provided as-built or installation specification is available. Neither the V1 capacity range nor the 2015 municipal estimate is substituted for the actual installation.','note-box'));
    const compareButton=node('button','Compare observed coverage with our roof assessment','mini-btn');compareButton.type='button';compareButton.addEventListener('click',()=>{callbacks.openView('roof');byId('existing-pv-comparison').scrollIntoView({block:'start',behavior:'smooth'});});overview.append(compareButton);
    byId('view-solar').querySelector('.intro').after(overview);
    const panel=node('section',undefined,'card card-pad existing-pv-card');panel.id='existing-pv-comparison';
    panel.append(node('h2','Existing installation reference vs hypothetical roof layout'));
    panel.append(node('p','Compare horizontal panel-covered area and spatial overlap. Observed count and installed kWp are unknown, so capacity error cannot be calculated.','muted'));
    const buttons=node('div',undefined,'scenario-select');
    for(const scenario of ['conservative','base','optimistic']) {
      const button=node('button',scenario[0].toUpperCase()+scenario.slice(1),'scenario-btn');button.type='button';button.dataset.compareScenario=scenario;
      button.addEventListener('click',()=>callbacks.selectRoof(scenario));buttons.append(button);
    }
    panel.append(buttons);
    const plot=node('div');plot.id='comparison-plot';panel.append(plot);
    const summary=node('p',undefined,'muted');summary.id='comparison-summary';panel.append(summary);
    const wrapper=node('div',undefined,'table-scroll');
    const table=node('table',undefined,'data-table comparison-table');
    const caption=node('caption','Projected image reference vs predictions; all capacities are hypothetical.');table.append(caption);
    const head=node('thead');const header=node('tr');
    ['Scenario','Reference area (m²)','Predicted area (m²)','Area difference','IoU','Hypothetical capacity'].forEach(value=>header.append(node('th',value)));head.append(header);table.append(head);
    const body=node('tbody');
    existing.comparisons.forEach(row=>{const tr=node('tr');[row.scenario,number(row.observed_projected_area_m2),number(row.predicted_projected_area_m2),`${row.area_difference_percent>=0?'+':''}${number(row.area_difference_percent,1)}%`,number(row.spatial_iou,3),`${number(row.hypothetical_capacity_kwp)} kWp`].forEach(value=>tr.append(node('td',value)));body.append(tr);});table.append(body);wrapper.append(table);panel.append(wrapper);
    panel.append(node('p','The reference area changes with pixel thresholds and is not a counted installation. LiDAR already includes the PV, limiting pre-installation independence. A different installed layout does not establish a certified maximum.','note-box'));
    const explore=node('button','Explore these capacities as hypothetical PVGIS cases','mini-btn');explore.type='button';explore.addEventListener('click',()=>{callbacks.openView('solar');const select=byId('pvgis-case');if(select){select.value=`retrospective_${comparisonScenario}`;loadSolar();}});panel.append(explore);
    byId('view-roof').append(panel);compare();
  }
  function paintSolar(hourly,record) {
    const target=byId('pvgis-chart');const day=byId('pvgis-day').value;
    const rows=hourly.hourly.filter(row=>dayFormatter.format(new Date(row.timestamp_utc))===day);
    if(!rows.length){target.replaceChildren(node('p','No samples for that local date. Select a date inside the source year.'));return;}
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 720 260');svg.setAttribute('role','img');svg.setAttribute('aria-label',`Hypothetical PVGIS ${record.scenario_id}, ${day}, ${rows.length} source intervals in Europe/Madrid. Modeled energy, not observed generation.`);
    const left=65,right=690,top=25,bottom=205;
    const times=rows.map(row=>new Date(row.timestamp_utc).getTime()),start=times[0],span=times[times.length-1]-start||1;
    const peak=Math.max(...rows.map(row=>row.pv_generation_kwh),.01)*1.12;
    const font=Math.max(12,12*720/Math.max(target.clientWidth,300));
    function add(tag,attrs,text){const e=document.createElementNS(svg.namespaceURI,tag);Object.entries(attrs).forEach(([key,value])=>e.setAttribute(key,value));if(text!==undefined)e.textContent=text;svg.append(e);return e;}
    for(let i=0;i<=4;i++) {const y=bottom-i/4*(bottom-top);add('line',{x1:left,y1:y,x2:right,y2:y,stroke:'#dce6dc'});add('text',{x:55,y:y+4,'text-anchor':'end','font-size':font,fill:'#405c4d'},number(peak*i/4,1));}
    const points=rows.map((row,i)=>[left+(times[i]-start)/span*(right-left),bottom-row.pv_generation_kwh/peak*(bottom-top)]);
    add('path',{d:points.map((point,i)=>(i?'L':'M')+point.join(' ')).join(' '),fill:'none',stroke:'#4a86a6','stroke-width':3});
    for(let i=0;i<=4;i++){const index=Math.round(i*(rows.length-1)/4);add('text',{x:points[index][0],y:235,'text-anchor':'middle','font-size':font,fill:'#405c4d'},hourFormatter.format(new Date(rows[index].timestamp_utc)));}
    target.replaceChildren(svg);
    byId('pvgis-day-summary').textContent=`${rows.length} source intervals on this Europe/Madrid date · ${number(rows.reduce((sum,row)=>sum+row.pv_generation_kwh,0))} modeled kWh · UTC instants and original minute offsets preserved.`;
  }
  async function loadSolar() {
    const select=byId('pvgis-case');if(!select)return;
    const id=select.value, record=dataset.pvgis.hypothetical_scenarios.find(row=>row.scenario_id===id),sequence=++requestId;
    if(!record)return;
    const meta=byId('pvgis-run-details');meta.replaceChildren();
    addRow(meta,'Hypothetical capacity',`${number(record.capacity_kwp)} kWp — not installed capacity`);
    addRow(meta,'Modeled annual generation',record.status==='available'?`${number(record.annual_generation_kwh,0)} kWh`:'Not simulated / unavailable');
    addRow(meta,'Weather / system losses',`${record.weather_year} SARAH3 · ${record.loss_percent}% assumed`);
    addRow(meta,'Assumed layout',`${record.tilt}° tilt · ${number(record.azimuth,2)}° PVGIS south-zero aspect`);
    addRow(meta,'Model / samples',`${record.model_version} · ${record.rows??0} hourly intervals`);
    addRow(meta,'Source acquisition',record.acquisition_mode==='MANUAL_PVGIS_EXPORT'?'Manual PVGIS CSV; settings declared by user':record.acquisition_mode==='OFFICIAL_PVGIS_API'?'Official API response, cached with source hash':'Not acquired');
    addRow(meta,'Case-study sharing readiness','Not eligible — actual PV and independent demands remain unverified');
    const day=byId('pvgis-day');
    day.min=record.first_timestamp_utc?dayFormatter.format(new Date(record.first_timestamp_utc)):`${record.weather_year}-01-01`;
    day.max=record.last_timestamp_utc?dayFormatter.format(new Date(record.last_timestamp_utc)):`${record.weather_year}-12-31`;
    if(!day.value||day.value<day.min||day.value>day.max)day.value=`${record.weather_year}-06-21`;
    byId('download-pvgis-settings').onclick=()=>download(`A160_${id}_hypothetical_pvgis.json`,{document_type:'HYPOTHETICAL_PVGIS_SCENARIO',...record,actual_installed_capacity_kwp:null,existing_installed_capacity_verified:false,energy_sharing_eligible:false,timestamp_basis:'UTC',power_unit:'W',assumptions:dataset.pvgis.assumptions,provenance:dataset.pvgis.provenance});
    if(record.status!=='available'){byId('pvgis-chart').replaceChildren(node('p',record.status==='not_applicable_zero_capacity'?'Zero hypothetical capacity: no PVGIS simulation is run.':record.error||'API output unavailable. Use the documented manual CSV fallback.'));byId('pvgis-day-summary').textContent='No hourly values are substituted.';return;}
    byId('pvgis-chart').replaceChildren(node('p','Loading official modeled hourly records…'));
    try {
      let hourly=solarCache.get(id);
      if(!hourly){const response=await fetch(`/api/pvgis/hypothetical/hourly?scenario=${encodeURIComponent(id)}`);if(!response.ok)throw new Error();hourly=await response.json();if(hourly.state!=='available')throw new Error();solarCache.set(id,hourly);}
      if(sequence!==requestId)return;
      paintSolar(hourly,record);day.onchange=()=>paintSolar(hourly,record);
    } catch(_){if(sequence===requestId){byId('pvgis-chart').replaceChildren(node('p','Hourly source unavailable or its provenance changed. No curve invented.'));}}
  }
  function renderSolar() {
    const pvgis=dataset.pvgis;
    const placeholder=document.querySelector('#view-solar .large-placeholder');if(!placeholder)return;
    const card=placeholder.closest('.card');card.querySelector('h2').textContent='Hypothetical PVGIS generation';
    card.querySelector('.tag').textContent=pvgis.hypothetical_state==='available'?'Modeled sensitivity · not actual generation':'API acquisition pending / unavailable';
    const explorer=node('div');explorer.id='pvgis-explorer';
    explorer.append(node('p','Official PVGIS output for assumed capacity scenarios. This does not estimate or measure the actual installed A160 system.','note-box'));
    const select=node('select');select.id='pvgis-case';select.className='mini-btn';select.setAttribute('aria-label','Hypothetical PVGIS scenario');
    (pvgis.hypothetical_scenarios||[]).forEach(row=>{const option=node('option',`${row.assessment==='retrospective'?'Retrospective potential':'Conditional additional'} · ${row.scenario} · ${number(row.capacity_kwp)} kWp`);option.value=row.scenario_id;select.append(option);});
    select.value='retrospective_base';select.addEventListener('change',loadSolar);explorer.append(select);
    const dayLabel=node('label','Local date (Europe/Madrid) ','pv-date-label');const day=node('input');day.type='date';day.id='pvgis-day';day.setAttribute('aria-label','PVGIS local display date');dayLabel.append(day);explorer.append(dayLabel);
    const plot=node('div');plot.id='pvgis-chart';explorer.append(node('p','Modeled energy per hourly interval (kWh), not observed power.','label'),plot);
    const summary=node('p',undefined,'footnote');summary.id='pvgis-day-summary';explorer.append(summary);
    const details=node('dl');details.id='pvgis-run-details';explorer.append(details);
    const button=node('button','Download hypothetical settings & provenance','mini-btn');button.id='download-pvgis-settings';button.type='button';explorer.append(button);
    explorer.append(node('p','PVGIS P(W) uses a one-hour P/1000 energy approximation. The 2017 satellite-weather sequence differs from office IWEC weather. UTC offsets are retained; local dates at the UTC-year boundaries can be partial. Local roof shading/inverters are unknown. No demand matching is performed.','footnote'));
    if(pvgis.hypothetical_state!=='available'){
      explorer.append(node('p','Automatic API acquisition unavailable. Preserve the failure record and import an actual PVGIS export using the manual fallback.','muted'));
      explorer.append(node('code',pvgis.manual_fallback));
    }
    placeholder.replaceWith(explorer);
    if(select.options.length)loadSolar();else{plot.replaceChildren(node('p','No acquired hourly series. Run the documented acquisition or manual-import command.'));button.disabled=true;}
  }
  window.RoofscapesPV={
    render(data,context){dataset=data;callbacks=context;renderExisting();renderSolar();},
    selectScenario(scenario){comparisonScenario=scenario;if(dataset)compare();},
    getSelection(){return byId('pvgis-case')?.value?{scenario_id:byId('pvgis-case').value,local_display_date:byId('pvgis-day').value,display_timezone:'Europe/Madrid',hypothetical:true,energy_sharing_eligible:false}:null;}
  };
})();
