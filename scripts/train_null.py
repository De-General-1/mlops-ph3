import os
import numpy as np
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

MODEL_NAME = "distilbert-base-uncased"
DATASET_NAME = "imdb"
OUTPUT_DIR = "RESULTS"
MODEL_SAVE_PATH = "MODELS"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_SAVE_PATH, exist_ok=True)

#  Load Dataset 
def _load_dataset(DATASET_NAME):
    print(f"Loading dataset: {DATASET_NAME}")

    raw_datasets = load_dataset(DATASET_NAME)
    print("Dataset loaded successfully.")
    print(raw_datasets)

    return raw_datasets

def load_tokenizer(MODEL_NAME):
    print(f"Loading tokenizer for Model: {MODEL_NAME}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print("Tokenizer loaded successfully.")

    return tokenizer

def load_model(MODEL_NAME):
    print(f"Loading model: {MODEL_NAME}")

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    print("Model loaded successfully.")

    return model

def tokenize_function(examples):
    # This function takes text examples and tokenizes them using the loaded tokenizer.
    # It also truncates sequences longer than the model's max input length and pads them
    # to the longest sequence in the batch (or a specified max_length).
    return tokenizer(examples["text"], truncation=True, padding=True)

# This function is passed to the Trainer to compute evaluation metrics.
def compute_metrics(p):
    """
    Computes accuracy, precision, recall, and f1-score for evaluation.
    Args:
        p (EvalPrediction): A tuple containing predictions and labels.
    Returns:
        dict: A dictionary of metrics.
    """
    preds = np.argmax(p.predictions, axis=1) # Get the predicted class (0 or 1)
    # Calculate precision, recall, f1-score for binary classification
    precision, recall, f1, _ = precision_recall_fscore_support(p.label_ids, preds, average='binary')
    acc = accuracy_score(p.label_ids, preds)
    return {
        "accuracy": acc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

if __name__ == "__main__":
    raw_datasets = _load_dataset(DATASET_NAME)
    tokenizer = load_tokenizer(MODEL_NAME)
    model = load_model(MODEL_NAME)

    # Apply the tokenization function to both train and test splits of the dataset
    tokenized_datasets = raw_datasets.map(tokenize_function, batched=True)
    print("Data tokenization complete.")
    print(tokenized_datasets)

    # Rename the 'label' column to 'labels' as required by the Trainer API
    # and set the format to PyTorch tensors.
    tokenized_datasets = tokenized_datasets.rename_column("label", "labels")
    tokenized_datasets.set_format("torch", columns=["input_ids", "attention_mask", "labels"])

    # Split the dataset into training and evaluation sets
    # This uses the first 24990 examples for training and the last 10 examples for evaluation
    train_dataset = tokenized_datasets["train"].shuffle(seed=42).select(range(24990, 25000))
    eval_dataset = tokenized_datasets["train"].shuffle(seed=42).select(range(24990, 25000))

    print(f"Training dataset size: {len(train_dataset)}")
    print(f"Evaluation dataset size: {len(eval_dataset)}")

    # Configure Training Arguments
    print("Configuring training arguments...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,          # directory for storing logs and checkpoints
        eval_strategy="epoch",    # evaluate at the end of each epoch
        learning_rate=2e-5,             # learning rate
        per_device_train_batch_size=16, # batch size for training
        per_device_eval_batch_size=16,  # batch size for evaluation
        num_train_epochs=3,             # number of training epochs
        weight_decay=0.01,              # weight decay for regularization
        logging_dir="./logs",           # directory for storing logs
        logging_steps=100,              # log every 100 steps
        save_strategy="epoch",          # save model checkpoint at the end of each epoch
        load_best_model_at_end=True,    # load the best model (based on eval_loss) at the end of training
        metric_for_best_model="f1",     # metric to use to compare models
        report_to="none",               # Do not report to any external services for this local setup
    )

    # Initialize Trainer
    print("Initializing Trainer...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer, # Pass tokenizer to trainer to ensure it's saved with the model
        compute_metrics=compute_metrics,
    )

    # Train the Model
    print("Starting model training (this might take a while)...")
    trainer.train()
    print("Model training finished.")

    # Save the Model
    print(f"Saving fine-tuned model and tokenizer to {MODEL_SAVE_PATH}...")
    
    trainer.save_model(MODEL_SAVE_PATH)
    tokenizer.save_pretrained(MODEL_SAVE_PATH)
    
    print("Model and tokenizer saved successfully.")

    print("Training script completed.")