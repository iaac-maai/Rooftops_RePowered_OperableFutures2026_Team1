"""Independent 2025 imagery reference, deliberately separate from prediction."""
import json
import math

import numpy as np
from PIL import Image
import shapely
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pipeline.common import now, require_file, resolve, sha256, write_json
from .adapter import load_geometry, write_geojson
from .assessments import load_settings


def annotate(settings_path='config/a160_assessments.json', annotation_path='config/a160_pv_reference_annotation.json'):
    settings = load_settings(settings_path)
    protocol = json.loads(require_file(resolve(annotation_path)).read_text(encoding='utf-8'))
    image_path = require_file(resolve(settings['orthophoto_path']))
    image = np.asarray(Image.open(image_path).convert('RGB'), dtype=float)
    height, width = image.shape[:2]
    source = json.loads(require_file(resolve(settings['orthophoto_bounds_report'])).read_text())
    x0, y0, x1, y1 = source['ortho_bbox_25831']
    dx, dy = (x1 - x0) / width, (y1 - y0) / height
    angle = math.radians(protocol['visual_rotation_ccw_degrees'])
    rw, rh = protocol['rotated_image_size_pixels']

    def project(vertices):
        xy = np.asarray(vertices, dtype=float)
        u, v = xy[:, 0] - rw / 2, xy[:, 1] - rh / 2
        original_x = np.cos(angle) * u - np.sin(angle) * v + width / 2
        original_y = np.sin(angle) * u + np.cos(angle) * v + height / 2
        return Polygon(np.column_stack([x0 + original_x * dx, y1 - original_y * dy]))

    rows = [project([(left,top),(right,top),(right,bottom),(left,bottom)])
            for left,top,right,bottom in protocol['pv_row_rectangles_rotated_pixels']]
    footprint = load_geometry(settings['footprint_path'], 'EPSG:4326')
    row_union = unary_union(rows).intersection(footprint)
    yy, xx = np.indices((height, width))
    xs, ys = x0 + (xx + .5) * dx, y1 - (yy + .5) * dy
    inside = shapely.contains_xy(row_union, xs, ys)
    luminance = image.mean(axis=2)
    rule = protocol['pv_pixel_rule']

    def classify(threshold):
        return inside & (luminance < threshold) & (luminance > rule['minimum_mean_rgb']) & ((image[:,:,0] - image[:,:,2]) < rule['maximum_red_minus_blue'])

    pv = classify(rule['maximum_mean_rgb'])
    rr, cc = np.nonzero(pv)
    cells = shapely.box(x0 + cc * dx, y1 - (rr + 1) * dy, x0 + (cc + 1) * dx, y1 - rr * dy)
    coverage = shapely.union_all(cells).intersection(footprint)
    occupied = unary_union([part.buffer(protocol['occupied_array_envelope_buffer_m']) for part in rows]).intersection(footprint)
    perimeter = project(protocol['current_perimeter_roof_polygon_rotated_pixels'])
    perimeter_access = perimeter.difference(perimeter.buffer(-protocol['current_perimeter_access_reserve_m']))
    access = unary_union([perimeter_access, *[project(polygon) for polygon in protocol['current_access_polygons_rotated_pixels']]]).intersection(footprint)
    props = {'building_id':'A160','data_origin':'OBSERVED_IMAGE_INTERPRETATION',
             'capture_date':protocol['capture_date'],'native_gsd_m':protocol['native_gsd_m'],
             'pv_identity_confirmed_by':'User manual review; ChatGPT Work conversation 2026-11-15',
             'installed_capacity_kwp':None,'module_count':None}
    write_geojson(resolve(settings['observed_panel_mask']), [coverage], [{**props,'interpretation':'horizontal projected module-like pixel coverage; not survey-grade panel boundaries'}])
    write_geojson(resolve(settings['observed_array_envelopes']), [occupied], [{**props,'interpretation':'occupied PV row-block envelopes including inter-row spacing'}])
    access_path = resolve(settings['current_access_exclusions'])
    write_geojson(access_path, [access], [{**props,'interpretation':'visible service/circulation zones, assessment B only; not certified fire design'}])
    write_geojson(resolve(settings['current_high_roof_boundary']), [perimeter.intersection(footprint)],
                  [{**props,'interpretation':'current upper-roof boundary from imagery; assessment B only, with georegistration uncertainty'}])
    metadata = {**protocol,'created_utc':now(),'image_sha256':sha256(image_path),
                'annotation_protocol_sha256':sha256(resolve(annotation_path)),
                'observed_projected_panel_coverage_m2':coverage.area,'occupied_array_envelopes_m2':occupied.area,
                'access_plant_exclusions_m2':access.area,
                'area_sensitivity_m2':{str(t):float(classify(t).sum()*dx*dy) for t in protocol['annotation_sensitivity_thresholds']},
                'resampled_pixel_size_m':[dx,dy], 'reliable_panel_count':None,
                'retrospective_prediction_manifest_sha256_at_annotation':sha256(resolve(settings['output_dir'])/'retrospective/run_manifest.json'),
                'prediction_completed_before_this_annotation':True,
                'retrospective_image_annotation_is_not_maximum_capacity_truth':True}
    write_json(resolve(settings['observed_annotation_metadata']), metadata)
    print(json.dumps({key:metadata[key] for key in ['observed_projected_panel_coverage_m2','occupied_array_envelopes_m2','area_sensitivity_m2','reliable_panel_count']},indent=2))
    return metadata


if __name__=='__main__':annotate()
