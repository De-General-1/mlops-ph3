import os
import numpy as np
import pandas as pd
import kagglehub
from datasets import DatasetDict, Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
import mlflow
import mlflow.transformers

from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "google/flan-t5-base"
DATASET_NAME = "tmdb/tmdb-movie-metadata"
OUTPUT_DIR = "RESULTS"
MODEL_SAVE_PATH = "MODELS"

MFLOW_SERVER_IP = os.getenv('MFLOW_SERVER_IP')
if MFLOW_SERVER_IP is None:
    raise ValueError("MFLOW_SERVER_IP environment variable is not set. Please set it to your MLflow server's public IP or ensure it's in your .env file.")
MLFLOW_TRACKING_URI = f"http://{MFLOW_SERVER_IP}/"
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_SAVE_PATH, exist_ok=True)


tokenizer = None


def _load_dataset(dataset_name_param: str) -> DatasetDict:
    print(f"Downloading and loading dataset from Kaggle: {dataset_name_param}")
    try:
       
       
        path = kagglehub.dataset_download(dataset_name_param)
        print(f"Dataset downloaded to: {path}")

       
        movies_csv_file = os.path.join(path, "tmdb_5000_movies.csv")
       

        if not os.path.exists(movies_csv_file):
            raise FileNotFoundError(f"Expected file not found: {movies_csv_file}")

       
        df_movies = pd.read_csv(movies_csv_file)
        print(f"Loaded {len(df_movies)} movie entries from {movies_csv_file}.")
        print("Columns available:", df_movies.columns.tolist())

       
       
        if 'overview' not in df_movies.columns or 'title' not in df_movies.columns:
            raise ValueError("Required columns 'overview' and 'title' not found in the dataset. Please check the CSV structure.")

       
        df_processed = df_movies[['overview', 'title']].dropna().reset_index(drop=True)
       
        df_processed = df_processed.rename(columns={'overview': 'description'})
        df_processed = df_processed.head(5)

        print(f"Processed DataFrame has {len(df_processed)} entries after cleaning.")
        print(f"Sample processed data (first 2 entries):\n{df_processed.head(2)}")

       
        hf_dataset = Dataset.from_pandas(df_processed)

       
       
        train_test_split = hf_dataset.train_test_split(test_size=0.2, seed=42)
        raw_datasets = DatasetDict({
            'train': train_test_split['train'],
            'validation': train_test_split['test']
        })

        print("Dataset loaded, processed, and split successfully.")
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
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    print("Model loaded successfully.")
    return model

def tokenize_function(examples):
   
   

    if "description" not in examples or "title" not in examples:
        raise ValueError("Dataset must contain 'description' and 'title' columns for tokenization.")

   
    input_texts = [f"generate title: {desc}" for desc in examples["description"]]
    target_texts = examples["title"]

   
    model_inputs = tokenizer(input_texts, max_length=512, truncation=True)

   
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(target_texts, max_length=128, truncation=True)

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs



def compute_metrics(eval_pred):
   
   
    print("Compute metrics for text generation is not fully implemented. Using default Trainer evaluation.")
    return {}


if __name__ == "__main__":
   
    raw_datasets = _load_dataset(DATASET_NAME)

    tokenizer = load_tokenizer(MODEL_NAME)
    model = load_model(MODEL_NAME)

   
   
   
    tokenized_datasets = raw_datasets.map(
        tokenize_function,
        batched=True,
        remove_columns=raw_datasets["train"].column_names
    )

   
    tokenized_datasets.set_format("torch")

    train_dataset = tokenized_datasets["train"]
    eval_dataset = tokenized_datasets["validation"]

    print(f"Training dataset size: {len(train_dataset)}")
    print(f"Evaluation dataset size: {len(eval_dataset)}")

   
    print("Configuring training arguments...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8, 
        num_train_epochs=3,
        weight_decay=0.01,
        logging_dir="./logs",
        logging_steps=100,
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="none",
       
       
        fp16=False,
    )

   
   
    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

   
    print("Initializing Trainer...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=None,
    )

   
    print("Starting model training (this might take a while)...")
    trainer.train()
    print("Model training finished.")

   
    print("Evaluating the model and logging metrics...")
    eval_results = trainer.evaluate()
    for key, value in eval_results.items():
        mlflow.log_metric(key, value)
    print("Metrics logged successfully.")

   
    print(f"Saving fine-tuned model and tokenizer to {MODEL_SAVE_PATH}...")
    trainer.save_model(MODEL_SAVE_PATH)
    tokenizer.save_pretrained(MODEL_SAVE_PATH)
    print("Model and tokenizer saved locally.")

   
    print("Logging model to MLflow...")
    mlflow.transformers.log_model(
        transformers_model=MODEL_SAVE_PATH,
        name="huggingface-model",
        tokenizer=tokenizer,
        task="text2text-generation",
        registered_model_name="MovieTitleGeneratorFlanT5"
    )
    print("Model logged to MLflow successfully.")

print("Training script completed and MLflow run finished.")