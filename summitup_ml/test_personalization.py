"""Tests use actual pretrained vectors; no fake embeddings or synthetic training data."""
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
try:
    from .recommend import Recommender
    from .seasonal import ROOT
except ImportError:
    from recommend import Recommender
    from seasonal import ROOT

class PersonalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Recommender()
        cls.lakes=cls.engine.hikes[cls.engine.hikes.name.str.contains('Lake',case=False)].head(4).hike_id.tolist()
        cls.coast=cls.engine.hikes[cls.engine.hikes.name.str.contains('Beach|Coast',case=False)].head(4).hike_id.tolist()

    def query(self,ids):return {'travel_date':'2027-01-15','as_of':'2026-10-04','max_distance_km':10,
                               'saved_hike_ids':ids,'allow_experimental':True,'top_k':20}

    def test_real_vectors(self):
        self.assertEqual(self.engine.vectors.shape,(500,384))
        np.testing.assert_allclose(np.linalg.norm(self.engine.vectors,axis=1),1,atol=1e-5)
        self.assertGreater(float(np.std(self.engine.vectors)),.001)

    def test_different_saves_change_rank(self):
        a=self.engine.recommend(self.query(self.lakes));b=self.engine.recommend(self.query(self.coast))
        self.assertEqual(a['personalization']['model_category'],'off-the-shelf')
        self.assertNotEqual([r['hike_id'] for r in a['results']],[r['hike_id'] for r in b['results']])
        self.assertTrue(all(r['personalization_used'] for r in a['results']))
        self.assertFalse(set(self.lakes)&{r['hike_id'] for r in a['results']})

    def test_duplicate_saves_have_no_extra_weight(self):
        a,ma=self.engine.personalizer.profile(self.lakes)
        b,mb=self.engine.personalizer.profile(self.lakes+self.lakes)
        np.testing.assert_allclose(a,b);self.assertEqual(ma['saved_examples_used'],mb['saved_examples_used'])

    def test_unsaving_returns_cold_start(self):
        self.engine.recommend(self.query(self.lakes))
        response=self.engine.recommend(self.query([]))
        self.assertEqual(response['personalization']['status'],'cold_start')
        self.assertTrue(all(r['personalization_score'] is None for r in response['results']))

    def test_unknown_ids_are_not_fabricated(self):
        result=self.engine.recommend(self.query(['NZ999']))
        self.assertEqual(result['personalization']['status'],'cold_start')
        self.assertEqual(result['personalization']['unresolved_saved_ids'],['NZ999'])

    def test_external_saved_metadata(self):
        q=self.query([]);q['saved_hikes']=[{'place_id':'google-saved-example','name':'Example lake walk',
                                         'address':'New Zealand','metrics':{'difficulty':'Easy','length_km':3}}]
        result=self.engine.recommend(q)
        self.assertEqual(result['personalization']['external_saved_count'],1)
        self.assertEqual(result['personalization']['saved_catalog_hike_ids'],[])

    def test_user_profiles_do_not_leak(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda ids:self.engine.recommend(self.query(ids)),[self.lakes,self.coast]))
        self.assertEqual(responses[0]['personalization']['saved_catalog_hike_ids'],sorted(self.lakes))
        self.assertEqual(responses[1]['personalization']['saved_catalog_hike_ids'],sorted(self.coast))

    def test_unreviewed_tags_excluded(self):
        from personalization import catalog_document
        row={'name':'Test trail','region':'Otago','features_reviewed':0,'waterfall':1,'description_curated':'Glacier views'}
        text=catalog_document(row)
        self.assertNotIn('waterfall',text);self.assertNotIn('Glacier',text)

if __name__=='__main__':unittest.main()
