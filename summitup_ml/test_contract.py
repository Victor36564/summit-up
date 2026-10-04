"""Meaningful invariants for future planning, unknown labels, and API output."""
import unittest,json
import pandas as pd
from seasonal import ROOT,WEATHER,seasonal_features
from recommend import Recommender

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=Recommender()
    def test_future_weather_cannot_leak(self):
        rows=pd.DataFrame([{'region':'Otago','observation_date':'2027-01-15'}])
        weather=pd.read_csv(ROOT/'data/weather_source.csv')
        first=seasonal_features(rows,weather,as_of='2026-10-01')
        future=weather.iloc[:1].copy();future['date']='2027-01-15';future['region']='Otago'
        future[WEATHER]=999999
        second=seasonal_features(rows,pd.concat([weather,future]),as_of='2026-10-01')
        pd.testing.assert_frame_equal(first,second)
    def test_unsupported_labels_stay_null(self):
        q=json.loads((ROOT/'example_request.json').read_text());result=self.engine.recommend(q)
        self.assertTrue(result['results'])
        for hike in result['results']:
            for t in ['snow','ice','scenic_positive','crowded','trail_quality_good']:
                self.assertIsNone(hike['conditions'][t]['model_score'])
            self.assertLessEqual(hike['distance_km'],10)
            self.assertEqual(hike['region'],'Otago')
        json.dumps(result,allow_nan=False)
    def test_invalid_requests(self):
        with self.assertRaises(ValueError):self.engine.recommend({'travel_date':'2025-01-01','as_of':'2026-10-01'})
        with self.assertRaises(ValueError):self.engine.recommend({'travel_date':'2027-01-01','condition_weights':{'bugs':-1}})
    def test_no_match(self):
        r=self.engine.recommend({'travel_date':'2027-01-01','max_distance_km':0})
        self.assertEqual(r['status'],'no_matches')
if __name__=='__main__':unittest.main()
