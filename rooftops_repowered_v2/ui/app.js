/* Read-only research UI. Reported findings come only from the local API. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const all = selector => [...document.querySelectorAll(selector)];
  const labels = {overview:'Overview',roof:'Roof intelligence',solar:'Solar production',demand:'Demand prediction',sharing:'Energy sharing',impact:'Impact assessment',evidence:'Sources & evidence'};
  const state = {view:'overview',assessment:'retrospective',roofScenario:'base',hour:12,typology:'office',strategy:'host'};
  let data = null;
  let mapRequest = 0;
  const profiles = window.ROOFSCAPES_PROFILES;
  const colors = {office:'#427f6a',school:'#6b9bb1',home:'#c59c5f',hotel:'#ae809c'};
  const strategies = {
    grid:['Grid-only baseline','No participant allocation is applied. This reference describes conventional grid imports.'],
    host:['Host-only self-consumption','A160 uses its own solar output. Other buildings receive no allocated share.'],
    fixed:['Fixed community shares','Each participant receives a pre-agreed constant fraction of hourly solar production.'],
    informed:['Demand-informed pre-agreed shares','Forecast-based hourly shares must be frozen before evaluation against independent reference demands.']
  };
  function text(id,value) { if ($(id)) $(id).textContent = value; }
  function element(tag,value,className) {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  }
  const fmt = (value,digits=2) => Number.isFinite(value) ? value.toFixed(digits) : 'Unknown';
  function activate(view,focus=true) {
    if (!labels[view]) return;
    state.view = view;
    all('.view').forEach(node => node.classList.toggle('active',node.id === `view-${view}`));
    all('.nav-btn').forEach(node => {
      const active = node.dataset.view === view;
      node.classList.toggle('active',active);
      if (active) node.setAttribute('aria-current','page'); else node.removeAttribute('aria-current');
    });
    text('breadcrumb-current',labels[view]);
    const heading = $(`view-${view}`).querySelector('h1');
    if (focus && heading) { heading.tabIndex = -1; heading.focus({preventScroll:true}); }
    window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    if (view === 'demand') drawCharts();
  }
  function drawCharts() {
    all('.hour-label').forEach(node => node.textContent = `${String(state.hour).padStart(2,'0')}:00`);
    all('.hour-control').forEach(node => node.value = state.hour);
    all('svg.profile-chart').forEach(svg => {
      const selected = svg.closest('#view-demand') ? state.typology : null;
      const left=38,right=688,top=21,bottom=175;
      let markup = '<title>ILLUSTRATIVE_NOT_SIMULATED: normalized activity, not kWh</title>';
      for (let i=0;i<=4;i++) {
        const y=top+(bottom-top)*i/4;
        markup += `<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" stroke="#dfe7dd"/><text x="30" y="${y+4}" text-anchor="end" font-size="10" fill="#4b6354">${(1-i/4).toFixed(2)}</text>`;
      }
      for (const hour of [0,6,12,18,23]) markup += `<text x="${left+hour/23*(right-left)}" y="201" text-anchor="middle" font-size="11" fill="#4b6354">${hour}:00</text>`;
      for (const [key,values] of Object.entries(profiles)) {
        const path = values.map((v,i)=>`${i?'L':'M'}${left+i/23*(right-left)} ${bottom-v*(bottom-top)}`).join(' ');
        markup += `<path d="${path}" fill="none" stroke="${colors[key]}" stroke-width="${selected===key?4:3}" opacity="${selected&&selected!==key?.2:.95}"/>`;
      }
      const x=left+state.hour/23*(right-left), key=selected||'office';
      markup += `<line x1="${x}" y1="${top-5}" x2="${x}" y2="${bottom+2}" stroke="#355e4f" stroke-dasharray="5 4"/><circle cx="${x}" cy="${bottom-profiles[key][state.hour]*(bottom-top)}" r="5" fill="white" stroke="${colors[key]}" stroke-width="2.5"/>`;
      svg.innerHTML = markup; // Only fixed educational arrays and numeric UI state, never API text.
    });
  }
  function setStrategy(strategy) {
    if (!strategies[strategy]) return;
    state.strategy = strategy;
    all('[data-strategy]').forEach(node => {
      node.classList.toggle('active',node.dataset.strategy === strategy);
      node.setAttribute('aria-pressed',String(node.dataset.strategy === strategy));
    });
    text('strategy-title',strategies[strategy][0]);
    text('strategy-description',strategies[strategy][1]);
  }
  function row(assessment,scenario=state.roofScenario) {
    return data?.roof.assessments[assessment]?.scenarios?.find(item=>item.scenario===scenario);
  }
  function setRoof(scenario) {
    if (!['conservative','base','optimistic'].includes(scenario)) return;
    state.roofScenario = scenario;
    const retro=row('retrospective'), additional=row('additional');
    text('roof-retro',retro?`${fmt(retro.estimated_kwp)} kWp`:'Pending source');
    text('roof-additional',additional?`${fmt(additional.estimated_kwp)} kWp`:'Pending source');
    text('roof-panel-count',retro?retro.panel_count:'Pending');
    text('roof-eligible',retro?`${fmt(retro.usable_area_m2)} m²`:'Pending');
    text('roof-additional-caption',additional?`${additional.panel_count} hypothetical additional modules; access, mounting and structural checks remain unverified.`:'Additional assessment source unavailable.');
    const score=data?.reference.metrics?.find(item=>item.scenario===scenario);
    text('roof-iou',score?fmt(score.panel_coverage_iou,3):'Pending');
    all('[data-roof-scenario]').forEach(node => {
      node.classList.toggle('selected',node.dataset.roofScenario===scenario);
      node.setAttribute('aria-pressed',String(node.dataset.roofScenario===scenario));
    });
    if (data) drawRoof();
    window.RoofscapesPV?.selectScenario(scenario);
  }
  async function drawRoof() {
    const sequence=++mapRequest;
    const container=$('roof-map');
    try {
      const response=await fetch(`/api/roof/A160/map?assessment=${state.assessment}&scenario=${state.roofScenario}`);
      if (!response.ok) throw new Error('Map source unavailable');
      const map=await response.json();
      if (sequence!==mapRequest) return;
      if (map.state!=='available') throw new Error('Map source unavailable');
      const features=Object.values(map.layers).flatMap(layer=>layer.features);
      const points=[];
      function collect(coords) {
        if (typeof coords[0]==='number') points.push(coords); else coords.forEach(collect);
      }
      features.forEach(feature=>collect(feature.geometry.coordinates));
      if (!points.length) throw new Error('Geometry is empty');
      const longitude=points.reduce((sum,p)=>sum+p[0],0)/points.length;
      const latitude=points.reduce((sum,p)=>sum+p[1],0)/points.length;
      const radians=Math.PI/180, radius=6378137;
      const project=point=>[(point[0]-longitude)*radians*radius*Math.cos(latitude*radians),(point[1]-latitude)*radians*radius];
      const projected=points.map(project), xs=projected.map(p=>p[0]), ys=projected.map(p=>p[1]);
      const bounds=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
      const scale=Math.min(630/(bounds[2]-bounds[0]),270/(bounds[3]-bounds[1]));
      const offsetX=(710-(bounds[2]-bounds[0])*scale)/2;
      const screen=point=>{const [x,y]=project(point);return [offsetX+(x-bounds[0])*scale,325-(y-bounds[1])*scale];};
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
      svg.setAttribute('viewBox','0 0 710 380');svg.setAttribute('role','img');
      svg.setAttribute('aria-label',`Actual A160 WGS84 geometry: ${state.assessment}, ${state.roofScenario}. Local metric projection.`);
      const fills={footprint:'#e7e7dc',eligible:'#cde2d3',panels:'#527f99'};
      for (const [name,layer] of Object.entries(map.layers)) for (const feature of layer.features) {
        const polygons=feature.geometry.type==='Polygon'?[feature.geometry.coordinates]:feature.geometry.coordinates;
        for (const polygon of polygons) {
          const path=document.createElementNS(svg.namespaceURI,'path');
          path.setAttribute('d',polygon.map(ring=>ring.map((p,i)=>`${i?'L':'M'}${screen(p).join(',')}`).join(' ')+'Z').join(' '));
          path.setAttribute('fill',fills[name]);path.setAttribute('fill-rule','evenodd');
          path.setAttribute('stroke',name==='panels'?'#27506b':'#71887b');path.setAttribute('stroke-width',name==='panels'?'.6':'1.1');
          svg.append(path);
        }
      }
      const caption=document.createElementNS(svg.namespaceURI,'text');caption.setAttribute('x','40');caption.setAttribute('y','22');caption.setAttribute('fill','#234a37');caption.setAttribute('font-size','13');
      caption.textContent=`${state.assessment==='retrospective'?'A · Retrospective':'B · Additional'} / ${state.roofScenario} · EPSG:4326 source · north up`;
      svg.append(caption);
      const scaleLine=document.createElementNS(svg.namespaceURI,'path');scaleLine.setAttribute('d',`M40 350h${10*scale}`);scaleLine.setAttribute('stroke','#234a37');scaleLine.setAttribute('stroke-width','3');svg.append(scaleLine);
      const scaleText=document.createElementNS(svg.namespaceURI,'text');scaleText.setAttribute('x','40');scaleText.setAttribute('y','370');scaleText.setAttribute('font-size','11');scaleText.textContent='10 m · local equirectangular display';svg.append(scaleText);
      container.replaceChildren(svg);
    } catch (_) { if(sequence===mapRequest) container.textContent='Roof geometry unavailable. Scenario tables remain independently readable.'; }
  }
  function openEvidence(id,trigger) {
    if (!data) return;
    const dialog=$('evidence-dialog'), content=$('evidence-content');
    content.replaceChildren();
    const records=id?data.evidence.records.filter(record=>record.id===id):data.evidence.records;
    for (const record of records) content.append(evidenceCard(record));
    dialog.returnFocus=trigger;
    dialog.showModal(); $('close-evidence').focus();
  }
  function evidenceCard(record) {
    const card=element('article',undefined,'evidence-record');
    card.append(element('h3',record.title),element('span',record.state,'tag estimated'));
    card.append(element('p',record.limitations));
    card.append(element('p',`Source date: ${record.source_date||'See source manifest'} · Units: ${record.unit}`,'muted'));
    if (record.id==='model' && data.model.model_version) card.append(element('p',`Model report version: ${data.model.model_version}`,'muted'));
    if (record.id==='roof') {
      const version=row(state.assessment)?.model_version;
      if (version) card.append(element('p',`Roof model version: ${version}`,'muted'));
    }
    if (record.source_url) {
      const link=element('a','Open publisher source ↗','inline-source');link.href=record.source_url;link.target='_blank';link.rel='noreferrer';card.append(link);
    }
    record.repository_paths.forEach(path=>card.append(element('code',path)));
    return card;
  }
  function bindEvidence() {
    const add=(parent,id,label)=>{
      const button=element('button',label,'mini-btn evidence-trigger');button.type='button';
      button.addEventListener('click',()=>openEvidence(id,button));parent.append(button);
    };
    add($('view-roof').querySelector('.scenario-select'),'roof','Sources & assumptions');
    add($('view-demand').querySelector('.intro'),'model','Model evidence');
    add($('view-roof').querySelector('.intro'),'reference','Capture dates & reference');
    for (const link of all('.inline-source')) {
      if (link.textContent==='View roof sources and assumptions' || link.textContent==='View model evidence and limitations') {
        const id=link.textContent.startsWith('View roof')?'roof':'model';
        link.href='#evidence';link.removeAttribute('target');link.addEventListener('click',event=>{event.preventDefault();openEvidence(id,link);});
      }
    }
  }
  function renderData() {
    const status=data.status;
    text('connection-status',`Repository data connected · read-only · ${status.commit?status.commit.slice(0,7):'version unavailable'}`);
    $('connection-status').classList.add('connected');
    if (status.last_updated_utc) text('updated-at',`Repository files updated ${new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Madrid'}).format(new Date(status.last_updated_utc))} (Europe/Madrid).`);
    const inventory=$('building-inventory');inventory.replaceChildren();
    if (data.buildings.state==='available') {
      text('building-count',`${data.buildings.buildings.length} buildings`);
      for (const building of data.buildings.buildings) {
        const item=element('div',undefined,'cluster-item');
        const icon=element('div',building.is_host?'▤':'⌂',`cluster-icon ci-${building.is_host?'office':'school'}`);
        const description=element('div');description.append(element('strong',building.building_name),element('span',`${building.building_use} · ${building.is_host?'PV host':'hypothetical participant'}`));
        const details=element('details',undefined,'candidate-evidence');
        details.append(element('summary','Evidence & assumptions'));
        details.append(element('p',`Geometry/as-built status: ${building.geometry_status}. Hourly building meters: unavailable. Participation and electrical eligibility: unverified.`));
        details.append(element('p',building.is_host?'Existing PV is visually confirmed; module specifications and installed kWp are unknown.':`Existing PV status: ${building.existing_pv_status}. Building-use patterns are hypotheses until sourced simulations are prepared.`));
        if(building.source_url) {
          const source=element('a','Publisher source ↗','inline-source');source.href=building.source_url;source.target='_blank';source.rel='noreferrer';details.append(source);
        }
        description.append(details);
        item.append(icon,description);if(building.is_host) item.append(element('span','Host','right-label'));inventory.append(item);
      }
      inventory.append(element('p','Candidate buildings only. Participation, electrical connections and legal eligibility are unverified.','footnote'));
    } else inventory.textContent=data.buildings.message;
    const retro=row('retrospective','base'),additional=row('additional','base');
    text('overview-retro',retro?`${fmt(retro.estimated_kwp)} kWp`:'Pending');
    text('overview-additional',additional?`${fmt(additional.estimated_kwp)} kWp`:'Pending');
    text('observed-coverage',data.reference.state==='available'?`${fmt(data.reference.observed_projected_panel_coverage_m2)} m²`:'Pending');
    if(data.roof.assumptions) text('module-assumption',`Assumed new modules: ${data.roof.assumptions.wp} Wp, ${data.roof.assumptions.long_m} × ${data.roof.assumptions.short_m} m; ${data.roof.assumptions.tilt_degrees}° tilt. Not installed module specifications.`);
    const model=data.model;
    if(model.state==='available') {
      const test=model.metrics.find(row=>row.model==='office_energyplus_xgboost' && row.split==='test');
      const validation=model.metrics.find(row=>row.model==='office_energyplus_xgboost' && row.split==='validation');
      const linear=model.metrics.find(row=>row.model==='schedule_linear_baseline' && row.split==='test');
      text('model-configurations',model.configuration_count);
      text('model-splits',`${model.splits.train} train · ${model.splits.validation} validation · ${model.splits.test} test configurations`);
      // Training hours are not present in the metrics CSV; never infer them from synthetic constants.
      text('model-hours',test&&validation?(test.rows+validation.rows).toLocaleString('en-GB'):'Pending');
      const hours=$('model-hours').closest('.card');hours.querySelector('.label').textContent='Held-out evaluated hourly intervals';
      hours.querySelector('.muted').textContent='Validation + test rows; simulated loads';
      text('model-mae',test?`${fmt(test.mae_kwh,3)} kWh`:'Pending');
      text('model-baseline',linear?`vs ${fmt(linear.mae_kwh,3)} linear baseline; per hourly interval`:'Baseline unavailable');
      text('model-area',`${fmt(model.floor_area_m2)} m² reference office`);
      text('sidebar-model',`${model.configuration_count} office simulation configurations.`);
    }
    for (const [view,stage] of Object.entries({solar:'pvgis',demand:'demand',sharing:'sharing',impact:'impact'})) {
      const item=data[stage], container=$(`pending-${view}`);container.replaceChildren(element('strong',stage==='pvgis'&&item.hypothetical_state==='available'?'ACTUAL SYSTEM PENDING · HYPOTHETICAL PVGIS AVAILABLE':'PENDING · MISSING_SOURCE_INPUT'),element('p',item.message));
      const list=element('ul');item.missing_inputs.forEach(input=>list.append(element('li',input)));container.append(list);
    }
    const evidence=$('evidence-records');evidence.replaceChildren(element('h2','Repository evidence register'));
    data.evidence.records.forEach(record=>evidence.append(evidenceCard(record)));
    const dates=data.reference.source_dates;
    if(dates) {
      const sourceNote=element('div',undefined,'note-box source-dates');
      sourceNote.append(element('strong','Capture dates and uncertainty'));
      sourceNote.append(element('p',`LiDAR acquired ${dates.lidar_acquired}; finalized orthophoto ${dates.final_ortho_captured}; provisional image ${dates.provisional_image_captured}. The LiDAR already contains PV.`));
      const municipal=data.reference.municipal_comparison;
      sourceNote.append(element('p',`Municipal record ${municipal.municipal_source_date}: ${fmt(municipal.municipal_potential_kw_source,1)} kW legacy modeled potential. Predates modern A160; not current installed capacity and never additive.`));
      $('view-roof').append(sourceNote);
    }
    setRoof(state.roofScenario);
    window.RoofscapesPV?.render(data,{selectRoof:setRoof,openView:activate});
    $('export-config').disabled=false;$('export-config-mobile').disabled=false;
  }
  function exportTemplate() {
    if(!data) return;
    const selected=row(state.assessment);
    const payload={document_type:'UI_SCENARIO_TEMPLATE', executed:false,
      note:'Unexecuted research template. Not meter data, a simulation result or a pipeline execution config.',
      case_study:'A160_Poblenou',host:'A160',
      participants:(data.buildings.buildings||[]).filter(row=>!row.is_host).map(row=>row.building_id),
      roof_estimation:{assessment:state.assessment,scenario:state.roofScenario,estimated_kwp:selected?.estimated_kwp??null,
        generation_role:selected?.generation_role??null,actual_installed_kwp:null,
        confidence:selected?.confidence??null,data_origin:selected?.data_origin??null,
        model_version:selected?.model_version??null,assumed_module_wp:selected?.assumed_module_wp??null},
      sharing_strategy:state.strategy, explorer_hour:state.hour,demand_typology_preview:state.typology,
      profile_origin:'ILLUSTRATIVE_NOT_SIMULATED',profile_unit:'normalized_activity_0_to_1',
      timestamp_basis:'timestamp_utc',display_timezone:'Europe/Madrid',
      provenance:{commit:data.status.commit,model_version:data.model.model_version??null,
        scenario_sources:data.roof.assessments[state.assessment]?.provenance??[],source_dates:data.reference.source_dates??null},
      pv_hourly:null,demand_hourly:null,scenario_results:null,impact_results:null};
    payload.pvgis_sensitivity_preview=window.RoofscapesPV?.getSelection()??null;
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='roofscapes_ui_scenario_template.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  all('.nav-btn').forEach(node=>node.addEventListener('click',()=>activate(node.dataset.view)));
  all('[data-goto]').forEach(node=>node.addEventListener('click',()=>activate(node.dataset.goto)));
  all('[data-roof-scenario]').forEach(node=>node.addEventListener('click',()=>setRoof(node.dataset.roofScenario)));
  $('assessment-select').addEventListener('change',event=>{state.assessment=event.target.value;drawRoof();});
  all('.hour-control').forEach(node=>node.addEventListener('input',()=>{state.hour=+node.value;drawCharts();}));
  $('typology-select').addEventListener('change',event=>{state.typology=event.target.value;drawCharts();});
  all('[data-strategy]').forEach(node=>node.addEventListener('click',()=>setStrategy(node.dataset.strategy)));
  $('export-config').addEventListener('click',exportTemplate);$('export-config-mobile').addEventListener('click',exportTemplate);
  $('close-evidence').addEventListener('click',()=>$('evidence-dialog').close());
  $('evidence-dialog').addEventListener('close',()=>{ $('evidence-dialog').returnFocus?.focus(); });
  bindEvidence();activate('overview',false);setRoof('base');setStrategy('host');drawCharts();
  fetch('/api/dashboard').then(response=>{if(!response.ok)throw new Error();return response.json();})
    .then(payload=>{data=payload;renderData();})
    .catch(()=>{text('connection-status','Repository data unavailable. Run python -m ui.server and reload; reported metrics remain pending.');$('connection-status').setAttribute('role','alert');});
})();
