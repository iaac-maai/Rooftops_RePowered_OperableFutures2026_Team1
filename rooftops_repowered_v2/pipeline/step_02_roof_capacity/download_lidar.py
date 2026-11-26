"""Download the public ICGC 432583 tile and inspect acquisition GPS times."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys

from pipeline.common import ROOT
import laspy
import numpy as np
import shapely
from download_datasets import fetch
from pipeline.common import now,sha256,write_json
from pipeline.step_02_roof_capacity.adapter import load_geometry

URL='https://datacloud.icgc.cat/datacloud/lidar-territorial/vigent/laz_unzip/full10km4358/lidar-territorial-full1km432583.laz'


def main():
    out=ROOT/'datasets/raw/roof_capacity/A160/lidar'
    out.mkdir(parents=True,exist_ok=True)
    path=out/'lidar-territorial-full1km432583.laz'
    report=ROOT/'reports/roof_capacity/A160'
    if not path.exists():
        partial=path.with_suffix('.laz.part')
        fetch(URL,partial,report/'lidar_download.log',1800)
        partial.replace(path)
    print('Tile downloaded:',path.stat().st_size,flush=True)
    fp=load_geometry('datasets/inputs/roof_capacity/A160_footprint.geojson','EPSG:4326')
    x0,y0,x1,y1=fp.bounds
    rows=[]; low=np.inf; high=-np.inf
    with laspy.open(path) as reader:
        header=reader.header
        info={'url':URL,'retrieved_utc':now(),'sha256':sha256(path),'bytes':path.stat().st_size,
              'point_count':header.point_count,'point_format':header.point_format.id,
              'creation_date_not_survey_date':str(header.creation_date),
              'gps_time_type':str(header.global_encoding.gps_time_type),'crs':str(header.parse_crs()),
              'bounds':[header.mins.tolist(),header.maxs.tolist()]}
        adjusted=int(header.global_encoding.gps_time_type)==1
        for chunk in reader.chunk_iterator(1_000_000):
            x,y,z=map(np.asarray,(chunk.x,chunk.y,chunk.z))
            gps=np.asarray(chunk.gps_time)
            valid=np.isfinite(gps)&(gps>0)
            if valid.any():low=min(low,float(gps[valid].min()));high=max(high,float(gps[valid].max()))
            keep=(x>=x0)&(x<=x1)&(y>=y0)&(y<=y1)
            indices=np.flatnonzero(keep)
            if indices.size:
                indices=indices[shapely.contains_xy(fp,x[indices],y[indices])]
                rows.append(np.column_stack([x[indices],y[indices],z[indices],np.asarray(chunk.classification)[indices],gps[indices]]))
    data=np.vstack(rows)
    np.savez_compressed(out/'A160_points.npz',points=data)
    info['clipped_points']=len(data)
    info['class_counts']={str(int(c)):int((data[:,3]==c).sum()) for c in np.unique(data[:,3])}
    info['gps_time_minmax']=[low,high]
    info['roof_gps_time_minmax']=[float(data[:,4].min()),float(data[:,4].max())]
    if adjusted:
        def convert(value):return (datetime(1980,1,6,tzinfo=timezone.utc)+timedelta(seconds=float(value)+1e9-18)).isoformat()
        info['tile_acquisition_utc']=[convert(low),convert(high)]
        info['roof_acquisition_utc']=[convert(data[:,4].min()),convert(data[:,4].max())]
        info['date_conversion']='LAS adjusted-standard GPS seconds +1e9, epoch 1980-01-06; subtract GPS-UTC leap offset 18 seconds for post-2017 surveys.'
    write_json(report/'lidar_acquisition.json',info)
    print(json.dumps(info,indent=2),flush=True)


if __name__=='__main__':main()
