from pathlib import Path
import math
import sys
from typing import Any, TYPE_CHECKING


SUMMITUP_ML_ROOT = Path(__file__).resolve().parents[2] / "summitup_ml"
if str(SUMMITUP_ML_ROOT) not in sys.path:
	sys.path.insert(0, str(SUMMITUP_ML_ROOT))

if TYPE_CHECKING:
	from recommend import Recommender


def load_recommender() -> "Recommender":
	from recommend import Recommender

	return Recommender(root=SUMMITUP_ML_ROOT, text_backend="minilm")


def recommend(recommender: Any, request: dict[str, Any]) -> dict[str, Any]:
	return _json_safe(recommender.recommend(request))


def catalog_options(recommender: Any) -> dict[str, list[str]]:
	return {
		"regions": sorted(recommender.hikes["region"].dropna().astype(str).unique().tolist()),
		"difficulties": sorted(recommender.hikes["difficulty_or_grade"].dropna().astype(str).unique().tolist()),
	}


def catalog_options_from_csv() -> dict[str, list[str]]:
	"""Return filter values without requiring the recommendation runtime to load."""
	import pandas as pd

	hikes = pd.read_csv(SUMMITUP_ML_ROOT / "data" / "hikes.csv")
	return {
		"regions": sorted(hikes["region"].dropna().astype(str).unique().tolist()),
		"difficulties": sorted(hikes["difficulty_or_grade"].dropna().astype(str).unique().tolist()),
	}


def _json_safe(value: Any) -> Any:
	if isinstance(value, dict):
		return {key: _json_safe(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_json_safe(item) for item in value]
	if hasattr(value, "item"):
		return _json_safe(value.item())
	if isinstance(value, float) and not math.isfinite(value):
		return None
	return value