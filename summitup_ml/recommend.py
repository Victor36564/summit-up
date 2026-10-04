"""App contract: JSON preferences in, ranked hikes plus honest model statuses out."""
import argparse,json
from datetime import date
import joblib,numpy as np,pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
try:
    from .seasonal import ROOT,TARGETS,seasonal_features,apply_calibration,load_weather
    from .personalization import SavedHikePersonalizer
    from .semantic_encoder import MiniLMEncoder
except ImportError:
    from seasonal import ROOT,TARGETS,seasonal_features,apply_calibration,load_weather
    from personalization import SavedHikePersonalizer
    from semantic_encoder import MiniLMEncoder

FEATURE_TAGS=['forest','mountain_alpine','lake','waterfall','coastal','river','glacier','views']
class Recommender:
    def __init__(self,root=ROOT,text_backend='minilm'):
        self.root=root
        self.hikes=pd.read_csv(root/'data/hikes.csv')
        self.weather=load_weather(root)
        self.models={t:joblib.load(root/'models'/f'{t}.joblib') for t in TARGETS if (root/'models'/f'{t}.joblib').exists()}
        obs=pd.read_csv(root/'data/seasonal_training.csv')
        self.support=obs[obs.usable_for_training.eq(1)].groupby(['hike_id','month']).size()
        self.text_backend=text_backend
        self.personalizer=None
        if text_backend=='minilm':
            self.encoder=MiniLMEncoder(root/'pretrained/minilm')
            self.personalizer=SavedHikePersonalizer(self.hikes,root,self.encoder)
            self.documents=self.personalizer.documents
            self.vectors=self.personalizer.vectors
        elif text_backend=='sentence_transformer':
            # Compatibility alias: the same published MiniLM model is executed locally via ONNX.
            self.text_backend='minilm'
            self.encoder=MiniLMEncoder(root/'pretrained/minilm')
            self.personalizer=SavedHikePersonalizer(self.hikes,root,self.encoder)
            self.documents=self.personalizer.documents
            self.vectors=self.personalizer.vectors
        elif text_backend=='tfidf':
            self.documents=(self.hikes['name'].fillna('')+' '+self.hikes.region.fillna('')+' '+self.hikes.route_type.fillna('')).tolist()
            self.encoder=TfidfVectorizer(ngram_range=(1,2),stop_words='english').fit(self.documents)
            self.vectors=self.encoder.transform(self.documents)
        else:raise ValueError('text_backend must be minilm, tfidf, or sentence_transformer')

    def recommend(self,request):
        travel=date.fromisoformat(request['travel_date']);as_of=date.fromisoformat(request.get('as_of',date.today().isoformat()))
        if travel<as_of:raise ValueError('travel_date must be on or after as_of; this API supports future planning.')
        top_k=request.get('top_k',10)
        if not isinstance(top_k,int) or not 1<=top_k<=500:raise ValueError('top_k must be an integer from 1 to 500')
        allow=request.get('allow_experimental',False)
        if not isinstance(allow,bool):raise ValueError('allow_experimental must be a boolean')
        saved_ids=request.get('saved_hike_ids',[]);saved_records=request.get('saved_hikes',[])
        personalization_weight=request.get('personalization_weight',0.4)
        if isinstance(personalization_weight,bool) or not isinstance(personalization_weight,(int,float)) or not np.isfinite(personalization_weight) or personalization_weight<0:
            raise ValueError('personalization_weight must be finite and nonnegative')
        exclude_saved=request.get('exclude_saved',True)
        if not isinstance(exclude_saved,bool):raise ValueError('exclude_saved must be a boolean')
        if self.personalizer is not None:
            profile,profile_meta=self.personalizer.profile(saved_ids,saved_records)
            personal_scores=self.personalizer.similarities(profile) if profile is not None else None
        else:
            if saved_ids or saved_records:raise ValueError('Saved-hike personalization requires text_backend=minilm; TF-IDF is not the second pretrained model.')
            personal_scores=None
            profile_meta={'status':'disabled','saved_examples_used':0,'saved_catalog_hike_ids':[]}
        x=self.hikes.copy();x['observation_date']=travel.isoformat()
        x=seasonal_features(x,self.weather,as_of=as_of.isoformat())
        if request.get('region'):x=x[x.region.str.casefold()==request['region'].casefold()]
        if request.get('difficulty'):x=x[x.difficulty_or_grade.str.casefold()==request['difficulty'].casefold()]
        for key,col in [('max_distance_km','distance_km'),('max_elevation_gain_m','elevation_gain_m'),('max_time_hours','estimated_time_hr')]:
            if request.get(key) is not None:
                limit=float(request[key])
                if not np.isfinite(limit) or limit<0:raise ValueError(key+' must be finite and nonnegative')
                # A published range must fit at its upper end, not its lower end.
                numeric=pd.to_numeric(x[col].astype(str).str.replace('–','-').str.split('-').str[-1],errors='coerce')
                x=x[numeric<=limit]
        x=x[~x.current_access_status.eq('previously marked closed')]
        if exclude_saved:x=x[~x.hike_id.isin(profile_meta['saved_catalog_hike_ids'])]
        if x.empty:return {'status':'no_matches','results':[],'request':{k:v for k,v in request.items() if k not in ('saved_hikes','saved_hike_ids')},'personalization':profile_meta}
        query=request.get('preferences_text','')
        if query:
            q=self.encoder.encode([query],normalize_embeddings=True) if self.text_backend=='minilm' else self.encoder.transform([query])
            text_scores=cosine_similarity(q,self.vectors)[0]
        else:text_scores=np.zeros(len(self.hikes))
        weights={'overall_good':1.0,'bugs':0.5,'mud':0.5,'snow':0.5,'ice':0.5,
                 'scenic_positive':0.5,'crowded':0.5,'trail_quality_good':0.5}
        supplied=request.get('condition_weights',{})
        if set(supplied)-set(TARGETS):raise ValueError('Unknown condition_weights target')
        weights.update(supplied)
        if any(not isinstance(v,(int,float)) or not np.isfinite(v) or v<0 for v in weights.values()):raise ValueError('Condition weights must be finite nonnegative numbers')
        preferences=request.get('desired_features',[])
        if set(preferences)-set(FEATURE_TAGS):raise ValueError('Unsupported desired_features; see input schema')
        predictions={};statuses={}
        climate_ok=x.climate_available.to_numpy()
        for t in TARGETS:
            bundle=self.models.get(t)
            if bundle is None:
                predictions[t]=np.full(len(x),np.nan);statuses[t]='withheld: insufficient labels';continue
            meta=bundle['metadata']
            predictions[t]=apply_calibration(bundle['model'],bundle['calibrator'],x)
            statuses[t]='exploratory_gate_passed' if meta['passes_exploratory_gate'] else 'experimental_weak_or_sparse'
        results=[]
        for j,(idx,row) in enumerate(x.iterrows()):
            components=[];condition_detail={};unsupported=[]
            for t in TARGETS:
                value=predictions[t][j]
                usable=np.isfinite(value) and climate_ok[j] and (allow or statuses[t]=='exploratory_gate_passed')
                condition_detail[t]={'model_score':float(value) if np.isfinite(value) and climate_ok[j] else None,
                                     'status':statuses[t] if climate_ok[j] else 'withheld: no prior seasonal climate',
                                     'used_in_ranking':bool(usable and weights[t]>0)}
                if usable and weights[t]>0:
                    desirability=value if t in ['overall_good','scenic_positive','trail_quality_good'] else 1-value
                    components.append((weights[t],desirability))
                elif weights[t]>0:unsupported.append(t)
            seasonal=sum(w*s for w,s in components)/sum(w for w,s in components) if components else None
            tag_matches=[];unknown_tags=[]
            for tag in preferences:
                if row.features_reviewed==1 and pd.notna(row[tag]):tag_matches.append(float(row[tag]))
                else:unknown_tags.append(tag)
            tag_score=float(np.mean(tag_matches)) if tag_matches else None
            contributions=[]
            if seasonal is not None:contributions.append((.6,seasonal))
            if query:contributions.append((.3,float(text_scores[idx])))
            if tag_score is not None:contributions.append((.1,tag_score))
            if personal_scores is not None and personalization_weight>0:contributions.append((personalization_weight,float(personal_scores[idx])))
            score=sum(w*s for w,s in contributions)/sum(w for w,s in contributions) if contributions else None
            reasons=[]
            if seasonal is not None:reasons.append('Seasonal model scores contribute; trained on selectively reported review labels.')
            if query:reasons.append('Semantic text preference similarity; current descriptions are sparse.' if self.text_backend=='minilm' else 'Lexical text preference similarity.')
            closest=None
            if personal_scores is not None and personalization_weight>0:
                closest=self.personalizer.closest_saved(idx,profile_meta['saved_catalog_hike_ids'])
                reasons.append('Similar to your saved hike '+closest['name']+'.' if closest else 'Similar to your saved-trail metadata.')
            if unknown_tags:reasons.append('Requested features lack verified catalog evidence: '+', '.join(unknown_tags))
            if row.current_access_status=='not checked':reasons.append('Current trail access has not been checked.')
            results.append({'hike_id':row.hike_id,'name':row['name'],'region':row.region,
                'distance_km':float(row.distance_km),'elevation_gain_m':float(row.elevation_gain_m),
                'estimated_time_hours':str(row.estimated_time_hr),'difficulty':row.difficulty_or_grade,
                'ranking_score':float(score) if score is not None else None,'seasonal_suitability_score':float(seasonal) if seasonal is not None else None,
                'text_similarity':float(text_scores[idx]) if query else None,'conditions':condition_detail,
                'personalization_score':float(personal_scores[idx]) if personal_scores is not None else None,
                'personalization_used':bool(personal_scores is not None and personalization_weight>0),
                'similar_saved_hike':closest,
                'unsupported_weighted_targets':unsupported,'unknown_requested_features':unknown_tags,
                'same_hike_month_observations':int(self.support.get((row.hike_id,travel.month),0)),
                'climate_scope':row.climate_scope,
                'source_url':row.source_url,'reasons':reasons})
        results.sort(key=lambda r:(-(r['ranking_score'] if r['ranking_score'] is not None else -1),r['hike_id']))
        for i,r in enumerate(results):r['rank']=i+1 if r['ranking_score'] is not None else None
        return {'status':'experimental' if allow else 'limited_evidence','travel_date':travel.isoformat(),
                'as_of':as_of.isoformat(),'text_backend':self.text_backend,'candidates':len(results),
                'personalization':profile_meta,
                'prediction_meaning':'Scores for explicit reviewer reports, not calibrated population trip probabilities.',
                'ranking_validated':False,'results':results[:top_k]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--output',default='response.json')
    p.add_argument('--text-backend',default='minilm',choices=['minilm','tfidf','sentence_transformer']);a=p.parse_args()
    response=Recommender(text_backend=a.text_backend).recommend(json.loads(open(a.request).read()))
    with open(a.output,'w') as f:json.dump(response,f,indent=2,allow_nan=False)
    print('Wrote',a.output)
if __name__=='__main__':main()
