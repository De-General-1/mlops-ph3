import os
import numpy as np
import pandas as pd
import kagglehub
from datasets import DatasetDict, Dataset
import tensorflow as tf
from transformers import (
    AutoTokenizer,
    TFAutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    DefaultDataCollator
)
import mlflow
import mlflow.transformers
import dagshub
dagshub.init(repo_owner='De-General-1', repo_name='mlops-ph3', mlflow=True)

from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "google/flan-t5-base"
# <--- CHANGE 2: Update DATASET_NAME to our chosen Spotify dataset
DATASET_NAME = "devdope/900k-spotify" # This is the Kaggle ID for "500K+ Spotify Songs with Lyrics, Emotions & More"
OUTPUT_DIR = "RESULTS_MUSIC_REC" # <--- CHANGE 3: Update output directory name
MODEL_SAVE_PATH = "MODELS_MUSIC_REC" # <--- CHANGE 4: Update model save path

# It's good practice to get this from .env file.
# Your colleague's hardcoded IP suggests it's a static MLflow server.
# Ensure this IP is correct and reachable from where you run the script.
MFLOW_SERVER_IP = os.getenv("MFLOW_SERVER_IP", "34.251.243.175") # Get from .env or fallback
if MFLOW_SERVER_IP is None:
    raise ValueError("MFLOW_SERVER_IP environment variable is not set. Please set it to your MLflow server's public IP or ensure it's in your .env file.")

MLFLOW_TRACKING_URI = f"https://dagshub.com/De-General-1/mlops-ph3.mlflow"
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_SAVE_PATH, exist_ok=True)


tokenizer = None


def _load_dataset(dataset_name_param: str) -> DatasetDict:
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
        # 1. Rename columns to match expected names
        df_songs.rename(columns={
            'song': 'track_name',
            'Artist(s)': 'artist(s)_name'
        }, inplace=True)

        # 2. Identify "Good for..." columns for contextual tags
        contextual_cols = [col for col in df_songs.columns if col.startswith('Good for')]

        # 3. Create 'contextual_tags' by combining relevant "Good for..." columns
        # The Kaggle visualization shows these as int (0 or 1), so checking for 1 is correct.
        df_songs['contextual_tags'] = df_songs[contextual_cols].apply(
            lambda row: ", ".join([col.replace('Good for ', '') for col in contextual_cols if row[col] == 1]),
            axis=1
        )
        # Replace empty strings (if no tags apply) with NaN so dropna works on this column
        df_songs['contextual_tags'].replace('', np.nan, inplace=True) # Use np.nan instead of float('NaN')

        # 4. Select the necessary columns and drop rows with any missing values
        # Now, the column names 'emotion', 'track_name', 'artist(s)_name', 'contextual_tags' should exist in df_songs
        df_processed = df_songs[[
            'emotion',
            'track_name',
            'artist(s)_name',
            'contextual_tags', # Ensure this is included as a source column
            'text' # Include the 'text' (lyrics) column here, as it can be a rich input feature
        ]].dropna(
            subset=['emotion', 'track_name', 'artist(s)_name', 'contextual_tags', 'text'] # Dropna on all critical input/output components
        ).reset_index(drop=True)

        # 5. Convert relevant columns to string type explicitly
        df_processed['emotion'] = df_processed['emotion'].astype(str).str.strip()
        df_processed['contextual_tags'] = df_processed['contextual_tags'].astype(str).str.strip()
        df_processed['track_name'] = df_processed['track_name'].astype(str).str.strip()
        df_processed['artist(s)_name'] = df_processed['artist(s)_name'].astype(str).str.strip()
        df_processed['text'] = df_processed['text'].astype(str).str.strip() # Ensure lyrics are string

        # --- Creating Input and Target Texts for FLAN-T5 ---
        # Option 1: Generate song from emotion + tags
        # Input: "recommend song: feeling: [emotion]. context: [tags]."
        # Target: "[Track Name] by [Artist Name]"
        # This seems to be the most direct fit for your problem statement.
        df_processed['input_text'] = df_processed.apply(
            lambda row: f"recommend song: feeling: {row['emotion']}. " +
                        (f"context: {row['contextual_tags']}." if pd.notna(row['contextual_tags']) and row['contextual_tags'] != 'nan' and row['contextual_tags'] != '' else ""),
            axis=1
        )
        df_processed['input_text'] = df_processed['input_text'].str.replace('  ', ' ').str.strip() # Clean up double spaces

        df_processed['target_text'] = df_processed['track_name'] + " by " + df_processed['artist(s)_name']

        # Option 2 (Alternative/Bonus): Summarize song based on lyrics and metadata
        # Input: "summarize song: lyrics: [text]. emotion: [emotion]. tags: [tags]."
        # Target: "This song is about [summary of lyrics/key themes from emotion+tags]"
        # If you want to leverage lyrics more, this is a good prompt.
        # For now, let's stick to Option 1 for direct recommendation.

        # If you wanted to use lyrics as part of input
        # df_processed['input_text_with_lyrics'] = df_processed.apply(
        #     lambda row: f"recommend song: lyrics: {row['text']}. feeling: {row['emotion']}. " +
        #                 (f"context: {row['contextual_tags']}." if pd.notna(row['contextual_tags']) and row['contextual_tags'] != 'nan' and row['contextual_tags'] != '' else ""),
        #     axis=1
        # )


        # Optional: Reduce dataset size for quicker local iteration
        # KEEP THIS LINE FOR NOW FOR QUICK TESTING!
        df_processed = df_processed.head(1000)

        print(f"Processed DataFrame has {len(df_processed)} entries after cleaning.")
        print(f"Sample processed data (first 2 entries):\n{df_processed[['input_text', 'target_text']].head(2)}")

        # Create Hugging Face Dataset
        hf_dataset = Dataset.from_pandas(df_processed[['input_text', 'target_text']])

        train_test_split = hf_dataset.train_test_split(test_size=0.2, seed=42)
        raw_datasets = DatasetDict({
            'train': train_test_split['train'],
            'validation': train_test_split['test']
        })

        print("Dataset loaded, processed, and split successfully for music recommendation.")
        print(raw_datasets)
        return raw_datasets

    except Exception as e:
        print(f"Error loading dataset from Kaggle: {e}")
        raise


def load_tokenizer(model_name: str):
    print(f"Loading tokenizer for Model: {model_name}")
    global tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    print("Tokenizer loaded successfully.")
    return tokenizer

def load_model(model_name: str):
    print(f"Loading model: {model_name}")
    # <--- CHANGE 7: Load TF-specific model
    model = TFAutoModelForSeq2SeqLM.from_pretrained(model_name)
    print("Model loaded successfully.")
    return model

def tokenize_function(examples):
    # <--- CHANGE 8: Update column names for tokenization
    if "input_text" not in examples or "target_text" not in examples:
        raise ValueError("Dataset must contain 'input_text' and 'target_text' columns for tokenization.")

    # <--- CHANGE 9: Update task prefix for music recommendation
    input_texts = [f"recommend song: {text}" for text in examples["input_text"]]
    target_texts = examples["target_text"]

    model_inputs = tokenizer(input_texts, max_length=512, truncation=True)

    with tokenizer.as_target_tokenizer():
        labels = tokenizer(target_texts, max_length=128, truncation=True) # Max length for song titles/artists

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs


def compute_metrics(eval_pred):
    print("Compute metrics for text generation is not fully implemented. Relying on eval_loss for now.")
    # For full implementation, consider using the 'evaluate' library with ROUGE/BLEU.
    return {}


if __name__ == "__main__":
    raw_datasets = _load_dataset(DATASET_NAME)

    tokenizer = load_tokenizer(MODEL_NAME)
    model = load_model(MODEL_NAME)

    tokenized_datasets = raw_datasets.map(
        tokenize_function,
        batched=True,
        # <--- CHANGE 10: Remove new column names after tokenization
        remove_columns=[col for col in raw_datasets["train"].column_names if col not in ['input_ids', 'attention_mask', 'labels']]
    )

    # <--- CHANGE 11: Set dataset format to TensorFlow
    tokenized_datasets.set_format("tf")

    train_dataset = tokenized_datasets["train"]
    eval_dataset = tokenized_datasets["validation"]

    print(f"Training dataset size: {len(train_dataset)}")
    print(f"Evaluation dataset size: {len(eval_dataset)}")

    # Convert Hugging Face datasets to tf.data.Dataset
    tf_train_dataset = model.prepare_tf_dataset(
    train_dataset,
    tokenizer=tokenizer,
    batch_size=8,
    shuffle=True,
    collate_fn=DefaultDataCollator(return_tensors="tf")
    )

    tf_eval_dataset = model.prepare_tf_dataset(
    eval_dataset,
    tokenizer=tokenizer,
    batch_size=8,
    shuffle=False,
    collate_fn=DefaultDataCollator(return_tensors="tf")
    )

    # Compile the model
    optimizer = tf.keras.optimizers.Adam(learning_rate=2e-5)
    model.compile(optimizer=optimizer)

    # Setup MLflow autologging
    mlflow.tensorflow.autolog()

    # Train
    print("Starting model training...")
    model.fit(tf_train_dataset, validation_data=tf_eval_dataset, epochs=3)

    # Save model and tokenizer
    print(f"Saving fine-tuned model and tokenizer to {MODEL_SAVE_PATH}...")
    model.save_pretrained(MODEL_SAVE_PATH)
    tokenizer.save_pretrained(MODEL_SAVE_PATH)
    print("Model and tokenizer saved successfully.")

    # Log model to MLflow (this logs the saved model directory)
    print("Logging model to MLflow...")
    mlflow.transformers.log_model(
        transformers_model=MODEL_SAVE_PATH,
        name="huggingface-music-recommendation-model",
        tokenizer=tokenizer,
        task="text2text-generation",
        registered_model_name="ContextualSongRecommenderFlanT5"
    )
    print("Model logged to MLflow.")

print("Training script completed and MLflow run finished.")