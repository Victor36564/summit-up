# SummitUp frontend integration handoff

Copy the prompt below into your frontend coding assistant. Backend/ML changes are uncommitted in the `off-the-shelf` checkout; frontend files have been restored and have no diff. Your partner handles merging later.

## Prompt for the frontend coding assistant

You are integrating the existing SummitUp React frontend with saved-hike personalization that is already implemented in its FastAPI backend and ML runtime.

### Scope and Git restrictions

First report your working directory and current branch using read-only commands. Work only in the current local checkout and branch. Do not stage, commit, push, pull, fetch, merge, rebase, checkout, switch, reset, clean, stash, create branches/worktrees, or perform equivalent operations through tools/APIs. Leave changes uncommitted. Inspect current local files before changing them and preserve existing work. If another operation is necessary, explain it and wait for explicit permission.

Implement only the frontend integration and its relevant tests/documentation. Preserve existing routes, layouts, components, provider integration, and database/API conventions. Do not replace the frontend or ML folder. The backend/ML changes are already implemented; investigate any contract mismatch before changing backend code.

Read these existing files first:
- `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/App.tsx`, `frontend/src/styles.css`
- `backend/api/routes.py`, `backend/schemas.py`, `backend/database.py`
- `backend/test_personalization_integration.py`
- `summitup_ml/recommend.py`, `summitup_ml/personalization.py`

### Existing backend contract

Keep these endpoints:
- `GET /api/recommendations/options`: returns `regions` and `difficulties`; preserve dropdown handling.
- `POST /api/recommendations`: existing trip body plus optional personalization controls. Do NOT change it to `/api/recommendations/personalized`; that separate ZIP adapter was not adopted.
- `GET /api/saved`: returns saves for the current session, from both existing save tables.
- `POST /api/saved`: existing save/remove payload, with `saved: true` to save and `saved: false` to remove.

The existing request helper sends `X-Session-ID`. It reads or creates an anonymous browser UUID in localStorage under `summit-up-session`. Reuse it for all requests; do not generate a new ID per request, submit someone else's ID, or introduce a separate session mechanism.

The recommendation route loads that session's saved history server-side on every request. Never send `saved_hikes`, `saved_hike_ids`, user IDs, or session IDs in the JSON body; unknown body fields are rejected with HTTP 422. Missing headers or the literal `anonymous` session use cold-start recommendations, without reading shared anonymous saves. Invalid header syntax returns 400. This browser header is an anonymous identity convention, not authentication.

Example recommendation body:

```json
{
  "travel_date": "2027-01-15",
  "region": "Otago",
  "max_distance_km": 10,
  "preferences_text": "quiet lake walks",
  "desired_features": ["lake"],
  "condition_weights": {"overall_good": 1, "bugs": 0.8, "mud": 0.5},
  "allow_experimental": true,
  "top_k": 10,
  "personalization_weight": 0.4,
  "exclude_saved": true
}
```

Choose a current/future date in the actual UI. Existing date, region, difficulty, maximum distance/elevation/time, text, feature, and condition-weight fields still work. `personalization_weight` defaults to 0.4 and must be finite/nonnegative. `exclude_saved` defaults to true. Weight zero omits personalization from ranking but does not disable saved-hike exclusion; `exclude_saved: false` is a separate control. A new settings UI is optional, not required for automatic personalization. Preserve the existing API's `allow_experimental: true` convention: it is currently a Literal[True], so sending false is rejected even though the lower-level ML runtime supports strict mode.

Successful responses preserve all existing top-level and result fields, with `text_backend: "minilm"` and these additive fields:

```ts
type Personalization = {
  status: "cold_start" | "personalized" | "unusable_profile" | "disabled";
  saved_examples_used: number;
  saved_catalog_hike_ids?: string[];
  saved_catalog_count?: number;
  external_saved_count?: number;
  unresolved_saved_ids?: string[];
  matching_methods?: string[];
  model_category?: string;
  model_id?: string;
  revision?: string;
  profile_method?: string;
  catalog_text_status?: string;
  rank_quality_validated?: boolean;
};
// Add to successful and no_matches responses:
// personalization: Personalization
// Add to each recommendation result:
// personalization_score: number | null
// personalization_used: boolean
// similar_saved_hike: { hike_id: string; name: string } | null
```

Treat the fields defensively for compatibility with old/mock responses. `no_matches` still returns `status: "no_matches"`, `results: []`, `request`, and personalization metadata; the echoed request excludes internal saved histories. Do not assume every response has ranking/date fields.

Personalization uses bundled pretrained MiniLM embeddings of catalog saves and available external saved metadata. Saved profiles are recomputed per request; saving does not retrain network weights. Catalog saves are excluded by default. Unknown IDs remain unresolved. External saves only exclude a catalog hike when they can be matched to it; do not hide candidates by fuzzy guesses.

### Required frontend work

1. Extend TypeScript request/response types to describe the additive fields above. Preserve the discriminated response union and nullable values.
2. Correct saved-item types: `place_id` may be null/absent for catalog-only saves. Keep Google `Trail` identity requirements where appropriate, but do not model all `SavedTrail` objects as having a nonnull Google place ID.
3. Keep recommendation calls on the existing endpoint. Retain the last submitted trip request. After a successful save or removal, re-request recommendations with those choices and the existing session header. Do not issue a recommendation request before the user has submitted trip choices. Do not refresh after failed save/removal operations. A save/removal succeeds independently of any subsequent refresh error.
4. Prevent older in-flight recommendation responses from overwriting newer results. Use an abort controller or request sequence. Keep loading/error handling consistent, and avoid briefly displaying a result saved moments ago after a refresh finishes. Use server results as the ranking source of truth.
5. Add a concise personalization indicator to the existing recommendation panel, e.g. “Personalized from 4 saved hikes.” For cold start, explain that saves personalize future recommendations. Distinguish unusable profiles from successful personalization. Keep empty-history recommendations usable.
6. Display a similarity/affinity explanation where appropriate using `personalization_used`, `personalization_score`, and `similar_saved_hike`. Existing `reasons` already include saved-hike explanations, so avoid redundant text. Never label similarity as a chance of a good/safe hike.
7. Ensure both kinds of saves can be removed from the existing vault and that removal refreshes recommendations. For a recommendation save, send `catalog_hike_id: result.hike_id`, its name, and available metrics; for removal, send the stored identity and `saved: false` through the same endpoint. Preserve `catalog_hike_id` when a saved record also has a Google place ID.
8. Use stable saved-item keys/identity comparisons that handle both catalog IDs and Google place IDs. Do not compare null Google IDs as if they identified the same trail. Do not use numeric database `id` alone across both save tables: the IDs can overlap.
9. Catalog-only saved cards must not call `/api/trails/details/null` or `/undefined`. Resolve Google details through the existing name-search flow, with an honest unavailable state if that enrichment cannot be verified. Do not invent coordinates, IDs, or scenery evidence. Use accessible separate buttons for opening and removing; avoid nested buttons.
10. Keep the current frontend structure and visual style. No unrelated redesign, dependency upgrades, provider changes, or account system.

### Evidence and limitations to preserve

Seasonal code, the three saved seasonal models, and catalog/climate/support CSVs are unchanged. Seasonal rankings remain experimental, `ranking_validated` remains false, and scores are not validated trip probabilities or safety guarantees. Snow, ice, scenic-positive, crowded, and trail-quality predictions remain null/withheld. Null must never display as zero risk or a confirmed absence. Unreviewed features remain unknown; currently all catalog rows have unreviewed features, and MiniLM mostly embeds route names. Do not claim useful ranking accuracy has been measured.

The backend keeps existing startup error handling: unavailable model assets/dependencies cause recommendation endpoints to return 503 while unrelated routes remain usable. Preserve useful frontend error handling; do not fabricate fallback personalized results.

### Validation and completion

Run frontend typecheck/build using the project's package scripts and test the actual UI behavior where possible. Verify:
- Cold-start recommendations work with no saves.
- Saving a catalog hike updates recommendations using unchanged trip choices and excludes that hike by default.
- Removing it updates recommendations; removing all saves returns cold start.
- Google-place saves and catalog-only saves can coexist and be removed correctly.
- Two independent browser sessions/localStorage contexts keep histories and recommendation metadata separate.
- Slow older requests cannot overwrite newer refreshes.
- Failed save/removal does not change local saved state or trigger a false success; failed refresh has clear error handling.
- Empty results, null fields, experimental labels, unavailable Google enrichment, and unavailable models are handled honestly.

Backend verification commands, run from the repository root after installing `backend/requirements-dev.txt` in a virtual environment:

```bash
(cd backend && ../.venv/bin/python -m unittest test_recommendations test_personalization_integration -v)
(cd summitup_ml && ../.venv/bin/python -m unittest test_personalization test_contract -v)
```

Adjust virtual-environment executable paths on other operating systems. These tests use actual bundled MiniLM inference and an isolated in-memory saved database, with no provider calls. The current backend/ML checks passed: 4 existing API tests, 3 integration tests, 8 personalization tests, and 4 ML contract tests (19 total). End-to-end frontend refresh has NOT been implemented or browser-tested yet; that is your task.

Deployment already copies `summitup_ml/` in the Dockerfile and installs backend requirements. Ensure deployment includes new `pretrained/minilm/` files and `data/catalog_embeddings.npz`, and installs ONNX Runtime/tokenizers; no model download or training is needed. Do not publish/deploy or perform Git operations beyond read-only checks without separate authorization.

Finish by reporting changed files, tests passed, remaining limitations, and any manual steps. Leave everything uncommitted.
