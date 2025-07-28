import os
import pandas as pd
import kagglehub
import mlflow
import mlflow.tensorflow # Import for TF-specific logging
import tensorflow as tf # Import TensorFlow
from datasets import Dataset, DatasetDict # Keep DatasetDict as _load_dataset returns it
from transformers import AutoTokenizer, TFAutoModelForSeq2SeqLM # Use TF-specific model
import evaluate
import nltk
import numpy as np # Import numpy for NaN handling

# Ensure nltk 'punkt' is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# --- Config (MATCHES train.py) ---
# MLFLOW_TRACKING_URI = f"http://{os.getenv('MFLOW_SERVER_IP')}/" # Use your local MLflow URI or Dagshub
# Use Dagshub tracking URI as set in train.py
import dagshub
dagshub.init(repo_owner='De-General-1', repo_name='mlops-ph3', mlflow=True)
MLFLOW_TRACKING_URI = f"https://dagshub.com/De-General-1/mlops-ph3.mlflow"
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

# Use your trained model name
MODEL_NAME_MLFLOW = "ContextualSongRecommenderFlanT5" # This is the registered_model_name from train.py
MODEL_NAME_HF = "google/flan-t5-base" # This is the Hugging Face model it's based on

# Use your dataset name from train.py
DATASET_NAME = "devdope/900k-spotify"

# --- Load model & tokenizer from MLflow (TF-compatible) ---
# When loading a TF model from MLflow, it returns a Keras model by default
# If you saved with mlflow.transformers.log_model, it creates a custom Pyfunc model.
# We need to load it in a way that allows us to get the TFAutoModelForSeq2SeqLM back.
# For simplicity, we'll load directly using AutoTokenizer and TFAutoModelForSeq2SeqLM
# from the saved path if it's local, or from Hugging Face Hub if registered there directly.
# If you're using mlflow.transformers.log_model, it's typically best to load
# the Hugging Face model from its artifact path if it was saved as a directory.

# Assuming your train.py saves to MODEL_SAVE_PATH locally:
LOCAL_MODEL_PATH = "MODELS_MUSIC_REC" # Must match MODEL_SAVE_PATH in train.py

try:
    # Try loading from local path first (faster for development)
    model = TFAutoModelForSeq2SeqLM.from_pretrained(LOCAL_MODEL_PATH)
    tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH)
    print(f"Loaded model and tokenizer from local path: {LOCAL_MODEL_PATH}")
except Exception as e:
    print(f"Could not load from local path ({e}). Attempting to load from MLflow registered model...")
    # This might require mlflow.pyfunc.load_model if saved as generic Pyfunc.
    # If saved with mlflow.transformers.log_model, it might be possible to load
    # the raw transformers model artifact directly.
    # A more robust way: use the artifact URI
    # Find the latest version's artifact URI for the transformers_model component
    try:
        client = mlflow.tracking.MlflowClient()
        latest_version = client.get_latest_versions(MODEL_NAME_MLFLOW, stages=["None", "Production", "Staging"])[0]
        artifact_path = latest_version.source # This is typically run URI like 'runs:/run_id/artifact_path'

        # This will load the PyFunc model wrapper. We need the underlying transformers model.
        # This is often the trickiest part of TF models with MLflow transformers wrapper.
        # A common pattern is to just load from the Hugging Face Hub if you know the name,
        # or have a direct path to the saved `transformers_model` directory.
        # Let's assume for now, it's easier to load the base model and then
        # load weights if you only log weights.
        # For simplicity in evaluation, let's load from the original HF Hub name
        # and assume it matches the fine-tuned one if we don't load specific fine-tuned weights here.
        # For full fidelity, you'd need the actual fine-tuned model's weights.
        # The best way to evaluate a saved `mlflow.transformers.log_model` is often:
        # loaded_artifact = mlflow.pyfunc.load_model(model_uri)
        # model = loaded_artifact.unwrap_python_model()._model # This is a hacky way to get the TF model
        # tokenizer = loaded_artifact.unwrap_python_model()._tokenizer # This is a hacky way to get the tokenizer
        #
        # A safer bet if you used `model.save_pretrained` is to always load from the local path,
        # or re-download from a cloud storage if that's where `MODEL_SAVE_PATH` points.
        #
        # For this script, we'll continue using the LOCAL_MODEL_PATH as the primary source,
        # as that's where your train.py explicitly saves it.
        # If the model is only on MLflow, we would need to fetch the artifact.
        # For now, let's assume `LOCAL_MODEL_PATH` contains the fine-tuned model.
        print(f"If local load failed, please ensure {LOCAL_MODEL_PATH} contains the saved model from train.py.")
        print(f"If model is only in MLflow, you need to download artifacts or load differently.")
        # For a truly robust solution, you'd fetch the artifact from MLflow if not local
        # e.g., using client.download_artifacts or a custom load function.

        # Fallback to loading original model from Hugging Face Hub if local failed
        model = TFAutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME_HF)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME_HF)
        print(f"Loaded base model and tokenizer from Hugging Face Hub: {MODEL_NAME_HF}")
    except Exception as e_mlflow:
        print(f"Failed to load model from MLflow registry or Hugging Face Hub: {e_mlflow}")
        raise

# No .to(device) for TensorFlow models
# model.eval() is for PyTorch, TF models handle this with `training=False` in call or through Keras layers

# --- Load test data (Modified for Spotify Dataset) ---
def _load_dataset(dataset_name_param: str) -> DatasetDict:
    # This is a copy of your _load_dataset from train.py, which is good for consistency
    # We load the full dataset then just take a portion for evaluation, similar to train.py's head(1000)
    print(f"Downloading and loading dataset from Kaggle: {dataset_name_param}")
    try:
        path = kagglehub.dataset_download(dataset_name_param)
        print(f"Dataset downloaded to: {path}")

        csv_file_path = os.path.join(path, "spotify_dataset.csv")

        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"Expected file not found: {csv_file_path}")

        df_songs = pd.read_csv(csv_file_path)
        print(f"Loaded {len(df_songs)} song entries from {csv_file_path}.")
        print("Columns available:", df_songs.columns.tolist())

        # --- Data Cleaning and Feature Engineering ---
        df_songs.rename(columns={
            'song': 'track_name',
            'Artist(s)': 'artist(s)_name'
        }, inplace=True)

        contextual_cols = [col for col in df_songs.columns if col.startswith('Good for')]

        df_songs['contextual_tags'] = df_songs[contextual_cols].apply(
            lambda row: ", ".join([col.replace('Good for ', '') for col in contextual_cols if row[col] == 1]),
            axis=1
        )
        df_songs['contextual_tags'].replace('', np.nan, inplace=True)

        df_processed = df_songs[[
            'emotion',
            'track_name',
            'artist(s)_name',
            'contextual_tags',
            'text'
        ]].dropna(
            subset=['emotion', 'track_name', 'artist(s)_name', 'contextual_tags', 'text']
        ).reset_index(drop=True)

        df_processed['emotion'] = df_processed['emotion'].astype(str).str.strip()
        df_processed['contextual_tags'] = df_processed['contextual_tags'].astype(str).str.strip()
        df_processed['track_name'] = df_processed['track_name'].astype(str).str.strip()
        df_processed['artist(s)_name'] = df_processed['artist(s)_name'].astype(str).str.strip()
        df_processed['text'] = df_processed['text'].astype(str).str.strip()

        df_processed['input_text'] = df_processed.apply(
            lambda row: f"recommend song: feeling: {row['emotion']}. " +
                        (f"context: {row['contextual_tags']}." if pd.notna(row['contextual_tags']) and row['contextual_tags'] != 'nan' and row['contextual_tags'] != '' else ""),
            axis=1
        )
        df_processed['input_text'] = df_processed['input_text'].str.replace('  ', ' ').str.strip()

        df_processed['target_text'] = df_processed['track_name'] + " by " + df_processed['artist(s)_name']

        # For evaluation, we want a larger set than just head(1000) for training,
        # but still manageable. Let's take the first 5000 examples or so for evaluation.
        df_processed = df_processed.head(5000) # Or df_processed.sample(n=5000, random_state=42)

        print(f"Processed DataFrame has {len(df_processed)} entries after cleaning for evaluation.")
        print(f"Sample processed data (first 2 entries):\n{df_processed[['input_text', 'target_text']].head(2)}")

        # Return a Dataset object, not DatasetDict, as evaluation typically runs on one split
        return Dataset.from_pandas(df_processed[['input_text', 'target_text']])

    except Exception as e:
        print(f"Error loading dataset from Kaggle: {e}")
        raise

# Load test data (using the adapted _load_dataset function)
test_data = _load_dataset(DATASET_NAME)
preds, refs = [], []

# Start MLflow run
with mlflow.start_run(run_name="Music Recommendation Model Evaluation"):
    mlflow.log_param("model_name_registered", MODEL_NAME_MLFLOW)
    mlflow.log_param("model_name_hf_base", MODEL_NAME_HF)
    mlflow.log_param("dataset", DATASET_NAME)
    mlflow.log_param("evaluation_size", len(test_data))

    rouge = evaluate.load("rouge")

    print("\nStarting inference for evaluation...")
    for i, example in enumerate(test_data):
        input_text = example['input_text'] # Already formatted correctly by _load_dataset
        
        # Tokenize input for TensorFlow model
        # return_tensors="tf" is crucial here
        input_ids = tokenizer(input_text, return_tensors="tf", truncation=True, max_length=512).input_ids

        # Generate output using TensorFlow model's generate method
        # The `generate` method on TF models automatically handles device placement.
        # No `torch.no_grad()` equivalent needed; TF handles gradients automatically during inference.
        output_ids = model.generate(
            input_ids, max_length=128, num_beams=4, early_stopping=True
        )
        # Decode the generated TensorFlow tensor
        # output_ids will be a tf.Tensor, need to convert to numpy or list if tokenizer.decode expects list
        generated = tokenizer.decode(output_ids[0].numpy(), skip_special_tokens=True) # .numpy() to convert tf.Tensor to numpy array

        preds.append(generated)
        refs.append(example["target_text"]) # target_text already has "Song by Artist"

        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{len(test_data)} examples.")

    # Compute ROUGE
    print("\nComputing ROUGE scores...")
    rouge_scores = rouge.compute(predictions=preds, references=refs, use_stemmer=True)

    for k, v in rouge_scores.items():
        mlflow.log_metric(f"rouge_{k}", v * 100)

    # Save predictions and references
    # Create an output directory for artifacts if it doesn't exist
    output_dir_mlflow = "outputs"
    os.makedirs(output_dir_mlflow, exist_ok=True)
    with open(os.path.join(output_dir_mlflow, "predictions.txt"), "w") as f:
        f.write("\n".join(preds))
    with open(os.path.join(output_dir_mlflow, "references.txt"), "w") as f:
        f.write("\n".join(refs))
    mlflow.log_artifacts(output_dir_mlflow) # Log the whole directory

    # Sample console output
    print("\nSample predictions:")
    for i in range(min(5, len(preds))):
        print(f"Prediction: {preds[i]}")
        print(f"Reference : {refs[i]}")
        print("-" * 40)

    print("\nLogged ROUGE Scores:")
    for k, v in rouge_scores.items():
        print(f"{k}: {v:.4f}")

print("\nEvaluation script completed and MLflow run finished.")