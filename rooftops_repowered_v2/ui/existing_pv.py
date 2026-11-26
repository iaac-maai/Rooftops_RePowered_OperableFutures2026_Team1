"""Existing-PV evidence and independent spatial comparison; no capacity inference."""
from .data import SourceUnavailable, pending, safe_text


def assess(repository):
    try:
        record=repository.read('existing_pv_record')
        reference=repository.reference()
        roof=repository.scenarios()
        if reference['state']!='available' or roof['state']!='available':
            return pending('Existing PV identity is known, but comparison sources are incomplete.', ['Reference and roof scenario reports'])
        observed=reference['observed_projected_panel_coverage_m2']
        metrics={row['scenario']:row for row in reference['metrics']}
        comparisons=[]
        for row in roof['assessments']['retrospective']['scenarios']:
            predicted=row['panel_projected_area_m2']
            comparisons.append({'scenario':row['scenario'],'observed_projected_area_m2':observed,
                'predicted_projected_area_m2':predicted,'area_difference_m2':predicted-observed,
                'area_difference_percent':100*(predicted-observed)/observed,
                'spatial_iou':metrics[row['scenario']]['panel_coverage_iou'],
                'observed_coverage_within_eligible_fraction':metrics[row['scenario']]['observed_panel_area_inside_predicted_eligible_fraction'],
                'hypothetical_capacity_kwp':row['estimated_kwp'],'hypothetical_module_count':row['panel_count'],
                'actual_installed_capacity_kwp':None,'capacity_error_percent':None})
        return {'state':'partial','evidence_state':'OBSERVED_IDENTITY_WITH_UNKNOWN_SYSTEM_SPECIFICATIONS',
            'building_id':'A160','assessment_version':record['assessment_version'],
            'existing_pv_identity':'visually_confirmed','installation':{key:None for key in record['installation']},
            'existing_capacity_verified':False,
            'observed':{'data_origin':'OBSERVED_IMAGE_INTERPRETATION','projected_panel_coverage_m2':observed,
                'threshold_sensitivity_m2':reference['area_sensitivity_m2'],'native_gsd_m':reference['native_gsd_m'],
                'capture_date':reference['source_dates']['final_ortho_captured'],
                'sensitivity_is_statistical_confidence_interval':False},
            'comparisons':comparisons,'additional_scenarios':roof['assessments']['additional']['scenarios'],
            'municipal_comparison':reference['municipal_comparison'],
            'limitations':reference['limitations']+[
                'Image coverage is not module count or installed kWp. PVGIS sensitivity is not actual existing generation.',
                'Spatial overlap tests an existing installation; it does not certify maximum installable capacity.'],
            'missing_inputs':['Owner/installer as-built PV record','Module count/Wp and inverter information',
                'Actual array tilt/orientation and any commissioning changes'],
            'provenance':repository.provenance('existing_pv_record','reference','annotation','retrospective','additional')}
    except (SourceUnavailable,KeyError) as exc:
        return pending(safe_text(exc), ['Existing PV evidence record'])
