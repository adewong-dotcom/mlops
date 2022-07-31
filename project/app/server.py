from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger
import joblib
from time import time
import datetime
import json

from sentence_transformers import SentenceTransformer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

GLOBAL_CONFIG = {
    "model": {
        "featurizer": {
            "sentence_transformer_model": "all-mpnet-base-v2",
            "sentence_transformer_embedding_dim": 768
        },
        "classifier": {
            "serialized_model_path": "./data/news_classifier.joblib"
        }
    },
    "service": {
        "log_destination": "./data/logs.out"
    }
}

class PredictRequest(BaseModel):
    source: str
    url: str
    title: str
    description: str


class PredictResponse(BaseModel):
    scores: dict
    label: str


class TransformerFeaturizer(BaseEstimator, TransformerMixin):
    def __init__(self, dim, sentence_transformer_model):
        self.dim = dim
        self.sentence_transformer_model = sentence_transformer_model

    #estimator. Since we don't have to learn anything in the featurizer, this is a no-op
    def fit(self, X, y=None):
        return self

    #transformation: return the encoding of the document as returned by the transformer model
    def transform(self, X, y=None):
        X_t = []
        for doc in X:
            X_t.append(self.sentence_transformer_model.encode(doc, normalize_embeddings = True))
        return X_t


class NewsCategoryClassifier:
    def __init__(self, config: dict) -> None:
        self.config = config
        """
        [TO BE IMPLEMENTED]
        1. Load the sentence transformer model and initialize the `featurizer` of type `TransformerFeaturizer` (Hint: revisit Week 1 Step 4)
        2. Load the serialized model as defined in GLOBAL_CONFIG['model'] into memory and initialize `model`
        """
        featurizer = TransformerFeaturizer(
            dim = (config["featurizer"]["sentence_tranformer_embedding_dim"]),
            sentence_transformer_model = SentenceTransformer(f"sentence-transformers/{config['featurizer']['sentence_transformer_model']}"))
                  )
        model = joblib.load(GLOBAL_CONFIG["model"]["classifier"]["serialized_model_path"])
        self.pipeline = Pipeline([
            ('transformer_featurizer', featurizer),
            ('classifier', model)
        ])

    def predict_proba(self, model_input: dict) -> dict:
        """
        [TO BE IMPLEMENTED]
        Using the `self.pipeline` constructed during initialization, 
        run model inference on a given model input, and return the 
        model prediction probability scores across all labels

        Output format: 
        {
            "label_1": model_score_label_1,
            "label_2": model_score_label_2 
            ...
        }
        """
        my_proba = self.pipeline.predict_proba([model_input]
        classes_to_probs = dict(zip(self.classes, my_proba[0].tolist()))
        
        return classes_to_probs

    def predict_label(self, model_input: dict) -> str:
        """
        [TO BE IMPLEMENTED]
        Using the `self.pipeline` constructed during initialization,
        run model inference on a given model input, and return the
        model prediction label

        Output format: predicted label for the model input
        """
        prediction = self.pipeline.predict([model_input])

        return prediction[0]


app = FastAPI()
data = {}
                                          

@app.on_event("startup")
def startup_event():
    """
        [TO BE IMPLEMENTED]
        2. Initialize the `NewsCategoryClassifier` instance to make predictions online. You should pass any relevant config parameters from `GLOBAL_CONFIG` that are needed by NewsCategoryClassifier 
        3. Open an output file to write logs, at the destimation specififed by GLOBAL_CONFIG['service']['log_destination']
        
        Access to the model instance and log file will be needed in /predict endpoint, make sure you
        store them as global variables
    """
    data['model'] = NewsCategoryClassifier(GLOBAL_CONFIG['model'])
    data['logger'] = open(GLOBAL_CONFIG['service']['log_destination'], "w", encoding ='utf-8')
                                               
    logger.info("Setup completed")


@app.on_event("shutdown")
def shutdown_event():
    # clean up
    """
        [TO BE IMPLEMENTED]
        1. Make sure to flush the log file and close any file pointers to avoid corruption
        2. Any other cleanups
    """
    data['logger'].flush()
    data['logger'].close()
    logger.info("Shutting down application")


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    # get model prediction for the input request
    # construct the data to be logged
    # construct response
    """
        [TO BE IMPLEMENTED]
        1. run model inference and get model predictions for model inputs specified in `request`
        2. Log the following data to the log file (the data should be logged to the file that was opened in `startup_event`, and writes to the path defined in GLOBAL_CONFIG['service']['log_destination'])
        {
            'timestamp': <YYYY:MM:DD HH:MM:SS> format, when the request was received,
            'request': dictionary representation of the input request,
            'prediction': dictionary representation of the response,
            'latency': time it took to serve the request, in millisec
        }
        3. Construct an instance of `PredictResponse` and return
    """
    time = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    start_time = lambda: int(time() * 1000)
    prediction = data['model'].predict_proba(request.description)
    label = data['model'].predict_label(request.description)
    response = PredictResponse(scores = prediction, label = label)
    end_time = lambda: int(time() * 1000)
    latency = end_time - start_time;
    to_log = {
            'timestamp': time,
            'request': request.dict(),
            'prediction': prediction,
            'latency': f"{latency} ms"
    }
    logger.info(to_log)
    data['logger'].write(json.dumps(to_log)+ "\n")
    data['logger'].flush()
    return response


@app.get("/")
def read_root():
    return {"Hello": "World"}
