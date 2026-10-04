# SummitUp training results

Built on October 1, 2026. This run trained seasonal reviewer-report models and produced an experimental recommender. It did not validate a dependable good-hike ranking.

## What changed

The refined dataset keeps 500 hikes and 2,375 source observations, preserves unknown labels, adds explicit curation fields, and separates historical seasonal climate from trip-day weather. The 2020 rows lack prior climate; five timing-uncertain rows remain excluded. There are 2,347 usable rows before missing target labels are excluded.

Trail tags inherited after route replacements are marked unverified and cannot silently satisfy user feature preferences. Snow, ice, scenery, crowding, and trail-quality predictions are unavailable rather than fabricated.

## Actual held-out results

| Target | Selected model | Later test observations | Balanced accuracy | Seasonal baseline | Result |
|---|---|---:|---:|---:|---|
| overall_good | logistic | 30 (29 positive, 1 negative) | 50.0% | 50.0% | Did not pass |
| bugs | random_forest | 4 (3 positive, 1 negative) | 66.7% | 50.0% | Did not pass |
| mud | random_forest | 6 (6 positive, 0 negative) | Not evaluable | Not evaluable | Did not pass |

The overall model mostly predicts favorable reports. It does not distinguish good/bad experiences well on the tiny final test. Bug probabilities have worse Brier error than the seasonal baseline. Mud has no negative final-test examples, so discrimination cannot be evaluated. These results supersede the old package’s route-held-out 67.8% bug result for this different, future-planning evaluation.

The models do change their scores across months and hikes, so they perform learned prediction rather than a hike/month lookup. That alone is not evidence of useful recommendations. The rank combines those model outputs with preferences; the weighting itself is not a learned ranking model.

## App handoff

Load Recommender once in the backend. Pass date, region, distance/time/difficulty limits, preference text, desired features, and condition weights. Return ordered hike IDs and model statuses using the provided JSON contract. The sample opts into experimental models. Strict mode excludes every seasonal model currently because none passes the evidence gate.

The executed text matcher is TF-IDF. Pretrained semantic matching and AI review-label proposal code are included but were not run; the required original review text and optional dependencies are absent.

## What Arin needs next

1. Obtain original dated review text, including unfavorable and favorable experiences across seasons. Check route identity, actual trip dates when available, and exact evidence quotes. Do not label silence as absence.
2. Complete the team’s required manual curation. Verify scenic/terrain descriptions and current trail identities. Import the approved labels, then retrain with the included code/notebook.
3. Populate verified trail coordinates if improving regional climate proxies; use the supplied weather retrieval script. It has not yet been run.
4. Collect a fresh later-season test with enough positive and negative examples across routes. Label reviewers’ ranking judgments for realistic trip requests and evaluate the recommendation order.
5. Run and evaluate a pretrained semantic or review-label model if documenting the course’s second model type.

Detailed reproducible instructions and exact metrics are included in the training package README.md and evaluation.json.
