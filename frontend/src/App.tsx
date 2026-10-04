import { useEffect, useRef, useState, type ReactNode, type WheelEvent } from "react";
import { GoogleMap, LoadScript, MarkerF } from "@react-google-maps/api";
import { Bookmark, ChevronDown, ChevronUp, CircleUserRound, Film, Info, Map as MapIcon, MapPin, MessageSquare, Search, Send, Share2, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import type { Details, Metrics, RecommendationOptions, RecommendationRequest, RecommendationResponse, RecommendationResult, SavedTrail, Trail, Video } from "./types";

const fallbackTrails: Trail[] = [
  { place_id: "fallback-tongariro", name: "Tongariro Alpine Crossing", address: "Tongariro National Park, New Zealand", latitude: -39.13, longitude: 175.64, rating: 4.8, user_rating_count: 1842 },
  { place_id: "fallback-sealy", name: "Sealy Tarns Track", address: "Aoraki / Mount Cook National Park", latitude: -43.73, longitude: 170.1, rating: 4.7, user_rating_count: 622 },
];
const fallbackVideo: Video = { video_id: "dQw4w9WgXcQ", title: "Aotearoa, one trail at a time", duration_sec: 32, dimensions: "1080x1920", tags: ["New Zealand", "hiking"], description: "Find your next summit in New Zealand.", url: "https://www.youtube.com/shorts/dQw4w9WgXcQ", hike_names: ["Tongariro Alpine Crossing"] };

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("hikes in Auckland, New Zealand");
  const [trails, setTrails] = useState<Trail[]>(fallbackTrails);
  const [videos, setVideos] = useState<Video[]>([fallbackVideo]);
  const [activeVideoIndex, setActiveVideoIndex] = useState(0);
  const [resolvedVideoTrails, setResolvedVideoTrails] = useState<Record<string, Trail>>({});
  const [saved, setSaved] = useState<SavedTrail[]>([]);
  const [selectedTrail, setSelectedTrail] = useState<Trail | null>(null);
  const [details, setDetails] = useState<Details | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [recommendationOptions, setRecommendationOptions] = useState<RecommendationOptions>({ regions: [], difficulties: [] });
  const [recommendationResponse, setRecommendationResponse] = useState<RecommendationResponse | null>(null);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");
  const page = location.pathname === "/map" ? "map" : location.pathname === "/profile" ? "profile" : "feed";
  const wheelLock = useRef(0);

  useEffect(() => { api.saved().then(setSaved).catch(() => undefined); }, []);
  useEffect(() => { api.recommendationOptions().then(setRecommendationOptions).catch(() => undefined); }, []);
  useEffect(() => {
    setActiveVideoIndex((index) => Math.min(index, Math.max(videos.length - 1, 0)));
  }, [videos.length]);
  useEffect(() => {
    if (page !== "feed") return;
    const video = videos[activeVideoIndex];
    const fallbackTrail = trails[activeVideoIndex % trails.length] ?? trails[0];
    if (!video || !fallbackTrail || resolvedVideoTrails[video.video_id]) return;
    resolveVideoTrail(video, fallbackTrail).then((trail) => {
      setResolvedVideoTrails((current) => ({ ...current, [video.video_id]: trail }));
    }).catch(() => undefined);
  }, [activeVideoIndex, page, trails, videos]);
  useEffect(() => {
    if (page !== "feed") return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowDown" || event.key === "PageDown") stepVideo(1);
      if (event.key === "ArrowUp" || event.key === "PageUp") stepVideo(-1);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [page, videos.length]);

  function stepVideo(direction: number) {
    setActiveVideoIndex((index) => (index + direction + videos.length) % videos.length);
  }

  function handleReelWheel(event: WheelEvent<HTMLElement>) {
    if (Math.abs(event.deltaY) < 20 || Date.now() - wheelLock.current < 500) return;
    wheelLock.current = Date.now();
    stepVideo(event.deltaY > 0 ? 1 : -1);
  }

  async function search(nextQuery = query) {
    setLoading(true);
    setNotice("");
    try {
      const [trailResponse, videoResponse] = await Promise.all([api.search(nextQuery), api.shorts(nextQuery)]);
      setTrails(trailResponse.items.length ? trailResponse.items : fallbackTrails);
      if (videoResponse.items.length) setVideos(videoResponse.items);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Search providers are unavailable. Showing local examples.");
    } finally { setLoading(false); }
  }

  async function openTrail(trail: Trail) {
    setSelectedTrail(trail);
    setDrawerOpen(true);
    setDetails(null);
    setMetrics(null);
    try {
      const [placeDetails, trailMetrics] = await Promise.all([api.details(trail.place_id), api.metrics(trail.name)]);
      setDetails(placeDetails);
      setMetrics(trailMetrics);
    } catch { setNotice("Some trail details are unavailable right now."); }
  }

  async function resolveVideoTrail(video: Video, fallbackTrail: Trail): Promise<Trail> {
    const hikeNames = video.hike_names.map((name) => name.trim()).filter(Boolean);
    if (!hikeNames.length) {
      return fallbackTrail;
    }
    const responses = await Promise.all(hikeNames.map((name) => api.search(name)));
    const candidates = responses.flatMap((response, index) => response.items.map((trail) => ({ trail, hikeName: hikeNames[index] })));
    const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
    const score = ({ trail, hikeName }: { trail: Trail; hikeName: string }) => {
      const trailName = normalize(trail.name);
      const requestedName = normalize(hikeName);
      if (trailName === requestedName) return 1000;
      if (trailName.includes(requestedName) || requestedName.includes(trailName)) return 500;
      const requestedWords = new Set(requestedName.split(" ").filter((word) => word.length > 2));
      return [...new Set(trailName.split(" "))].filter((word) => requestedWords.has(word)).length;
    };
    return candidates.sort((left, right) => score(right) - score(left))[0]?.trail ?? fallbackTrail;
  }

  async function openVideoTrail(video: Video, fallbackTrail: Trail) {
    try {
      const resolvedTrail = resolvedVideoTrails[video.video_id] ?? await resolveVideoTrail(video, fallbackTrail);
      setResolvedVideoTrails((current) => ({ ...current, [video.video_id]: resolvedTrail }));
      await openTrail(resolvedTrail);
    } catch {
      const hikeName = video.hike_names[0]?.trim();
      setNotice(hikeName ? `Could not find trail details for ${hikeName}.` : "Could not find trail details for this short.");
      await openTrail(fallbackTrail);
    }
  }

  async function toggleSave(trail: Trail) {
    const isSaved = saved.some((item) => item.place_id === trail.place_id);
    try {
      const result = await api.toggleSaved(trail, !isSaved);
      setSaved((current) => result.saved ? [...current.filter((item) => item.place_id !== trail.place_id), result.trail] : current.filter((item) => item.place_id !== trail.place_id));
    } catch { setNotice("Saving is unavailable until the API is running."); }
  }

  async function recommendTrails(payload: RecommendationRequest) {
    setRecommendationLoading(true);
    setRecommendationError("");
    try { setRecommendationResponse(await api.recommendations(payload)); }
    catch (error) { setRecommendationResponse(null); setRecommendationError(error instanceof Error ? error.message : "Recommendations are unavailable."); }
    finally { setRecommendationLoading(false); }
  }

  async function openRecommendation(result: RecommendationResult) {
    try {
      const response = await api.search(result.name);
      if (!response.items.length) { setNotice(`Google Places could not verify ${result.name}.`); return; }
      await openTrail(response.items[0]);
    } catch { setNotice("Google Places enrichment is unavailable; use the catalog source link for this recommendation."); }
  }

  async function saveRecommendation(result: RecommendationResult) {
    try {
      const savedResult = await api.toggleCatalogSaved({ catalog_hike_id: result.hike_id, name: result.name, metrics: { name: result.name, length_km: result.distance_km, elevation_gain_meters: result.elevation_gain_m, difficulty: result.difficulty, available: true } }, true);
      setSaved((current) => [...current.filter((item) => item.catalog_hike_id !== result.hike_id), savedResult.trail]);
      setNotice(`${result.name} saved to your vault.`);
    } catch { setNotice("Catalog saving is unavailable right now."); }
  }

  return <main className={`app-shell ${page}-page`}>
    {page === "feed" && <FeedView video={videos[activeVideoIndex]} trail={resolvedVideoTrails[videos[activeVideoIndex]?.video_id] ?? trails[activeVideoIndex % trails.length] ?? trails[0]} activeIndex={activeVideoIndex} videoCount={videos.length} onStep={stepVideo} onWheel={handleReelWheel} onInfo={() => openVideoTrail(videos[activeVideoIndex], resolvedVideoTrails[videos[activeVideoIndex]?.video_id] ?? trails[activeVideoIndex % trails.length] ?? trails[0])} onSave={() => toggleSave(resolvedVideoTrails[videos[activeVideoIndex]?.video_id] ?? trails[activeVideoIndex % trails.length] ?? trails[0])} saved={saved.some((item) => item.place_id === (resolvedVideoTrails[videos[activeVideoIndex]?.video_id] ?? trails[activeVideoIndex % trails.length] ?? trails[0])?.place_id)} onSearch={search} query={query} setQuery={setQuery} loading={loading} notice={notice} />}
    <div className={`map-view-shell ${page === "map" ? "is-active" : "is-hidden"}`}><MapView trails={trails} query={query} setQuery={setQuery} loading={loading} notice={notice} onSearch={search} onSelect={openTrail} recommendationOptions={recommendationOptions} recommendationResponse={recommendationResponse} recommendationLoading={recommendationLoading} recommendationError={recommendationError} onRecommend={recommendTrails} onOpenRecommendation={openRecommendation} onSaveRecommendation={saveRecommendation} /></div>
    {page === "profile" && <ProfileView saved={saved} onSelect={openTrail} />}
    <BottomNav page={page} navigate={navigate} />
    {drawerOpen && selectedTrail && <InfoDrawer trail={selectedTrail} details={details} metrics={metrics} saved={saved.some((item) => item.place_id === selectedTrail.place_id)} onClose={() => setDrawerOpen(false)} onSave={() => toggleSave(selectedTrail)} />}
  </main>;
}

function FeedView({ video, trail, activeIndex, videoCount, onStep, onWheel, onInfo, onSave, saved, onSearch, query, setQuery, loading, notice }: { video: Video; trail: Trail; activeIndex: number; videoCount: number; onStep: (direction: number) => void; onWheel: (event: WheelEvent<HTMLElement>) => void; onInfo: () => void; onSave: () => void; saved: boolean; onSearch: () => void; query: string; setQuery: (value: string) => void; loading: boolean; notice: string }) {
  return <section className="feed-stage" onWheel={onWheel}>
    <header className="shorts-header"><div className="shorts-brand"><span className="shorts-brand-mark"><Film size={18} /></span><strong>Summit Up</strong><small>SHORTS</small></div><div className="map-search reels-search"><Search size={18} /><input aria-label="Search hikes and shorts" placeholder="Search" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSearch()} /><button onClick={() => onSearch()}>{loading ? "Searching..." : "SEARCH"}</button></div></header>
    <div className="shorts-heading"><span className="eyebrow">SHORTS / TRAIL FEED</span><h1>Watch the wild.</h1><p>Vertical field notes for your next high point.</p></div>
    <div className="reel-frame"><iframe className="reel-video" src={`https://www.youtube.com/embed/${video.video_id}?autoplay=1&playsinline=1&rel=0&modestbranding=1`} title={video.title} allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen /><div className="reel-image" style={{ backgroundImage: "url(https://images.unsplash.com/photo-1464278533981-50106e6176b1?auto=format&fit=crop&w=900&q=85)" }} /><div className="reel-shade" /><div className="reel-copy"><h2>{trail.name}</h2><p>{trail.address}</p></div><div className="video-mark"><span>WATCH</span><strong>SHORT</strong></div></div>
    <div className="action-rail"><ActionButton icon={<Info />} label="Trail info" onClick={onInfo} /><ActionButton icon={<Bookmark fill={saved ? "currentColor" : "none"} />} label={saved ? "Saved" : "Save trail"} onClick={onSave} active={saved} /><ActionButton icon={<MessageSquare />} label="Reviews" onClick={onInfo} /><ActionButton icon={<Share2 />} label="Share" onClick={() => navigator.clipboard?.writeText(video.url)} /></div>
    {notice && <div className="toast">{notice}</div>}
    <div className="reel-controls"><button aria-label="Previous short" onClick={() => onStep(-1)}><ChevronUp /></button><span>{String(activeIndex + 1).padStart(2, "0")} / {String(videoCount).padStart(2, "0")}</span><button aria-label="Next short" onClick={() => onStep(1)}><ChevronDown /></button></div>
  </section>;
}

function ActionButton({ icon, label, onClick, active = false }: { icon: ReactNode; label: string; onClick: () => void; active?: boolean }) { return <button className={`action-button ${active ? "is-active" : ""}`} onClick={onClick} aria-label={label}>{icon}</button>; }

type MapBounds = { west: number; south: number; east: number; north: number };

function getMapBounds(trails: Trail[]): MapBounds {
  const searchedTrails = trails.filter((trail) => !trail.place_id.startsWith("fallback-") && trail.latitude != null && trail.longitude != null);
  if (!searchedTrails.length) return { west: 166, south: -47, east: 179, north: -34 };

  const longitudes = searchedTrails.map((trail) => trail.longitude as number);
  const latitudes = searchedTrails.map((trail) => trail.latitude as number);
  const longitudeSpan = Math.max(Math.max(...longitudes) - Math.min(...longitudes), 0.1);
  const latitudeSpan = Math.max(Math.max(...latitudes) - Math.min(...latitudes), 0.1);
  const longitudePadding = Math.max(longitudeSpan * 0.35, 0.25);
  const latitudePadding = Math.max(latitudeSpan * 0.35, 0.25);
  return {
    west: Math.min(...longitudes) - longitudePadding,
    south: Math.min(...latitudes) - latitudePadding,
    east: Math.max(...longitudes) + longitudePadding,
    north: Math.max(...latitudes) + latitudePadding,
  };
}

function MapView({ trails, query, setQuery, loading, notice, onSearch, onSelect, recommendationOptions, recommendationResponse, recommendationLoading, recommendationError, onRecommend, onOpenRecommendation, onSaveRecommendation }: { trails: Trail[]; query: string; setQuery: (value: string) => void; loading: boolean; notice: string; onSearch: () => void; onSelect: (trail: Trail) => void; recommendationOptions: RecommendationOptions; recommendationResponse: RecommendationResponse | null; recommendationLoading: boolean; recommendationError: string; onRecommend: (payload: RecommendationRequest) => void; onOpenRecommendation: (result: RecommendationResult) => void; onSaveRecommendation: (result: RecommendationResult) => void }) {
  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
  const [mapError, setMapError] = useState(false);
  const bounds = getMapBounds(trails);
  const openStreetMap = `https://www.openstreetmap.org/export/embed.html?bbox=${bounds.west}%2C${bounds.south}%2C${bounds.east}%2C${bounds.north}&layer=mapnik`;
  const mapPins = trails.filter((trail) => trail.latitude != null && trail.longitude != null).map((trail) => ({ trail, left: ((trail.longitude! - bounds.west) / (bounds.east - bounds.west)) * 100, top: ((bounds.north - trail.latitude!) / (bounds.north - bounds.south)) * 100 }));
  const center = trails.find((trail) => trail.latitude != null && trail.longitude != null) ?? fallbackTrails[0];
  const map = <GoogleMap mapContainerClassName="google-map" center={{ lat: center.latitude as number, lng: center.longitude as number }} zoom={trails.some((trail) => !trail.place_id.startsWith("fallback-")) ? 10 : 5} options={{ disableDefaultUI: true }}>{trails.map((trail) => trail.latitude != null && trail.longitude != null ? <MarkerF key={trail.place_id} position={{ lat: trail.latitude, lng: trail.longitude }} onClick={() => onSelect(trail)} /> : null)}</GoogleMap>;
  const fallbackMap = <div className="map-fallback"><iframe key={openStreetMap} title="New Zealand trail map" src={openStreetMap} /><div className="map-fallback-note">{mapError ? "Google Maps unavailable. Showing OpenStreetMap." : "OpenStreetMap trail map"}</div><div className="map-pins">{mapPins.map(({ trail, left, top }) => <button key={trail.place_id} className="map-pin" style={{ left: `${left}%`, top: `${top}%` }} onClick={() => onSelect(trail)} aria-label={`Open ${trail.name}`} title={trail.name}><MapPin size={24} fill="currentColor" /></button>)}</div></div>;
  return <section className="map-stage"><div className="map-backdrop">{key && !mapError ? <LoadScript googleMapsApiKey={key} onError={() => setMapError(true)}>{map}</LoadScript> : fallbackMap}</div><div className="map-search"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSearch()} /><button onClick={() => onSearch()}>{loading ? "Searching..." : "Search"}</button></div><div className="map-label"><span className="eyebrow">LIVE EXPLORATION</span><h1>Trace the<br /><em>ridgeline.</em></h1></div><RecommendationPanel options={recommendationOptions} response={recommendationResponse} loading={recommendationLoading} error={recommendationError} onSubmit={onRecommend} onOpen={onOpenRecommendation} onSave={onSaveRecommendation} />{notice && <div className="toast map-toast">{notice}</div>}</section>;
}

function RecommendationPanel({ options, response, loading, error, onSubmit, onOpen, onSave }: { options: RecommendationOptions; response: RecommendationResponse | null; loading: boolean; error: string; onSubmit: (payload: RecommendationRequest) => void; onOpen: (result: RecommendationResult) => void; onSave: (result: RecommendationResult) => void }) {
  const [travelDate, setTravelDate] = useState(new Date().toISOString().slice(0, 10));
  const [region, setRegion] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [preferences, setPreferences] = useState("");
  const [distance, setDistance] = useState("");
  const [elevation, setElevation] = useState("");
  const [time, setTime] = useState("");
  const [features, setFeatures] = useState<string[]>([]);
  const [conditionWeights, setConditionWeights] = useState({ overall_good: "1", bugs: "0.8", mud: "0.5" });
  const submit = () => onSubmit({ travel_date: travelDate, ...(region ? { region } : {}), ...(difficulty ? { difficulty } : {}), ...(distance ? { max_distance_km: Number(distance) } : {}), ...(elevation ? { max_elevation_gain_m: Number(elevation) } : {}), ...(time ? { max_time_hours: Number(time) } : {}), preferences_text: preferences, desired_features: features, condition_weights: Object.fromEntries(Object.entries(conditionWeights).map(([key, value]) => [key, Number(value)])), allow_experimental: true, top_k: 10 });
  const results = response && "results" in response ? response.results : [];
  return <aside className="recommendation-panel"><div className="recommendation-panel-head"><div><span className="eyebrow">EXPERIMENTAL SEASONAL RECOMMENDATIONS</span><h2>Plan a better day out.</h2></div><span className="recommendation-note">Reviewer-condition scores, not safety guarantees.</span></div><div className="recommendation-controls"><label>Date<input type="date" value={travelDate} onChange={(event) => setTravelDate(event.target.value)} /></label><label>Region<select value={region} onChange={(event) => setRegion(event.target.value)}><option value="">All regions</option>{options.regions.map((item) => <option key={item}>{item}</option>)}</select></label><label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option value="">Any difficulty</option>{options.difficulties.map((item) => <option key={item}>{item}</option>)}</select></label><label>Max km<input type="number" min="0" value={distance} onChange={(event) => setDistance(event.target.value)} /></label><label>Max hours<input type="number" min="0" value={time} onChange={(event) => setTime(event.target.value)} /></label><label>Max elevation<input type="number" min="0" value={elevation} onChange={(event) => setElevation(event.target.value)} /></label><label className="recommendation-preferences">Preferences<input placeholder="mountain views, quiet lake" value={preferences} onChange={(event) => setPreferences(event.target.value)} /></label><div className="recommendation-options"><span>Features</span>{["views", "lake", "forest", "waterfall", "coastal"].map((feature) => <label key={feature}><input type="checkbox" checked={features.includes(feature)} onChange={(event) => setFeatures((current) => event.target.checked ? [...current, feature] : current.filter((item) => item !== feature))} />{feature}</label>)}</div><div className="recommendation-options"><span>Condition weight</span>{Object.keys(conditionWeights).map((key) => <label key={key}>{key}<input type="number" min="0" step="0.1" value={conditionWeights[key as keyof typeof conditionWeights]} onChange={(event) => setConditionWeights((current) => ({ ...current, [key]: event.target.value }))} /></label>)}</div><button className="recommendation-submit" onClick={submit} disabled={loading}>{loading ? "Loading..." : "Recommend"}</button></div>{error && <p className="recommendation-error">{error}</p>}{response?.status === "no_matches" && <p className="recommendation-empty">No hikes match those filters.</p>}{results.length > 0 && <div className="recommendation-results">{results.map((result) => <article className="recommendation-card" key={result.hike_id}><div><span className="recommendation-rank">#{result.rank ?? "-"}</span><h3>{result.name}</h3><p>{result.region} · {result.difficulty ?? "Difficulty unavailable"}</p><p>{result.distance_km ?? "-"} km · {result.elevation_gain_m ?? "-"} m gain · {result.estimated_time_hours ?? "Time unavailable"}</p></div><div className="recommendation-card-actions"><span>{result.ranking_score == null ? "Unranked" : `Score ${result.ranking_score.toFixed(2)}`}</span><button onClick={() => onOpen(result)}>View details</button><button onClick={() => onSave(result)}>Save</button>{result.source_url && <a href={result.source_url} target="_blank" rel="noreferrer">Source</a>}</div><p className="recommendation-reasons">{result.reasons.join(" ") || "Catalog match; model evidence is limited."}</p></article>)}</div>}</aside>;
}

function ProfileView({ saved, onSelect }: { saved: SavedTrail[]; onSelect: (trail: Trail) => void }) { return <section className="profile-stage"><div className="profile-header"><div><p className="eyebrow">YOUR TRAIL VAULT</p><h1>Keep the wild<br /><em>within reach.</em></h1></div><div className="avatar"><CircleUserRound size={35} /></div></div><div className="profile-stats"><div><strong>{saved.length}</strong><span>Saved trails</span></div><div><strong>{saved.filter((trail) => trail.metrics?.difficulty === "Hard").length}</strong><span>Big days</span></div><div><strong>NZ</strong><span>Home range</span></div></div><div className="saved-header"><div><span className="eyebrow">BOOKMARKED</span><h2>Routes worth returning to</h2></div><span className="saved-count">{saved.length.toString().padStart(2, "0")} / VAULT</span></div>{saved.length === 0 ? <div className="empty-state"><Bookmark size={28} /><h3>Your vault is quiet.</h3><p>Save a trail from Explore and it will appear here.</p></div> : <div className="saved-grid">{saved.map((trail) => <button className="saved-card" key={trail.place_id} onClick={() => onSelect(trail)}><div className="saved-card-photo" style={{ backgroundImage: "url(https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=700&q=80)" }} /><div className="saved-card-copy"><span className="eyebrow">{trail.metrics?.difficulty ?? "TRAIL"}</span><h3>{trail.name}</h3><p>{trail.address ?? "New Zealand"}</p><span className="text-link">OPEN DETAILS <Send size={13} /></span></div></button>)}</div>}</section>; }

function InfoDrawer({ trail, details, metrics, saved, onClose, onSave }: { trail: Trail; details: Details | null; metrics: Metrics | null; saved: boolean; onClose: () => void; onSave: () => void }) { return <aside className="info-drawer"><div className="drawer-handle" /><button className="close-drawer" onClick={onClose} aria-label="Close trail information"><X /></button><div className="drawer-photo" style={{ backgroundImage: "url(https://images.unsplash.com/photo-1439853949127-fa647821eba0?auto=format&fit=crop&w=1200&q=85)" }}><div className="drawer-photo-title"><span className="eyebrow">TRAIL INTELLIGENCE</span><h2>{details?.name ?? trail.name}</h2></div></div><div className="drawer-content"><div className="drawer-heading"><div><span className="eyebrow">{metrics?.difficulty ?? "DISCOVER"}</span><h3>{trail.address ?? "New Zealand"}</h3></div><button className={`save-pill ${saved ? "is-active" : ""}`} onClick={onSave}><Bookmark size={16} fill={saved ? "currentColor" : "none"} /> {saved ? "Saved" : "Save"}</button></div><div className="metrics-grid"><Metric label="Length" value={metrics?.length_km ? `${metrics.length_km} km` : "Awaiting"} /><Metric label="Elevation" value={metrics?.elevation_gain_meters ? `${metrics.elevation_gain_meters} m` : "Awaiting"} /><Metric label="Rating" value={details?.rating ? `${details.rating} / 5` : trail.rating ? `${trail.rating} / 5` : "-"} /></div><div className="reviews-head"><h3>Field reports</h3><span>{details?.user_rating_count ?? trail.user_rating_count ?? 0} reviews</span></div>{details?.reviews?.length ? details.reviews.slice(0, 3).map((review, index) => <div className="review" key={`${review.author}-${index}`}><strong>{review.author}</strong><span>{review.relative_time ?? "Recent"} · {review.rating ?? "-"} stars</span><p>{review.text}</p></div>) : <p className="muted-copy">Reviews will appear when Google Places details are available.</p>}<div className="drawer-actions"><button onClick={onSave}><Bookmark size={16} /> {saved ? "Remove from vault" : "Save to vault"}</button><a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(trail.name)}`} target="_blank" rel="noreferrer"><MapPin size={16} /> Directions</a></div></div></aside>; }
function Metric({ label, value }: { label: string; value: string }) { const isLoading = value === "Awaiting" || value === "Loading"; return <div><span>{label}</span><strong className={isLoading ? "metric-loading" : ""}>{isLoading && <span className="loading-spinner" aria-hidden="true" />} {isLoading ? "Loading" : value}</strong></div>; }
function BottomNav({ page, navigate }: { page: string; navigate: (path: string) => void }) { return <nav className="bottom-nav" aria-label="Primary navigation"><button className={page === "feed" ? "active" : ""} onClick={() => navigate("/feed")}><Film /><span>Reels</span></button><button className={page === "map" ? "active" : ""} onClick={() => navigate("/map")}><MapIcon /><span>Explore</span></button><button className={page === "profile" ? "active" : ""} onClick={() => navigate("/profile")}><CircleUserRound /><span>Saved</span></button></nav>; }

export default App;
