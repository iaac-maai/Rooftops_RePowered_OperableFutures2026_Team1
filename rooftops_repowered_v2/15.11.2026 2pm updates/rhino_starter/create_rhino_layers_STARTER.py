"""OPTIONAL FUTURE RHINO 8 SCRIPT. DO NOT EXECUTE IN CODEX REVIEW-ONLY SESSION.
Creates a consistent layer tree in an open .3dm file, no geometry, no downloads.
Execute manually inside Rhino's Python 3 script environment after review.
"""
import rhinoscriptsyntax as rs

LAYERS = [
 ('00_SOURCE_DWG_LOCKED', (133, 144, 135)),
 ('01_CONTEXT_SHADING', (167, 177, 160)),
 ('02_A160_MASSING', (75, 104, 90)),
 ('03_FLOOR_DATUMS', (198, 168, 94)),
 ('04_THERMAL_ZONES', (78, 133, 158)),
 ('05_WINDOWS_APERTURES', (118, 171, 191)),
 ('06_ROOF_PV_REFERENCE', (51, 104, 151)),
 ('07_COURTYARDS_TERRACES', (145, 157, 96)),
 ('80_QA_DIMENSIONS', (189, 135, 91)),
 ('90_METADATA', (115, 113, 129)),
]

def main():
    for name, color in LAYERS:
        if not rs.IsLayer(name):
            rs.AddLayer(name, color)
        if name.startswith('00_'):
            rs.LayerLocked(name, True)
    print('Created or preserved {} named layers. No geometry generated.'.format(len(LAYERS)))

if __name__ == '__main__':
    main()
