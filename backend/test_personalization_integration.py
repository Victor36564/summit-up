"""Real MiniLM inference through existing routes and isolated saved storage."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from api.routes import router
from database import Base, get_db
from models.model import load_recommender

class PersonalizationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.model = load_recommender()
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        app = FastAPI(); app.include_router(router); app.state.recommender = self.model
        def db():
            with Session(self.engine) as session: yield session
        app.dependency_overrides[get_db] = db
        self.client = TestClient(app)
        self.payload = {'travel_date': f'{date.today().year+1}-01-15', 'max_distance_km': 10, 'top_k': 20}
        self.lakes = self.model.hikes[self.model.hikes.name.str.contains('Lake', case=False)].head(4).hike_id.tolist()
        self.coast = self.model.hikes[self.model.hikes.name.str.contains('Beach|Coast', case=False)].head(4).hike_id.tolist()
    def tearDown(self): self.client.close(); self.engine.dispose()
    def recommend(self, sid, **extra):
        r = self.client.post('/api/recommendations', headers={'X-Session-ID': sid}, json={**self.payload, **extra})
        self.assertEqual(r.status_code, 200, r.text); return r.json()
    def save(self, sid, hid, saved=True):
        r = self.client.post('/api/saved', headers={'X-Session-ID': sid}, json={'catalog_hike_id': hid, 'name': self.model.hikes.set_index('hike_id').loc[hid, 'name'], 'saved': saved})
        self.assertEqual(r.status_code, 200, r.text)
    def test_saving_removing_and_concurrent_session_isolation(self):
        cold = self.recommend('lake-session')
        self.assertEqual(cold['personalization']['status'], 'cold_start')
        for hid in self.lakes: self.save('lake-session', hid)
        for hid in self.coast: self.save('coast-session', hid)
        with ThreadPoolExecutor(max_workers=2) as pool:
            lake, coast = list(pool.map(self.recommend, ['lake-session', 'coast-session']))
        self.assertEqual(lake['text_backend'], 'minilm')
        self.assertEqual(lake['personalization']['saved_catalog_hike_ids'], sorted(self.lakes))
        self.assertEqual(coast['personalization']['saved_catalog_hike_ids'], sorted(self.coast))
        self.assertNotEqual([r['hike_id'] for r in lake['results']], [r['hike_id'] for r in coast['results']])
        self.assertNotEqual([r['hike_id'] for r in cold['results']], [r['hike_id'] for r in lake['results']])
        self.assertFalse(set(self.lakes) & {r['hike_id'] for r in lake['results']})
        self.save('lake-session', self.lakes[0])
        self.assertEqual(self.recommend('lake-session')['personalization']['saved_examples_used'], 4)
        self.save('lake-session', self.lakes[0], False)
        partial = self.recommend('lake-session')
        self.assertEqual(partial['personalization']['saved_examples_used'], 3)
        self.assertNotIn(self.lakes[0], partial['personalization']['saved_catalog_hike_ids'])
        for hid in self.lakes[1:]: self.save('lake-session', hid, False)
        restored = self.recommend('lake-session')
        self.assertEqual(restored['personalization'], cold['personalization'])
        self.assertEqual([r['hike_id'] for r in restored['results']], [r['hike_id'] for r in cold['results']])
        for before, after in zip(cold['results'], restored['results']):
            self.assertAlmostEqual(before['ranking_score'], after['ranking_score'], places=12)
            self.assertIsNone(after['personalization_score'])
        unchanged = self.recommend('coast-session')
        self.assertEqual(unchanged['personalization'], coast['personalization'])
        self.assertEqual([r['hike_id'] for r in unchanged['results']], [r['hike_id'] for r in coast['results']])
    def test_response_contract_and_unknown_evidence(self):
        result = self.recommend('new-session', desired_features=['lake'])
        for r in result['results']:
            self.assertIn('lake', r['unknown_requested_features'])
            for t in ['snow', 'ice', 'scenic_positive', 'crowded', 'trail_quality_good']:
                self.assertIsNone(r['conditions'][t]['model_score'])
        none = self.recommend('new-session', max_distance_km=0)
        self.assertEqual(none['status'], 'no_matches'); self.assertIn('request', none)
        self.assertNotIn('saved_hikes', none['request'])
        r = self.client.post('/api/recommendations', json={**self.payload, 'saved_hikes': [{'hike_id': self.lakes[0]}]})
        self.assertEqual(r.status_code, 422)
        r = self.client.post('/api/recommendations', headers={'X-Session-ID': 'bad/session'}, json=self.payload)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get('/api/recommendations/options').status_code, 200)
        filtered = self.recommend('new-session', region='Otago', preferences_text='quiet lake', max_elevation_gain_m=500)
        self.assertTrue(filtered['results'])
        for hike in filtered['results']:
            self.assertEqual(hike['region'], 'Otago')
            self.assertLessEqual(hike['distance_km'], 10)
            self.assertLessEqual(hike['elevation_gain_m'], 500)
            self.assertIsNotNone(hike['text_similarity'])
        invalid = self.client.post('/api/recommendations', json={**self.payload, 'personalization_weight': -1})
        self.assertEqual(invalid.status_code, 422)
    def test_external_metadata_and_anonymous_cold_start(self):
        r = self.client.post('/api/saved', headers={'X-Session-ID': 'external'}, json={'place_id': 'google-example', 'name': 'Example lake walk'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.recommend('external')['personalization']['external_saved_count'], 1)
        removed = self.client.post('/api/saved', headers={'X-Session-ID': 'external'}, json={'place_id': 'google-example', 'name': 'Example lake walk', 'saved': False})
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.recommend('external')['personalization']['status'], 'cold_start')
        self.save('anonymous', self.lakes[0])
        r = self.client.post('/api/recommendations', json=self.payload)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['personalization']['status'], 'cold_start')
