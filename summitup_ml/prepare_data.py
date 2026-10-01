"""Rebuild machine-learning data from the recovered source package and workbook."""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
import openpyxl
from seasonal import ROOT, TARGETS, seasonal_features

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-dir',required=True);parser.add_argument('--workbook',required=True)
    args=parser.parse_args();src=Path(args.source_dir);out=ROOT/'data';out.mkdir(exist_ok=True)
    obs=pd.read_csv(src/'condition_observations.csv');weather=pd.read_csv(src/'regional_weather_daily.csv')
    wb=openpyxl.load_workbook(args.workbook,read_only=True,data_only=True)
    rows=iter(wb['Dataset 1 - 500 Hikes'].values);headers=list(next(rows)[:23])
    cat=pd.DataFrame([list(row[:23]) for row in rows],columns=headers)
    cat=cat[cat.hike_id.astype(str).str.fullmatch(r'NZ\d{3}')].copy()
    assert len(cat)==500 and cat.hike_id.is_unique
    cat['catalog_feature_status']='legacy tags; not reverified after route replacements'
    cat['current_access_status']=np.where(cat.data_status.str.contains('closed',case=False,na=False),'previously marked closed','not checked')
    cat['description_curated']=None
    cat['feature_evidence_url']=None
    cat['features_reviewed']=0
    cat.to_csv(out/'hikes.csv',index=False)
    obs.to_csv(out/'observations_source.csv',index=False)
    weather.to_csv(out/'weather_source.csv',index=False)
    # Remove duplicate route/review keys rather than counting a review twice.
    clean=obs.drop_duplicates(['source_route_key','review_key']).copy()
    for t in TARGETS:
        if t not in clean:clean[t]=np.nan
        assert clean[t].dropna().isin([0,1]).all(),t
    clean['raw_review_text']=None
    clean['actual_trip_date']=None
    clean['manually_reviewed']=0
    clean['label_status']='legacy extracted tags; team review pending'
    x=seasonal_features(clean,weather)
    dates=pd.to_datetime(x.observation_date)
    x['split']=np.select([dates<pd.Timestamp('2025-01-01'),dates<pd.Timestamp('2025-07-01')],['train','validation'],default='test')
    x['usable_for_training']=(x.training_eligible.eq(1)&x.climate_available).astype(int)
    x.to_csv(out/'seasonal_training.csv',index=False)
    cols=['observation_id','hike_id','source_route_key','condition_source_url','observation_date','actual_trip_date',
          'raw_review_text','overall_good','bugs','mud','snow','ice','scenic_positive','crowded','trail_quality_good',
          'evidence_quote','date_verified','manually_reviewed','reviewer_notes']
    curate=clean.reindex(columns=cols)
    curate.to_csv(out/'review_curation.csv',index=False)
    audit={'source_rows':len(obs),'deduplicated_rows':len(clean),'hikes':len(cat),
           'catalog_routes_with_observations':int(clean.hike_id.nunique()),
           'source_files_reverified':False,'google_reviews_included':False,
           'labels':{t:{'positive':int(clean[t].eq(1).sum()),'negative':int(clean[t].eq(0).sum()),'unknown':int(clean[t].isna().sum())} for t in TARGETS},
           'training_rows_with_prior_climate':int(x.usable_for_training.sum()),
           'excluded_no_prior_climate':int((~x.climate_available).sum()),
           'tag_warning':'Legacy terrain/scenery tags are retained but excluded from model features until reverified.'}
    (ROOT/'audit.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
