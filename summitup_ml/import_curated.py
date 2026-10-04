"""Ingest team-reviewed review labels, then rebuild planning-time features."""
import argparse
import pandas as pd
from seasonal import ROOT,TARGETS,seasonal_features,load_weather

def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',required=True);p.add_argument('--hikes');a=p.parse_args()
    reviewed=pd.read_csv(a.reviews)
    if reviewed.observation_id.duplicated().any():raise ValueError('Duplicate observation IDs')
    accepted=reviewed[reviewed.manually_reviewed.eq(1)].copy()
    if accepted.empty:raise ValueError('No manually reviewed rows to import')
    for col in ['raw_review_text','evidence_quote','condition_source_url']:
        if accepted[col].isna().any() or accepted[col].astype(str).str.strip().eq('').any():raise ValueError('Reviewed rows need '+col)
    for t in TARGETS:
        if not accepted[t].dropna().isin([0,1]).all():raise ValueError('Labels must be 0, 1, or blank: '+t)
    src=pd.read_csv(ROOT/'data/seasonal_training.csv').set_index('observation_id')
    for col in ['raw_review_text','actual_trip_date','label_status','label_source','condition_source_url','evidence_quote']:
        if col not in src:src[col]=None
        src[col]=src[col].astype(object)
    if not set(accepted.observation_id)<=set(src.index):raise ValueError('New observation IDs require source and route metadata; add them to observations_source first.')
    # Assignment preserves reviewed unknowns (blank) instead of retaining unverified old labels.
    for row in accepted.to_dict('records'):
        oid=row['observation_id']
        for col in TARGETS+['raw_review_text','actual_trip_date','manually_reviewed','condition_source_url','evidence_quote']:
            src.loc[oid,col]=row[col]
        src.loc[oid,'label_status']='team reviewed'
        src.loc[oid,'label_source']='team-reviewed original review; see condition_source_url and evidence_quote'
        if row.get('date_verified')==1:
            if pd.isna(row['actual_trip_date']):raise ValueError('Verified dates require actual_trip_date')
            src.loc[oid,'observation_date']=pd.Timestamp(row['actual_trip_date']).date().isoformat()
            src.loc[oid,'date_basis']='verified actual trip date'
            src.loc[oid,'training_eligible']=1
    x=seasonal_features(src.reset_index(),load_weather())
    dates=pd.to_datetime(x.observation_date)
    x['split']='test';x.loc[dates<'2025-07-01','split']='validation';x.loc[dates<'2025-01-01','split']='train'
    x['usable_for_training']=(x.training_eligible.eq(1)&x.climate_available).astype(int)
    x.to_csv(ROOT/'data/seasonal_training.csv',index=False)
    if a.hikes:
        cat=pd.read_csv(a.hikes)
        if len(cat)!=500 or cat.hike_id.nunique()!=500:raise ValueError('Expected 500 unique catalog hikes')
        verified=cat.features_reviewed.eq(1)
        if cat.loc[verified,'feature_evidence_url'].isna().any():raise ValueError('Verified features require evidence URLs')
        cat.to_csv(ROOT/'data/hikes.csv',index=False)
    print('Imported',len(accepted),'reviewed observations. Run train.py again. Previously inspected test data is no longer an untouched holdout; collect a fresh future test for final validation.')
if __name__=='__main__':main()
