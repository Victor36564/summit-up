# SummitUp seasonal recommendation models

This package contains a working experimental recommender, refined data, trained models, held-out evaluation, and review-curation tools. It does not contain a validated good-hike model. None of the trained condition targets passed the exploratory evidence gate on the final temporal test.

## What is already done

- Preserved 500 catalog routes and all 2,375 existing dated observations. No new Google reviews or original review text were collected in this run. Existing source URLs and labels are inherited, not independently reverified.
- Kept absent, present, and unknown separate. Added empty targets for scenic enjoyment, crowding, and trail quality, rather than inventing labels.
- Built planning-time features: trail distance/gain, region, route type, difficulty, season, and historical monthly climate averages. Actual weather on the review date is not a model input.
- Excluded 23 observations from 2020 because no earlier climate years were available; also excluded five observations already marked timing-uncertain. 2,347 observations have usable planning-time features, before target-specific missing-label exclusions.
- Compared balanced logistic regression and Random Forest, selected by validation balanced accuracy, calibrated eligible targets using validation report labels, and tested on later dates. Also ran route-held-out cross-validation within the training era.
- Trained and saved overall favorable-condition, bugs, and mud models. Withheld snow, ice, scenic enjoyment, crowding, and trail-quality models because both classes were not sufficiently represented.
- Implemented JSON input/output for the existing backend, maximum time/distance/gain and difficulty filters, weighted predicted seasonal suitability, text preference matching, verified catalog-feature matching, unknown-target statuses, and reproducible example outputs.

## How this uses ML

The seasonal classifier learns relationships between trail attributes, month, prior climate, and explicit reviewer labels. It predicts a score for an individual hike/month even when that exact combination has no review. This is not a direct lookup of previously observed hike/month ratings.

The final rank combines learned seasonal scores with preference matching. Its weights are a transparent design choice, not learned from user relevance judgments. There is no trained pairwise/listwise ranking model yet. Default component weights are 0.6 seasonal, 0.3 text, and 0.1 verified feature match; unavailable components are omitted and remaining weights normalized. Condition weights are supplied separately in JSON.

The executed text backend is TF-IDF fitted to catalog text. It learns vocabulary statistics but is lexical matching, not pretrained semantic understanding. Optional `sentence_transformer` uses all-MiniLM-L6-v2 for semantic preference matching. Optional BART-MNLI proposes review labels. Both pretrained paths are implemented but were NOT installed, downloaded, or run here. They require the optional dependencies, network access for initial model download, and populated original review text/curated descriptions. The current package is not evidence that the course's second model-type requirement has been completed.

## Run on your Mac or in Colab

Use Python 3.11 or newer. The saved estimators were created with scikit-learn 1.8.0; use the pinned version to load them.

```bash
cd summitup_ml
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python recommend.py --request example_request.json --output my_response.json
python test_contract.py
```

Training is already completed. To reproduce it:

```bash
python train.py
```

The notebook `train_and_integrate.ipynb` also runs training, shows metrics, and calls the recommender. Extract this zip first and point the notebook at the `summitup_ml` directory.

## Connect to your existing app

Use `app_integration.py` as the pattern: instantiate `Recommender` once at server startup and pass the frontend's JSON into `engine.recommend(request_json)`. Catch `ValueError` and return HTTP 400 for invalid inputs. No frontend replacement is included or required.

Inputs:

| Input | Meaning |
|---|---|
| travel_date | Planned date, ISO YYYY-MM-DD. Seasonal predictions are month-level, not exact-day forecasts. |
| as_of | Date the prediction is made. Defaults to today's date. |
| region | One of the catalog's New Zealand regions; no coordinate/radius search is available yet. |
| difficulty | Exact catalog category, case insensitive. |
| max_distance_km / max_elevation_gain_m / max_time_hours | Hard limits. Time ranges use their upper bound. Unknown times cannot satisfy a time limit. |
| preferences_text | Free-text request, matched to available catalog descriptions. Sparse descriptions currently limit this. |
| desired_features | forest, mountain_alpine, lake, waterfall, coastal, river, glacier, views. Only manually verified features can contribute. Unknown features are returned explicitly. |
| condition_weights | Nonnegative weights for overall_good, bugs, mud, snow, ice, scenic_positive, crowded, trail_quality_good. Positive conditions are rewarded; bugs/mud/snow/ice/crowding penalized. |
| allow_experimental | False by default. True lets weak models contribute for a clearly marked research/demo run. |
| top_k | 1–500. |

Outputs include `ranking_score`, `seasonal_suitability_score`, per-target `model_score`, model status, whether the target contributed, unsupported requested conditions/features, source URL, climate scope, and supporting hike/month observation count. Scores are NOT population probabilities or safety judgments. A null score means unavailable, not zero risk. A strict request currently has no seasonal targets that pass the gate; it can still return preference matches, with seasonal scores null. Do not portray those as a validated seasonal ranking.

`example_request.json` explicitly opts into experimental ranking for January 2027. `example_response.json` is its actual output. `seasonal_scores_2027.csv` contains all 500 hikes × 12 months × 3 trained targets, using climate available before 2026-10-01. Do not publish these as validated chances of good trips.

## Evaluation and interpretation

- Training: dates before 2025-01-01.
- Validation/model selection/calibration: 2025-01-01 through 2025-06-30.
- Final temporal test: 2025-07-01 onward. This has very few rows because source observations concentrate in early 2025. The final model was not tuned on this test.
- Training-era route-held-out CV: three folds, no same source route on both sides. This diagnostic does not establish future-season performance.
- Baseline: smoothed region/month label rates fitted on training labels only.
- Gate: at least 10 positive and 10 negative final-test labels, plus better balanced accuracy and Brier score than the seasonal baseline. This is a research gate, not proof of production readiness.
- Calibration is fitted to a selectively labeled review sample. It does not correct selection bias or establish real-world trip probabilities. The same validation split selects the candidate and fits its calibrator; its scores are not independent final evidence.

See `evaluation.json`, `test_predictions.csv`, and `reliability_bins.csv` for exact numbers. Current overall favorable-condition testing has 29 positive and one negative review; balanced accuracy is 0.50. Bug testing has only four rows; Brier error is worse than the seasonal baseline. Mud testing has six positive reports and no negative reports, so balanced accuracy cannot be evaluated.

## Refine the data, then retrain

1. Open the refined Excel workbook's Review curation sheet. Obtain original review text for the cited route, verify the source, and enter exact supporting quotes. Start with a balanced selection across regions, seasons, and favorable/unfavorable experiences; do not select only negative keyword matches. Record the sampling method.
2. Label each dimension 1, 0, or blank. Read `review_label_instructions.txt`. A review can simultaneously be beautiful, muddy, and enjoyable. Actual trip dates require evidence; otherwise retain posting-date uncertainty.
3. Verify catalog features after route replacements. Set `features_reviewed=1` only when an evidence URL supports the current route's features. Never infer a waterfall from an old route's tag.
4. Save Review curation and Hikes as CSVs using the existing headers. Run:

```bash
python import_curated.py --reviews my_review_curation.csv --hikes my_hikes.csv
python train.py
python recommend.py --request example_request.json --output my_response.json
```

The importer accepts reviewed existing observations only. New review IDs require full route/source metadata; add them to `data/observations_source.csv` and rebuild the source data rather than silently inventing joins. Existing prepared labels are retained for unreviewed rows; they remain explicitly flagged as legacy labels, not team-reviewed samples. After reviewing data whose test results you already inspected, obtain a fresh final holdout before making final performance claims.

For pretrained AI assistance after installing optional dependencies:

```bash
python -m pip install -r requirements_optional_ai.txt
python propose_review_labels.py --reviews my_review_curation.csv --output proposals.json
python recommend.py --request example_request.json --text-backend sentence_transformer --output semantic_response.json
```

AI proposals never enter the training dataset automatically. Check each proposal against the original review and add exact evidence quotes. Zero-shot confidence scores are not validated label accuracy. Label accuracy must be checked against a team-authored reference set.

For weather closer to trails, fill `data/hike_locations.csv` with verified coordinates and source URLs. The retrieval script is supplied but has not been executed:

```bash
python fetch_trail_weather.py --locations data/hike_locations.csv --end 2026-09-30
```

Use the resulting weather in `import_curated.py` and retrain. The script checkpoints by hike ID; use a new file if changing its requested date range. Climate retrieval at a coordinate is still a reanalysis proxy, not observed snow/ice on the trail. No verified trail coordinates are currently supplied.

## What you need next

- Complete the required team manual review of at least 500 samples; no row here is newly claimed as manually reviewed.
- Prioritize explicit positive AND negative examples for overall conditions, mud, snow/ice, scenery, crowding, and trail quality. There is no single guaranteed sufficient sample count; track distinct routes and seasonal coverage as well as counts.
- Collect dated 2026+ observations for a meaningful fresh temporal test.
- Populate source-supported catalog descriptions for the semantic recommender.
- Have teammates judge ordered candidate lists for a set of real trip requests. Measure ranking relevance (for example NDCG@10) against those independently authored judgments. Do not manufacture ranking targets from the scoring formula.
- Run the optional pretrained model and document its measured contribution if using it for the course's second model type.

## Technical references

- Calibration: https://scikit-learn.org/stable/modules/calibration.html
- Semantic embeddings: https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html
- Zero-shot review-label proposals: https://huggingface.co/facebook/bart-large-mnli

Files are local and reproducible. The original recovered workbook is unchanged. `prepare_data.py` can regenerate this dataset using that workbook and the original training package, if needed.
