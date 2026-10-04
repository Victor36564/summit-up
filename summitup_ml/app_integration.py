"""Copy this pattern into your existing backend; no new frontend required."""
from recommend import Recommender

# Load once at backend startup, not once per HTTP request.
engine=Recommender(text_backend='tfidf')

def recommendation_handler(request_json):
    # Your existing endpoint deserializes JSON, then calls this function.
    # Catch ValueError at your endpoint boundary and return HTTP 400.
    return engine.recommend(request_json)
