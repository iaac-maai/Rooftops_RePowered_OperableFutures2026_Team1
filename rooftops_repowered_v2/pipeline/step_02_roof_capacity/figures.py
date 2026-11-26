"""Export annotated scientific rooftop figures; no generative imagery."""
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
from PIL import Image
import shapely

from pipeline.common import ROOT, resolve
from .adapter import load_geometry
from .assessments import load_settings


def outline(axis, geometry, color, linewidth=1.2, fill=False, alpha=.2):
    if geometry.is_empty:
        return
    polygons = list(geometry.geoms) if geometry.geom_type == 'MultiPolygon' else [geometry]
    for polygon in polygons:
        x,y = polygon.exterior.xy
        if fill:
            axis.fill(x,y,color=color,alpha=alpha,linewidth=0)
        axis.plot(x,y,color=color,linewidth=linewidth)


def render(settings_path='config/a160_assessments.json'):
    settings=load_settings(settings_path)
    root=resolve(settings['output_dir'])
    report=ROOT/'reports/roof_capacity/A160'
    image=np.asarray(Image.open(resolve(settings['orthophoto_path'])).convert('RGB'))
    meta=json.loads(resolve(settings['orthophoto_bounds_report']).read_text())
    bbox=meta['ortho_bbox_25831']; x0,y0,x1,y1=bbox
    fp=load_geometry(settings['footprint_path'],'EPSG:4326')
    occupied=load_geometry(settings['observed_array_envelopes'],'EPSG:4326')
    observed=load_geometry(settings['observed_panel_mask'],'EPSG:4326')
    annotation=json.loads(resolve(settings['observed_annotation_metadata']).read_text())
    yy,xx=np.indices(image.shape[:2])
    xs=x0+(xx+.5)*(x1-x0)/image.shape[1]
    ys=y1-(yy+.5)*(y1-y0)/image.shape[0]
    shapely.prepare(observed)
    mask=shapely.contains_xy(observed,xs,ys)
    overlay=np.zeros((*mask.shape,4),dtype=float)
    overlay[mask]=[1,.55,.08,.65]
    fig,axes=plt.subplots(1,3,figsize=(17,8.4),layout='constrained')
    titles=['Independent image reference','A · Retrospective geometry screening','B · Current additional-PV screening']
    for axis,title in zip(axes,titles):
        axis.imshow(image,extent=[x0,x1,y0,y1],origin='upper')
        outline(axis,fp,'white',1.6)
        axis.set_title(title,fontsize=11,fontweight='bold')
        axis.set_xlim(x0,x1);axis.set_ylim(y0,y1);axis.set_aspect('equal')
        axis.set_xticks([]);axis.set_yticks([])
        axis.annotate('N',xy=(x0+7,y1-5),xytext=(x0+7,y1-15),
                      color='black',ha='center',arrowprops={'facecolor':'white','edgecolor':'black','width':2,'headwidth':7})
        axis.plot([x0+5,x0+15],[y0+5,y0+5],color='white',lw=4)
        axis.text(x0+10,y0+7,'10 m',ha='center',color='black',fontsize=8,
                  bbox={'facecolor':'white','alpha':.8,'edgecolor':'none','pad':1})
    axes[0].imshow(overlay,extent=[x0,x1,y0,y1],origin='upper')
    outline(axes[0],occupied,'#ffad21',.8)
    axes[0].text(.03,.02,f'Image-interpreted module coverage: {observed.area:.1f} m²\n'
                       f'Threshold sensitivity: {min(annotation["area_sensitivity_m2"].values()):.1f}–'
                       f'{max(annotation["area_sensitivity_m2"].values()):.1f} m²\n'
                       'Module count / installed kWp: unverified',
                       transform=axes[0].transAxes,fontsize=8,
                       bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
    import pandas as pd
    for axis,assessment,color in [(axes[1],'retrospective','#279bff'),(axes[2],'additional','#00db83')]:
        eligible=load_geometry(root/f'{assessment}/base_eligible.geojson','EPSG:4326',True)
        panels=load_geometry(root/f'{assessment}/base_panels.geojson','EPSG:4326',True)
        outline(axis,eligible,color,.7)
        outline(axis,panels,color,.5,True,.65)
        if assessment=='additional':outline(axis,occupied,'#ffad21',1.1)
        row=pd.read_csv(root/f'{assessment}/roof_capacity_scenarios.csv').set_index('scenario').loc['base']
        axis.text(.03,.02,f'Base scenario: {int(row.panel_count)} assumed modules · {row.estimated_kwp:.2f} kWp\n'
                          '420 Wp/module, 10° tilt · geometric assumption\nLow confidence; not installation approval',
                          transform=axis.transAxes,fontsize=8,
                          bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
    fig.suptitle('A160 · Existing installation reference and two separate rooftop assessments',fontsize=15,fontweight='bold')
    fig.legend(handles=[Line2D([0],[0],color='white',markeredgecolor='black',marker='s',label='Cadastral footprint'),
                        Patch(color='#ffad21',label='Observed PV / occupied array envelope'),
                        Patch(color='#279bff',label='A: predicted structural potential'),
                        Patch(color='#00db83',label='B: additional candidate panels')],
               loc='outside lower center',ncol=4,fontsize=8,frameon=False)
    fig.text(.01,.055,'ICGC ortho captured 2025-06-18 (native GSD 0.25 m; displayed resampled). LiDAR acquired 2022-06-01; PV already visible on 2022-05-18.\n'
             'A uses no observed PV mask, but post-installation LiDAR limits independence. Existing and proposed kWp/generation must never be combined implicitly.',fontsize=8)
    fig.savefig(report/'A160_two_assessments.png',dpi=180,bbox_inches='tight')
    fig.savefig(report/'A160_two_assessments.pdf',bbox_inches='tight')
    plt.close(fig)
    return report/'A160_two_assessments.png'


if __name__=='__main__':print(render())


def render_latest_context(settings_path='config/a160_assessments.json'):
    """Newest provisional imagery is contextual QA, not transferred PV labels."""
    settings = load_settings(settings_path)
    report = ROOT / 'reports/roof_capacity/A160'
    bbox = json.loads(resolve(settings['orthophoto_bounds_report']).read_text())['ortho_bbox_25831']
    x0,y0,x1,y1 = bbox
    fig, axes = plt.subplots(1, 2, figsize=(10, 7), layout='constrained')
    images = [(resolve(settings['orthophoto_path']), 'Final orthophoto: 2025-06-18'),
        (ROOT / 'datasets/raw/roof_capacity/A160/source_probes/A160_provisional_2026.png',
         'Provisional aerial mosaic: 2026-03-16')]
    for axis, (path, title) in zip(axes, images):
        axis.imshow(Image.open(path), extent=[x0,x1,y0,y1], origin='upper')
        axis.set_title(title, fontsize=11)
        axis.set_xticks([]); axis.set_yticks([])
    fig.suptitle('A160: finalized reference and newest public provisional imagery', fontsize=13)
    fig.supxlabel('ICGC WMS, identical requested extent. Provisional roof alignment differs; do not transfer pixel labels without registration.\n'
                  'Existing array blocks remain visible. Fine service/clearance changes and exact panel counts are not verified.', fontsize=8)
    fig.savefig(report / 'A160_latest_imagery_comparison.png', dpi=160)
    plt.close(fig)
