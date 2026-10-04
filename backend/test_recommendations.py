import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router


class RecommendationApiTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.state.recommender = object()
        self.client = TestClient(self.app)

    def test_successful_inference_returns_real_shape(self):
        payload = {
            "travel_date": "2027-01-15",
            "allow_experimental": True,
            "top_k": 1,
        }
        response_body = {
            "status": "experimental",
            "travel_date": "2027-01-15",
            "as_of": "2026-10-04",
            "text_backend": "tfidf",
            "candidates": 1,
            "prediction_meaning": "reviewer reports",
            "ranking_validated": False,
            "results": [],
        }
        with patch("api.routes.recommend", return_value=response_body):
            response = self.client.post("/api/recommendations", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "experimental")

    def test_invalid_request_is_rejected(self):
        response = self.client.post("/api/recommendations", json={"travel_date": "not-a-date"})
        self.assertEqual(response.status_code, 422)

    def test_no_matches_is_supported(self):
        payload = {"travel_date": "2027-01-15", "allow_experimental": True}
        with patch("api.routes.recommend", return_value={"status": "no_matches", "results": [], "request": payload}):
            response = self.client.post("/api/recommendations", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "no_matches")

    def test_unsupported_prediction_can_be_null(self):
        payload = {"travel_date": "2027-01-15", "allow_experimental": True}
        response_body = {
            "status": "experimental",
            "travel_date": "2027-01-15",
            "as_of": "2026-10-04",
            "text_backend": "tfidf",
            "candidates": 1,
            "prediction_meaning": "reviewer reports",
            "ranking_validated": False,
            "results": [{
                "hike_id": "NZ001", "name": "Example", "region": "Otago",
                "conditions": {"snow": {"model_score": None, "status": "withheld: insufficient labels", "used_in_ranking": False}},
            }],
        }
        with patch("api.routes.recommend", return_value=response_body):
            response = self.client.post("/api/recommendations", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["results"][0]["conditions"]["snow"]["model_score"])


if __name__ == "__main__":
    unittest.main()