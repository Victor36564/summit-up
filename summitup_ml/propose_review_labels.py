"""Optional pretrained AI labeling proposals; NEVER auto-approve them for training."""
import argparse,json
import pandas as pd

DESCRIPTIONS={
 'overall_good':['The reviewer explicitly reports good hiking conditions.','The reviewer explicitly reports poor hiking conditions.','The review does not establish overall trail conditions.'],
 'bugs':['The reviewer explicitly experienced annoying bugs or sandflies.','The reviewer explicitly reports no bugs or sandflies.','Bugs are not established in this review.'],
 'mud':['The trail was muddy.','The reviewer explicitly says the trail was not muddy.','Mud conditions are not established.'],
 'snow':['Snow was present on the trail.','The reviewer explicitly says the trail was snow free.','Snow conditions are not established.'],
 'ice':['Ice was present on the trail.','The reviewer explicitly says the trail was ice free.','Ice conditions are not established.'],
 'scenic_positive':['The reviewer found the scenery beautiful or impressive.','The reviewer found the scenery disappointing.','The scenic experience is not established.'],
 'crowded':['The reviewer found the trail crowded.','The reviewer explicitly found the trail quiet or uncrowded.','Crowding is not established.'],
 'trail_quality_good':['The reviewer explicitly reports a well maintained pleasant trail surface.','The reviewer explicitly reports a damaged or poor trail surface.','Trail surface quality is not established.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    from transformers import pipeline
    classifier=pipeline('zero-shot-classification',model='facebook/bart-large-mnli',device=-1)
    reviews=pd.read_csv(a.reviews);proposals=[]
    for row in reviews.to_dict('records'):
        text=row.get('raw_review_text')
        if not isinstance(text,str) or not text.strip():continue
        # Short reviews only: truncation could omit a crucial negation or contrary report.
        if len(text.split())>250:
            proposals.append({'observation_id':row['observation_id'],'status':'needs manual review: long text','manually_reviewed':0});continue
        for target,labels in DESCRIPTIONS.items():
            r=classifier(text,candidate_labels=labels,multi_label=False)
            winner=labels.index(r['labels'][0])
            proposals.append({'observation_id':row['observation_id'],'target':target,
                'proposed_label':1 if winner==0 else 0 if winner==1 else None,
                'classification_score':r['scores'][0], 'source_text':text,
                'condition_source_url':row.get('condition_source_url'),
                'status':'AI proposal; verify meaning and copy an exact evidence quote',
                'manually_reviewed':0})
    with open(a.output,'w') as f:json.dump(proposals,f,indent=2,allow_nan=False)
    print('Wrote proposals only. Review them before entering labels in review_curation.csv.')
if __name__=='__main__':main()
