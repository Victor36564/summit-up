"""Seasonal review-report models. No observed trip-day weather is a predictor."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score, brier_score_loss

ROOT = Path(__file__).resolve().parent
TARGETS = ['overall_good', 'bugs', 'mud', 'snow', 'ice', 'scenic_positive', 'crowded', 'trail_quality_good']
WEATHER = ['temperature_2m_mean', 'precipitation_sum', 'relative_humidity_2m_mean', 'wind_speed_10m_max', 'snowfall_sum']
NUM = ['distance_km', 'elevation_gain_m', 'month_sin', 'month_cos'] + ['climate_' + k for k in WEATHER]
CAT = ['region', 'difficulty_or_grade', 'route_type']
FEATURES = NUM + CAT

def load_weather(root=ROOT):
    regional=pd.read_csv(root/'data/weather_source.csv')
    regional['weather_location_key']=regional.region
    path=root/'data/hike_weather_daily.csv'
    if path.exists():
        trail=pd.read_csv(path)
        trail['weather_location_key']=trail.hike_id
        return pd.concat([regional,trail],ignore_index=True)
    return regional

def seasonal_features(rows, weather, as_of=None):
    """Use complete years before the trip year, also excluding anything after as_of."""
    x = rows.copy()
    dates = pd.to_datetime(x['observation_date'])
    x['month'] = dates.dt.month
    x['month_sin'] = np.sin(2*np.pi*x.month/12)
    x['month_cos'] = np.cos(2*np.pi*x.month/12)
    w = weather.copy(); w['date'] = pd.to_datetime(w.date)
    if 'weather_location_key' not in w:w['weather_location_key']=w.region
    available=set(w.weather_location_key)
    keys=[hid if pd.notna(hid) and hid in available else region for hid,region in zip(x.get('hike_id',pd.Series(index=x.index,dtype=str)),x.region)]
    x['weather_location_key']=keys
    x['climate_scope']=['trail coordinate reanalysis proxy' if key!=region else 'regional settlement proxy' for key,region in zip(keys,x.region)]
    lookup = {}
    for year in sorted(dates.dt.year.unique()):
        cutoff = pd.Timestamp(int(year), 1, 1)
        if as_of is not None:
            cutoff = min(cutoff, pd.Timestamp(as_of))
        prior = w[w.date < cutoff].copy()
        prior['month'] = prior.date.dt.month
        means = prior.groupby(['weather_location_key', 'month'])[WEATHER].mean()
        for key, row in means.iterrows():
            lookup[(int(year), *key)] = row.to_dict()
    for col in WEATHER:
        x['climate_' + col] = [lookup.get((int(d.year), r, int(d.month)), {}).get(col, np.nan)
                                   for d, r in zip(dates, x.weather_location_key)]
    x['climate_available'] = x[['climate_' + k for k in WEATHER]].notna().all(axis=1)
    return x

def make_model(kind):
    prep = ColumnTransformer([
        ('numbers', Pipeline([('impute', SimpleImputer(strategy='median', add_indicator=True)),
                              ('scale', StandardScaler())]), NUM),
        ('categories', Pipeline([('impute', SimpleImputer(strategy='constant', fill_value='unknown')),
                                 ('encode', OneHotEncoder(handle_unknown='ignore'))]), CAT)])
    estimator = (RandomForestClassifier(n_estimators=250, max_depth=6, min_samples_leaf=8,
                 class_weight='balanced_subsample', random_state=42, n_jobs=-1)
                 if kind == 'random_forest' else
                 LogisticRegression(C=0.1, class_weight='balanced', max_iter=2000, random_state=42))
    return Pipeline([('prepare', prep), ('model', estimator)])

def baseline(train, test, target):
    """Smoothed region/month report rate, fitted on training labels only."""
    overall = train[target].mean()
    grouped = train.groupby(['region', 'month'])[target].agg(['sum', 'count'])
    return np.array([(grouped.loc[(r,m),'sum'] + 10*overall)/(grouped.loc[(r,m),'count'] + 10)
                     if (r,m) in grouped.index else overall for r,m in zip(test.region,test.month)])

def metrics(y, p):
    y = np.asarray(y, dtype=int)
    return {'rows':len(y), 'positive':int(y.sum()), 'negative':int((y==0).sum()),
            'balanced_accuracy':float(balanced_accuracy_score(y,p>=0.5)) if len(set(y))==2 else None,
            'roc_auc':float(roc_auc_score(y,p)) if len(set(y))==2 else None,
            'brier':float(brier_score_loss(y,p))}

def counts(part, target):
    return {'rows':len(part), 'positive':int((part[target]==1).sum()), 'negative':int((part[target]==0).sum()),
            'routes':int(part.source_route_key.nunique())}

def apply_calibration(model, calibrator, frame):
    p = model.predict_proba(frame[FEATURES])[:,1]
    if calibrator is not None:
        p = calibrator.predict_proba(np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6))).reshape(-1,1))[:,1]
    return p
