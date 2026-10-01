"""Optional real weather retrieval after verifying trail coordinates. Not executed in this package."""
import argparse,json,time,urllib.request,urllib.parse
import pandas as pd
from seasonal import ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--locations',required=True);p.add_argument('--start',default='2020-01-01');p.add_argument('--end',required=True);a=p.parse_args()
    loc=pd.read_csv(a.locations);loc=loc[loc.coordinates_verified.eq(1)]
    if loc.empty:raise ValueError('No verified coordinates supplied; do not substitute invented coordinates.')
    path=ROOT/'data/hike_weather_daily.csv';existing=pd.read_csv(path) if path.exists() else pd.DataFrame()
    done=set(existing.hike_id) if len(existing) else set()
    variables=['temperature_2m_mean','precipitation_sum','relative_humidity_2m_mean','wind_speed_10m_max','snowfall_sum']
    for row in loc.itertuples():
        if row.hike_id in done:continue
        if pd.isna(row.latitude) or pd.isna(row.longitude):raise ValueError('Missing coordinate: '+row.hike_id)
        params={'latitude':row.latitude,'longitude':row.longitude,'start_date':a.start,'end_date':a.end,
                'daily':','.join(variables),'timezone':'Pacific/Auckland','models':'era5'}
        url='https://archive-api.open-meteo.com/v1/archive?'+urllib.parse.urlencode(params)
        # Regional source used UTC days; trail requests intentionally use NZ local days.
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url,timeout=60) as response:data=json.load(response)
                break
            except Exception:
                if attempt==2:raise
                time.sleep(2**attempt)
        new=pd.DataFrame(data['daily']).rename(columns={'time':'date'})
        new['hike_id']=row.hike_id;new['latitude']=row.latitude;new['longitude']=row.longitude
        new['source_url']=url;new['timezone']='Pacific/Auckland';new['source']='Open-Meteo ERA5 reanalysis'
        existing=pd.concat([existing,new],ignore_index=True);existing.to_csv(path,index=False)
        print('Saved',row.hike_id,len(new),'weather days');time.sleep(.25)
    print('Run import_curated.py or rebuild seasonal_features with load_weather(), then retrain. A coordinate proxy is still not observed trail conditions.')
if __name__=='__main__':main()
