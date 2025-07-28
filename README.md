# Metrics
I am choosing two fundamental metrics to evaluate generated text:

* **Coherence**: Is the output logically consistent, grammatically sound, and fluent?
* **Relevance**: Does the output directly address the input prompt or context?

Let's define these metrics precisely in a way that supports automation

## 1. **Coherence** — Definition & Metric

> **Definition:** ***The degree to which the generated text forms a clear, logical, and fluent structure — it "makes sense" and isn’t gibberish.***

### Evaluation Method: **Perplexity**

* **What is it?**
  A measure of how “surprised” a language model is by a piece of text. Lower = more fluent/coherent.

* **How to use it?**

  * Use a pre-trained causal language model (e.g., `gpt2`) to evaluate perplexity of the generated text.
  * Average token-level log probability.

### Metric:

```python
coherence_score = perplexity(generated_text)
```

* **Threshold (example):**

  * `perplexity < 40` → Coherent
  * `perplexity >= 40` → Incoherent or low quality


## 2. **Relevance** — Definition & Metric

> **Definition:** ***The semantic similarity between the input prompt and the generated output — does the response stay on-topic?***

### Evaluation Method: **Cosine Similarity of Sentence Embeddings**

* **Tool:** Use `sentence-transformers` like `all-MiniLM-L6-v2`
* **Process:**

  * Encode both prompt and generated text
  * Compute cosine similarity

### Metric:

```python
relevance_score = cosine_similarity(embedding(prompt), embedding(generated_text))
```

* **Threshold (example):**

  * `similarity > 0.6` → Relevant
  * `similarity <= 0.6` → Off-topic or weakly related