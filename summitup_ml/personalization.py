"""Saved-hike user profiles over actual pretrained semantic vectors."""
from pathlib import Path
import hashlib,json,re,unicodedata
import numpy as np
try:
    from .semantic_encoder import MiniLMEncoder,MODEL_ID
except ImportError:
    from semantic_encoder import MiniLMEncoder,MODEL_ID

TAGS={'forest':'forest','mountain_alpine':'mountain and alpine scenery','lake':'lake',
      'waterfall':'waterfall','coastal':'coast and beach','river':'river','glacier':'glacier','views':'scenic views'}

def clean(value):
    if value is None or (isinstance(value,float) and np.isnan(value)):return ''
    return str(value).strip()

def key(name):return ' '.join(unicodedata.normalize('NFKC',clean(name)).casefold().split())

def catalog_document(row):
    # Verifiable structured fields only; inherited unreviewed scenery tags are excluded.
    # Length, gain, region, and difficulty already feed filters/seasonal models.
    # Repeating generic numeric prose in every document overwhelms the available experience text.
    phrases=[clean(row.get('name'))]
    if row.get('features_reviewed')==1:
        phrases.extend(label for tag,label in TAGS.items() if row.get(tag)==1)
        description=clean(row.get('description_curated'))
        if description:phrases.append(description)
    return '. '.join(p for p in phrases if p)

def external_document(record):
    # No live API calls or guessed landscape labels. Only metadata actually supplied by storage.
    name=clean(record.get('name'))
    if not name:return None
    phrases=[name,'Saved hiking trail',clean(record.get('address'))]
    metrics=record.get('metrics') or {}
    if isinstance(metrics,dict):
        for field,label,unit in [('difficulty','Difficulty',''),('route_type','Route type',''),
                                 ('length_km','Distance','km'),('elevation_gain_meters','Elevation gain','m')]:
            value=clean(metrics.get(field))
            if value:phrases.append(f'{label}: {value} {unit}'.strip())
    return '. '.join(p for p in phrases if p)

class SavedHikePersonalizer:
    def __init__(self,hikes,root,encoder=None):
        self.hikes=hikes.reset_index(drop=True)
        self.encoder=encoder or MiniLMEncoder()
        self.ids=self.hikes.hike_id.tolist()
        self.index={hid:i for i,hid in enumerate(self.ids)}
        self.records=self.hikes.to_dict('records')
        self.documents=[catalog_document(row) for row in self.records]
        self.name_map={}
        for row in self.records:self.name_map.setdefault(key(row['name']),[]).append(row['hike_id'])
        fingerprint=hashlib.sha256(json.dumps({'documents':self.documents,'ids':self.ids,
                    'model':self.encoder.provenance},sort_keys=True).encode()).hexdigest()
        cache=Path(root)/'data/catalog_embeddings.npz'
        self.cache_reused=False
        if cache.is_file():
            with np.load(cache,allow_pickle=False) as loaded:
                if str(loaded['fingerprint'].item())==fingerprint:
                    self.vectors=loaded['vectors'].copy();self.cache_reused=True
        if not self.cache_reused:
            self.vectors=self.encoder.encode(self.documents)
            # A read-only deployment can run in memory if its precomputed cache is stale.
            try:np.savez_compressed(cache,vectors=self.vectors,ids=np.asarray(self.ids),fingerprint=np.asarray(fingerprint))
            except OSError:pass
        self.fingerprint=fingerprint
        if self.vectors.shape!=(len(self.ids),384):raise RuntimeError('Invalid catalog embedding cache shape')

    def profile(self,saved_hike_ids=None,saved_hikes=None):
        if saved_hike_ids is None:saved_hike_ids=[]
        if saved_hikes is None:saved_hikes=[]
        if not isinstance(saved_hike_ids,list) or not all(isinstance(x,str) for x in saved_hike_ids):raise ValueError('saved_hike_ids must be a list of catalog ID strings')
        if not isinstance(saved_hikes,list) or not all(isinstance(x,dict) for x in saved_hikes):raise ValueError('saved_hikes must be a list of stored trail records')
        if len(saved_hike_ids)+len(saved_hikes)>500:raise ValueError('At most 500 saved records are supported')
        matched=set();missing=[];external={};methods=[]
        for hid in saved_hike_ids:
            if hid in self.index:matched.add(hid)
            else:missing.append(hid)
        for record in saved_hikes:
            hid=clean(record.get('hike_id'))
            place_id=clean(record.get('place_id'))
            match=re.fullmatch(r'(?:catalog:|hike:)?(NZ\d{3})',place_id)
            if not hid and match:hid=match.group(1)
            if hid:
                if hid in self.index:matched.add(hid);methods.append('explicit_catalog_id');continue
                missing.append(hid);continue
            candidates=self.name_map.get(key(record.get('name')),[])
            if clean(record.get('region')):candidates=[c for c in candidates if key(self.records[self.index[c]]['region'])==key(record['region'])]
            if len(candidates)==1:
                matched.add(candidates[0]);methods.append('unique_exact_catalog_name');continue
            document=external_document(record)
            if document:
                identity=place_id or hashlib.sha256(document.encode()).hexdigest()
                external[identity]=document;methods.append('external_saved_metadata')
            else:missing.append(place_id or 'unnamed_saved_record')
        vectors=[self.vectors[self.index[hid]] for hid in sorted(matched)]
        if external:vectors.extend(self.encoder.encode(list(external.values())))
        meta={'status':'cold_start' if not vectors else 'personalized',
              'model_category':'off-the-shelf','model_id':MODEL_ID,'revision':self.encoder.provenance['revision'],
              'saved_catalog_hike_ids':sorted(matched),'saved_catalog_count':len(matched),
              'external_saved_count':len(external),'saved_examples_used':len(vectors),
              'unresolved_saved_ids':sorted(set(missing)),'matching_methods':sorted(set(methods)),
              'profile_method':'equal-weight mean of normalized saved-hike embeddings, then L2 normalization',
              'catalog_text_status':'route names plus verified descriptions/tags; current catalog is mostly names only',
              'rank_quality_validated':False}
        if not vectors:return None,meta
        mean=np.mean(vectors,axis=0);norm=np.linalg.norm(mean)
        if norm<1e-12:meta['status']='unusable_profile';return None,meta
        return mean/norm,meta

    def similarities(self,profile):
        # Map cosine [-1,1] to a nonnegative rank component [0,1]; not a probability.
        return np.clip((self.vectors@profile+1)/2,0,1)

    def closest_saved(self,catalog_index,saved_ids):
        if not saved_ids:return None
        candidates=sorted(saved_ids)
        scores=[float(self.vectors[catalog_index]@self.vectors[self.index[hid]]) for hid in candidates]
        best=candidates[int(np.argmax(scores))]
        return {'hike_id':best,'name':self.records[self.index[best]]['name']}
