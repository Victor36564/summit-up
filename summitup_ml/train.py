"""Train seasonal models; 2025 H2+ is untouched final temporal test."""
import json, joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.linear_model import LogisticRegression
from seasonal import ROOT,TARGETS,FEATURES,make_model,baseline,metrics,counts,apply_calibration

def main():
    df=pd.read_csv(ROOT/'data/seasonal_training.csv');df=df[df.usable_for_training.eq(1)]
    (ROOT/'models').mkdir(exist_ok=True)
    report={};predictions=[];reliability=[]
    for target in TARGETS:
        part=df[df[target].notna()].copy()
        train=part[part.split.eq('train')];val=part[part.split.eq('validation')];test=part[part.split.eq('test')]
        result={'label_meaning':'explicit reviewer report, conditional on reporting; not objective trip probability',
                'counts':{name:counts(p,target) for name,p in [('train',train),('validation',val),('test',test)]},
                'status':'withheld','calibrated':False}
        if min(train[target].eq(0).sum(),train[target].eq(1).sum())<8:
            result['reason']='Insufficient training examples of both classes (minimum 8 each).';report[target]=result;continue
        candidates={};models={}
        for kind in ['logistic','random_forest']:
            model=make_model(kind).fit(train[FEATURES],train[target].astype(int));models[kind]=model
            if len(val): candidates[kind]=metrics(val[target],apply_calibration(model,None,val))
        # Balanced accuracy selects the candidate; never select on the final test.
        kind=max(candidates,key=lambda k:candidates[k]['balanced_accuracy'] if candidates[k]['balanced_accuracy'] is not None else -1) if candidates else 'random_forest'
        model=models[kind];cal=None
        if min(val[target].eq(0).sum(),val[target].eq(1).sum())>=10:
            # This validation set also selected the model. Its scores are not reported as independent evidence.
            p=apply_calibration(model,None,val);logits=np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6)))
            cal=LogisticRegression(C=1,random_state=42).fit(logits.reshape(-1,1),val[target].astype(int))
        result.update({'candidate_validation':candidates,'selected_model':kind,'calibrated':cal is not None,
                       'calibration_note':'Sigmoid fitted to validation report labels; population trip probability remains unvalidated.',
                       'status':'experimental'})
        if len(test):
            p=apply_calibration(model,cal,test);b=baseline(train,test,target)
            result['temporal_test']=metrics(test[target],p);result['seasonal_baseline']=metrics(test[target],b)
            for row,score,base in zip(test.itertuples(),p,b):
                predictions.append({'observation_id':row.observation_id,'route':row.source_route_key,'target':target,
                                    'actual':int(getattr(row,target)),'model_score':float(score),'baseline_score':float(base)})
            for low in np.arange(0,1,.2):
                mask=(p>=low)&(p<(low+.2) if low<.8 else p<=1)
                if mask.any():reliability.append({'target':target,'bin_low':float(low),'rows':int(mask.sum()),
                    'mean_score':float(p[mask].mean()),'observed_report_rate':float(test[target].to_numpy()[mask].mean())})
        # Independent diagnostic: no same route across train and test, training era only.
        if min(train.loc[train[target].eq(c),'source_route_key'].nunique() for c in [0,1])>=3:
            cv=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=42);oof=np.full(len(train),np.nan)
            for tr,te in cv.split(train[FEATURES],train[target],train.source_route_key):
                assert not set(train.iloc[tr].source_route_key)&set(train.iloc[te].source_route_key)
                if train.iloc[tr][target].nunique()<2:continue
                m=make_model(kind).fit(train.iloc[tr][FEATURES],train.iloc[tr][target].astype(int))
                oof[te]=apply_calibration(m,None,train.iloc[te])
            valid=~np.isnan(oof)
            if valid.any():result['unseen_route_cv']=metrics(train.loc[valid,target],oof[valid])
        mt=result.get('temporal_test',{});bt=result.get('seasonal_baseline',{})
        supported=(mt.get('negative',0)>=10 and mt.get('positive',0)>=10 and mt.get('balanced_accuracy',0) is not None
                   and mt['balanced_accuracy']>bt['balanced_accuracy'] and mt['brier']<bt['brier'])
        result['passes_exploratory_gate']=bool(supported)
        result['production_validated']=False
        result['limitations']=['selective reporting','posting dates used','regional climate proxies',
                               'legacy labels not team verified','ranking relevance not evaluated']
        joblib.dump({'model':model,'calibrator':cal,'metadata':result},ROOT/'models'/f'{target}.joblib')
        report[target]=result
    (ROOT/'evaluation.json').write_text(json.dumps(report,indent=2))
    pd.DataFrame(predictions).to_csv(ROOT/'test_predictions.csv',index=False)
    pd.DataFrame(reliability).to_csv(ROOT/'reliability_bins.csv',index=False)
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
