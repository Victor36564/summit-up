"""Offline inference using the published pretrained all-MiniLM-L6-v2 ONNX model."""
from pathlib import Path
import json
import numpy as np

MODEL_ID='sentence-transformers/all-MiniLM-L6-v2'

class MiniLMEncoder:
    def __init__(self,model_dir=None):
        from tokenizers import Tokenizer
        import onnxruntime as ort
        self.model_dir=Path(model_dir or Path(__file__).resolve().parent/'pretrained/minilm')
        for name in ['model.onnx','tokenizer.json','provenance.json']:
            if not (self.model_dir/name).is_file():
                raise RuntimeError(f'Missing pretrained asset: {name}. Use the complete upgraded ML package; do not fall back to fake embeddings.')
        self.provenance=json.loads((self.model_dir/'provenance.json').read_text())
        self.tokenizer=Tokenizer.from_file(str(self.model_dir/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(self.model_dir/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.inputs={item.name for item in self.session.get_inputs()}

    def encode(self,texts,normalize_embeddings=True,batch_size=32):
        if isinstance(texts,str):texts=[texts]
        texts=list(texts)
        if not texts:return np.empty((0,384),dtype=np.float32)
        vectors=[]
        for start in range(0,len(texts),batch_size):
            batch=self.tokenizer.encode_batch([str(t) for t in texts[start:start+batch_size]])
            ids=np.asarray([x.ids for x in batch],dtype=np.int64)
            mask=np.asarray([x.attention_mask for x in batch],dtype=np.int64)
            types=np.asarray([x.type_ids for x in batch],dtype=np.int64)
            feed={k:v for k,v in {'input_ids':ids,'attention_mask':mask,'token_type_ids':types}.items() if k in self.inputs}
            outputs=self.session.run(None,feed)
            token_vectors=next((x for x in outputs if x.ndim==3 and x.shape[-1]==384),None)
            if token_vectors is None:raise RuntimeError('Unexpected MiniLM output; expected token embeddings with dimension 384')
            # Published model card: attention-masked mean pooling, then L2 normalization.
            embedded=(token_vectors*mask[:,:,None]).sum(axis=1)/np.maximum(mask.sum(axis=1,keepdims=True),1)
            if normalize_embeddings:embedded/=np.maximum(np.linalg.norm(embedded,axis=1,keepdims=True),1e-12)
            vectors.append(embedded.astype(np.float32))
        return np.concatenate(vectors,axis=0)
