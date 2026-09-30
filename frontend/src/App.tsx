import { useEffect, useRef, useState, type ReactNode, type WheelEvent } from "react";
import { GoogleMap, LoadScript, MarkerF } from "@react-google-maps/api";
import { Bookmark, ChevronDown, ChevronUp, CircleUserRound, Film, Info, Map as MapIcon, MapPin, MessageSquare, Search, Send, Share2, Star, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import type { Details, Metrics, SavedTrail, Trail, Video } from "./types";

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
  const [saved, setSaved] = useState<SavedTrail[]>([]);
  const [selectedTrail, setSelectedTrail] = useState<Trail | null>(null);
  const [details, setDetails] = useState<Details | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const page = location.pathname === "/map" ? "map" : location.pathname === "/profile" ? "profile" : "feed";
  const wheelLock = useRef(0);

  useEffect(() => { api.saved().then(setSaved).catch(() => undefined); }, []);
  useEffect(() => {
    setActiveVideoIndex((index) => Math.min(index, Math.max(videos.length - 1, 0)));
  }, [videos.length]);
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

  async function toggleSave(trail: Trail) {
    const isSaved = saved.some((item) => item.place_id === trail.place_id);
    try {
      const result = await api.toggleSaved(trail, !isSaved);
      setSaved((current) => result.saved ? [...current.filter((item) => item.place_id !== trail.place_id), result.trail] : current.filter((item) => item.place_id !== trail.place_id));
    } catch { setNotice("Saving is unavailable until the API is running."); }
  }

  return <main className={`app-shell ${page}-page`}>
    {page === "feed" && <FeedView video={videos[activeVideoIndex]} trail={trails[activeVideoIndex % trails.length] ?? trails[0]} activeIndex={activeVideoIndex} videoCount={videos.length} onStep={stepVideo} onWheel={handleReelWheel} onInfo={() => openTrail(trails[activeVideoIndex % trails.length] ?? trails[0])} onSave={() => toggleSave(trails[activeVideoIndex % trails.length] ?? trails[0])} saved={saved.some((item) => item.place_id === (trails[activeVideoIndex % trails.length] ?? trails[0])?.place_id)} onSearch={search} query={query} setQuery={setQuery} notice={notice} />}
    {page === "map" && <MapView trails={trails} query={query} setQuery={setQuery} loading={loading} notice={notice} onSearch={search} onSelect={openTrail} />}
    {page === "profile" && <ProfileView saved={saved} onSelect={openTrail} />}
    <BottomNav page={page} navigate={navigate} />
    {drawerOpen && selectedTrail && <InfoDrawer trail={selectedTrail} details={details} metrics={metrics} saved={saved.some((item) => item.place_id === selectedTrail.place_id)} onClose={() => setDrawerOpen(false)} onSave={() => toggleSave(selectedTrail)} />}
  </main>;
}

function FeedView({ video, trail, activeIndex, videoCount, onStep, onWheel, onInfo, onSave, saved, onSearch, query, setQuery, notice }: { video: Video; trail: Trail; activeIndex: number; videoCount: number; onStep: (direction: number) => void; onWheel: (event: WheelEvent<HTMLElement>) => void; onInfo: () => void; onSave: () => void; saved: boolean; onSearch: () => void; query: string; setQuery: (value: string) => void; notice: string }) {
  return <section className="feed-stage" onWheel={onWheel}>
    <div className="feed-heading"><p className="eyebrow">SUMMIT UP / FIELD NOTES</p><h1>Find your next<br /><em>high point.</em></h1><div className="search-line"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSearch()} /><button onClick={() => onSearch()}>Explore</button></div></div>
    <div className="reel-frame"><iframe className="reel-video" src={`https://www.youtube.com/embed/${video.video_id}?autoplay=1&playsinline=1&rel=0&modestbranding=1`} title={video.title} allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen /><div className="reel-image" style={{ backgroundImage: "url(https://images.unsplash.com/photo-1464278533981-50106e6176b1?auto=format&fit=crop&w=900&q=85)" }} /><div className="reel-shade" /><div className="reel-copy"><span className="location-chip"><MapPin size={13} /> AOTEAROA / NEW ZEALAND</span><h2>{trail.name}</h2><p>{trail.address}</p><div className="stat-row"><span><Star size={14} fill="currentColor" /> {trail.rating ?? "-"}</span><span>Portrait Short</span><span>{video.duration_sec.toFixed(0)} sec</span></div></div><div className="video-mark"><span>WATCH</span><strong>SHORT</strong></div></div>
    <div className="action-rail"><ActionButton icon={<Info />} label="Trail info" onClick={onInfo} /><ActionButton icon={<Bookmark fill={saved ? "currentColor" : "none"} />} label={saved ? "Saved" : "Save trail"} onClick={onSave} active={saved} /><ActionButton icon={<MessageSquare />} label="Reviews" onClick={onInfo} /><ActionButton icon={<Share2 />} label="Share" onClick={() => navigator.clipboard?.writeText(video.url)} /></div>
    {notice && <div className="toast">{notice}</div>}
    <div className="reel-controls"><button aria-label="Previous short" onClick={() => onStep(-1)}><ChevronUp /></button><span>{String(activeIndex + 1).padStart(2, "0")} / {String(videoCount).padStart(2, "0")}</span><button aria-label="Next short" onClick={() => onStep(1)}><ChevronDown /></button></div>
  </section>;
}

function ActionButton({ icon, label, onClick, active = false }: { icon: ReactNode; label: string; onClick: () => void; active?: boolean }) { return <button className={`action-button ${active ? "is-active" : ""}`} onClick={onClick} aria-label={label}>{icon}</button>; }

function MapView({ trails, query, setQuery, loading, notice, onSearch, onSelect }: { trails: Trail[]; query: string; setQuery: (value: string) => void; loading: boolean; notice: string; onSearch: () => void; onSelect: (trail: Trail) => void }) {
  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
  const [mapError, setMapError] = useState(false);
  const center = { lat: -40.9, lng: 174.9 };
  const map = <GoogleMap mapContainerClassName="google-map" center={center} zoom={5} options={{ disableDefaultUI: true, styles: [{ elementType: "geometry", stylers: [{ color: "#d8e2d0" }] }, { elementType: "labels.text.fill", stylers: [{ color: "#28543d" }] }] }}>{trails.map((trail) => trail.latitude && trail.longitude ? <MarkerF key={trail.place_id} position={{ lat: trail.latitude, lng: trail.longitude }} onClick={() => onSelect(trail)} /> : null)}</GoogleMap>;
  const openStreetMap = "https://www.openstreetmap.org/export/embed.html?bbox=166%2C-47%2C179%2C-34&layer=mapnik";
  const fallbackMap = <div className="map-fallback"><iframe title="New Zealand trail map" src={openStreetMap} /><div className="map-fallback-note">{mapError ? "Google Maps is unavailable. Showing OpenStreetMap." : "Trail map"}</div><div className="map-fallback-pins">{trails.map((trail) => <button key={trail.place_id} className="preview-pin" onClick={() => onSelect(trail)}><MapPin size={16} /> {trail.name}</button>)}</div></div>;
  return <section className="map-stage"><div className="map-backdrop">{key && !mapError ? <LoadScript googleMapsApiKey={key} onError={() => setMapError(true)}>{map}</LoadScript> : fallbackMap}</div><div className="map-search"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSearch()} /><button onClick={onSearch}>{loading ? "Searching..." : "Search"}</button></div><div className="map-label"><span className="eyebrow">LIVE EXPLORATION</span><h1>Trace the<br /><em>ridgeline.</em></h1></div>{notice && <div className="toast map-toast">{notice}</div>}</section>;
}

function ProfileView({ saved, onSelect }: { saved: SavedTrail[]; onSelect: (trail: Trail) => void }) { return <section className="profile-stage"><div className="profile-header"><div><p className="eyebrow">YOUR TRAIL VAULT</p><h1>Keep the wild<br /><em>within reach.</em></h1></div><div className="avatar"><CircleUserRound size={35} /></div></div><div className="profile-stats"><div><strong>{saved.length}</strong><span>Saved trails</span></div><div><strong>{saved.filter((trail) => trail.metrics?.difficulty === "Hard").length}</strong><span>Big days</span></div><div><strong>NZ</strong><span>Home range</span></div></div><div className="saved-header"><div><span className="eyebrow">BOOKMARKED</span><h2>Routes worth returning to</h2></div><span className="saved-count">{saved.length.toString().padStart(2, "0")} / VAULT</span></div>{saved.length === 0 ? <div className="empty-state"><Bookmark size={28} /><h3>Your vault is quiet.</h3><p>Save a trail from Explore and it will appear here.</p></div> : <div className="saved-grid">{saved.map((trail) => <button className="saved-card" key={trail.place_id} onClick={() => onSelect(trail)}><div className="saved-card-photo" style={{ backgroundImage: "url(https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=700&q=80)" }} /><div className="saved-card-copy"><span className="eyebrow">{trail.metrics?.difficulty ?? "TRAIL"}</span><h3>{trail.name}</h3><p>{trail.address ?? "New Zealand"}</p><span className="text-link">OPEN DETAILS <Send size={13} /></span></div></button>)}</div>}</section>; }

function InfoDrawer({ trail, details, metrics, saved, onClose, onSave }: { trail: Trail; details: Details | null; metrics: Metrics | null; saved: boolean; onClose: () => void; onSave: () => void }) { return <aside className="info-drawer"><div className="drawer-handle" /><button className="close-drawer" onClick={onClose} aria-label="Close trail information"><X /></button><div className="drawer-photo" style={{ backgroundImage: "url(https://images.unsplash.com/photo-1439853949127-fa647821eba0?auto=format&fit=crop&w=1200&q=85)" }}><div className="drawer-photo-title"><span className="eyebrow">TRAIL INTELLIGENCE</span><h2>{details?.name ?? trail.name}</h2></div></div><div className="drawer-content"><div className="drawer-heading"><div><span className="eyebrow">{metrics?.difficulty ?? "DISCOVER"}</span><h3>{trail.address ?? "New Zealand"}</h3></div><button className={`save-pill ${saved ? "is-active" : ""}`} onClick={onSave}><Bookmark size={16} fill={saved ? "currentColor" : "none"} /> {saved ? "Saved" : "Save"}</button></div><div className="metrics-grid"><Metric label="Length" value={metrics?.length_km ? `${metrics.length_km} km` : "Awaiting"} /><Metric label="Elevation" value={metrics?.elevation_gain_meters ? `${metrics.elevation_gain_meters} m` : "Awaiting"} /><Metric label="Rating" value={details?.rating ? `${details.rating} / 5` : trail.rating ? `${trail.rating} / 5` : "-"} /></div><div className="reviews-head"><h3>Field reports</h3><span>{details?.user_rating_count ?? trail.user_rating_count ?? 0} reviews</span></div>{details?.reviews?.length ? details.reviews.slice(0, 3).map((review, index) => <div className="review" key={`${review.author}-${index}`}><strong>{review.author}</strong><span>{review.relative_time ?? "Recent"} · {review.rating ?? "-"} stars</span><p>{review.text}</p></div>) : <p className="muted-copy">Reviews will appear when Google Places details are available.</p>}<div className="drawer-actions"><button onClick={onSave}><Bookmark size={16} /> {saved ? "Remove from vault" : "Save to vault"}</button><a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(trail.name)}`} target="_blank" rel="noreferrer"><MapPin size={16} /> Directions</a></div></div></aside>; }
function Metric({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
function BottomNav({ page, navigate }: { page: string; navigate: (path: string) => void }) { return <nav className="bottom-nav" aria-label="Primary navigation"><button className={page === "feed" ? "active" : ""} onClick={() => navigate("/feed")}><Film /><span>Reels</span></button><button className={page === "map" ? "active" : ""} onClick={() => navigate("/map")}><MapIcon /><span>Explore</span></button><button className={page === "profile" ? "active" : ""} onClick={() => navigate("/profile")}><CircleUserRound /><span>Saved</span></button></nav>; }

export default App;
