import os
import pandas as pd
import kagglehub
import mlflow
import mlflow.transformers
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import evaluate
import nltk

# Ensure nltk 'punkt' is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Config
MLFLOW_TRACKING_URI = f"http://{os.getenv('MFLOW_SERVER_IP')}/"
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
MODEL_NAME = "MovieTitleGeneratorFlanT5"
DATASET_NAME = "tmdb/tmdb-movie-metadata"

# Load model & tokenizer from MLflow
model_uri = f"models:/{MODEL_NAME}/latest"
loaded = mlflow.transformers.load_model(model_uri)
model = loaded.model
tokenizer = loaded.tokenizer
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# Load test data from Kaggle
def load_test_data():
    path = kagglehub.dataset_download(DATASET_NAME)
    movies = pd.read_csv(os.path.join(path, "tmdb_5000_movies.csv"))
    credits = pd.read_csv(os.path.join(path, "tmdb_5000_credits.csv"))
    credits.rename(columns={'title': 'credit_title', 'movie_id': 'id'}, inplace=True)
    df = movies.merge(credits, on="id")
    df = df[['title', 'overview']].dropna().tail(100)
    return Dataset.from_pandas(df.rename(columns={'overview': 'description'}))

test_data = load_test_data()
preds, refs = [], []

# Start MLflow run
with mlflow.start_run(run_name="Model Evaluation"):
    mlflow.log_param("model_name", MODEL_NAME)
    mlflow.log_param("dataset", DATASET_NAME)
    mlflow.log_param("evaluation_size", len(test_data))

    rouge = evaluate.load("rouge")

    for example in test_data:
        input_text = f"generate title: {example['description']}"
        input_ids = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=512).input_ids.to(device)

        with torch.no_grad():
            output_ids = model.generate(
                input_ids, max_length=128, num_beams=4, early_stopping=True
            )
            generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)

        preds.append(generated)
        refs.append(example["title"])

    # Compute ROUGE
    rouge_scores = rouge.compute(predictions=preds, references=refs, use_stemmer=True)

    for k, v in rouge_scores.items():
        mlflow.log_metric(f"rouge_{k}", v * 100)

    # Save predictions and references
    mlflow.log_text("\n".join(preds), "outputs/predictions.txt")
    mlflow.log_text("\n".join(refs), "outputs/references.txt")

    # Sample console output
    print("\nSample predictions:")
    for i in range(min(5, len(preds))):
        print(f"Prediction: {preds[i]}")
        print(f"Reference : {refs[i]}")
        print("-" * 40)

    print("\nLogged ROUGE Scores:")
    for k, v in rouge_scores.items():
        print(f"{k}: {v:.4f}")
