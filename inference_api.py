import os
import uvicorn
import pandas as pd
import kagglehub
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mlflow
import mlflow.transformers
from transformers import Pipeline
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ast
from fastapi.responses import HTMLResponse

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
MFLOW_SERVER_IP = os.getenv('MFLOW_SERVER_IP')
if MFLOW_SERVER_IP is None:
    raise ValueError("MFLOW_SERVER_IP environment variable is not set. Please set it to your MLflow server's public IP or ensure it's in your .env file.")
MLFLOW_TRACKING_URI = f"http://{MFLOW_SERVER_IP}/"
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

REGISTERED_MODEL_NAME = "MovieTitleGeneratorFlanT5"
MODEL_VERSION_OR_STAGE = "latest"

# --- Global Variables for Models and Data ---
text_generation_pipeline: Pipeline = None
movies_df = None # DataFrame to store movie metadata for recommendations
cosine_sim = None # Cosine similarity matrix for recommendations
indices = None # Series mapping movie titles to their indices

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Movie AI Services",
    description="API for suggesting movie titles and recommending movies.",
    version="0.1.0",
)

# --- Request Body Models ---
class GenerateTitleRequest(BaseModel):
    """
    Defines the structure of the request body for movie title generation.
    """
    description: str

class RecommendMovieRequest(BaseModel):
    """
    Defines the structure of the request body for movie recommendations.
    """
    movie_title: str
    num_recommendations: int = 10 

# Function to convert stringified list of dicts to a list of names
def convert_json_to_list(obj):
    if isinstance(obj, str):
        L = []
        try:
            for i in ast.literal_eval(obj):
                L.append(i['name'])
        except (ValueError, SyntaxError):
            return [] # Handle malformed JSON strings
        return [] # Return empty list if parsing fails or obj is not a string
    return []

# Function to get director's name from crew json
def get_director(obj):
    if isinstance(obj, str):
        try:
            for i in ast.literal_eval(obj):
                if i['job'] == 'Director':
                    return i['name']
        except (ValueError, SyntaxError):
            return '' # Handle malformed JSON strings
    return ''

# Function to combine features into a single string
def combine_features(row):
    features = []
    # Ensure features are lists before extending
    if isinstance(row['keywords'], list):
        features.extend([i.replace(" ", "") for i in row['keywords']])
    if isinstance(row['genres'], list):
        features.extend([i.replace(" ", "") for i in row['genres']])
    if isinstance(row['cast'], list):
        features.extend([i.replace(" ", "") for i in row['cast'][:3]]) # Top 3 actors
    if isinstance(row['director'], str):
        features.append(row['director'].replace(" ", ""))
    if isinstance(row['overview'], str):
        features.append(row['overview'])
    return " ".join(features)

def normalize_title(title: str) -> str:
    """
    Normalize movie titles for case-insensitive and hyphen-insensitive matching.
    """
    # return title
    return title.lower().replace("-", "").strip()

# --- Data Loading and Preprocessing for Recommendation System ---
@app.on_event("startup")
async def load_models_and_data_on_startup():
    """
    Loads the MLflow model (for generation) and prepares data for the recommendation system
    when the FastAPI application starts.
    """
    global text_generation_pipeline, movies_df, cosine_sim, indices

    # 1. Load Flan-T5 Model for Title Generation
    print(f"MLFlow Registry URL set to {MLFLOW_TRACKING_URI}")
    print(f"Loading model '{REGISTERED_MODEL_NAME}' version/stage '{MODEL_VERSION_OR_STAGE}' from MLflow Registry...")
    try:
        model_uri = f"models:/{REGISTERED_MODEL_NAME}/{MODEL_VERSION_OR_STAGE}"
        text_generation_pipeline = mlflow.transformers.load_model(model_uri)
        
        if text_generation_pipeline.device.type == "cuda":
            print("Title Generation Model pipeline loaded and moved to GPU.")
        else:
            print("No GPU found, Title Generation Model pipeline will run on CPU.")
        print("Title Generation Model pipeline loaded successfully!")
    except Exception as e:
        print(f"Failed to load title generation model: {e}")
        raise RuntimeError(f"Could not load title generation model on startup: {e}")

    # 2. Prepare Data for Movie Recommendation System
    print("Preparing data for Movie Recommendation System...")
    try:
        path = kagglehub.dataset_download("tmdb/tmdb-movie-metadata")
        movies_csv_file = os.path.join(path, "tmdb_5000_movies.csv")
        credits_csv_file = os.path.join(path, "tmdb_5000_credits.csv")

        if not os.path.exists(movies_csv_file) or not os.path.exists(credits_csv_file):
            raise FileNotFoundError("TMDB movie or credits CSV files not found after download.")

        df_movies = pd.read_csv(movies_csv_file)
        df_credits = pd.read_csv(credits_csv_file)

        # Rename 'title' in df_credits to avoid conflict with df_movies' 'title' during merge
        # We will use the 'title' from df_movies as the primary movie title.
        df_credits.rename(columns={'title': 'credit_title', 'movie_id': 'id'}, inplace=True)
        
        # Merge the two dataframes on 'id'
        movies_df = df_movies.merge(df_credits, on='id')

        # Drop rows with missing 'overview' or 'title' (from df_movies)
        movies_df.dropna(subset=['overview', 'title'], inplace=True)
        movies_df.reset_index(drop=True, inplace=True)

        # Process JSON columns
        features_to_process = ['genres', 'keywords', 'cast', 'crew']
        for feature in features_to_process:
            movies_df[feature] = movies_df[feature].apply(convert_json_to_list)

        # Extract director
        movies_df['director'] = movies_df['crew'].apply(get_director)

        # Combine relevant features into a single 'soup' string
        movies_df['soup'] = movies_df.apply(combine_features, axis=1)
        
        # Handle potential NaN values in 'soup' after combining features
        movies_df.dropna(subset=['soup'], inplace=True)
        movies_df = movies_df[movies_df['soup'].str.strip() != ''].reset_index(drop=True)


        # Initialize TF-IDF Vectorizer
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(movies_df['soup'])

        # Compute cosine similarity matrix
        cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

        # Create a Series that maps normalized movie titles to their indices
        indices = pd.Series(
            movies_df.index, 
            index=movies_df['title'].apply(normalize_title)
        ).drop_duplicates()

        print("Movie Recommendation System data prepared successfully!")
        print(f"Recommendation data loaded for {len(movies_df)} movies.")

    except Exception as e:
        print(f"Failed to prepare recommendation data: {e}")
        raise RuntimeError(f"Could not prepare recommendation data on startup: {e}")

# --- Recommendation Logic Function ---
def get_recommendations(title: str, num_recommendations: int):
    """
    Generates content-based movie recommendations.
    """
    normalized_title = normalize_title(title)
    if normalized_title not in indices:
        return {"error": f"Movie title '{title}' not found in the database. Please try another title."}

    idx = indices[normalized_title]
    sim_scores = list(enumerate(cosine_sim[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Get the scores of the N most similar movies (excluding itself)
    # Ensure we don't go out of bounds if num_recommendations is too large
    sim_scores = sim_scores[1:num_recommendations+1] 

    movie_indices = [i[0] for i in sim_scores]
    return movies_df['title'].iloc[movie_indices].tolist()


# --- API Endpoints ---

@app.post("/generate_title")
async def generate_movie_title(request: GenerateTitleRequest):
    """
    Generates a movie title based on the provided description using Flan-T5.
    """
    if text_generation_pipeline is None:
        raise HTTPException(status_code=503, detail="Title generation model not loaded yet. Please try again in a moment.")

    description = request.description
    print(f"Received title generation request for description: '{description}'")

    try:
        input_text_for_pipeline = f"generate title: {description}"
        
        results = text_generation_pipeline(
            input_text_for_pipeline,
            max_new_tokens=128,
            num_beams=5,
            early_stopping=True
        )

        generated_title = results[0]["generated_text"]
        print(f"Generated title: '{generated_title}'")

        return {"suggested_title": generated_title}

    except Exception as e:
        print(f"Error during title generation: {e}")
        raise HTTPException(status_code=500, detail=f"Title generation failed: {e}")

@app.post("/recommend_movie")
async def recommend_movie(request: RecommendMovieRequest):
    """
    Recommends movies based on a given movie title using content-based filtering.
    """
    if movies_df is None or cosine_sim is None or indices is None:
        raise HTTPException(status_code=503, detail="Recommendation data not loaded yet. Please try again in a moment.")

    movie_title = request.movie_title
    num_recommendations = request.num_recommendations
    print(f"Received recommendation request for movie: '{movie_title}' with {num_recommendations} recommendations.")

    try:
        recommendations = get_recommendations(movie_title, num_recommendations)
        if "error" in recommendations:
            raise HTTPException(status_code=404, detail=recommendations["error"])
        return {"recommended_movies": recommendations}
    except Exception as e:
        print(f"Error during movie recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Movie recommendation failed: {e}")

@app.get("/", response_class=HTMLResponse)
async def root_ui():
    return """
        <html lang="en">
            <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Movie AI Services</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body
                class="bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors duration-300"
            >
                <div class="flex h-screen">
                <!-- Sidebar -->
                <aside class="w-64 bg-white dark:bg-gray-800 shadow-md flex flex-col">
                    <div class="p-4 text-xl font-bold">Movie AI</div>
                    <nav class="flex-1 p-4 space-y-2">
                    <button
                        id="nav-generate"
                        class="w-full text-left px-3 py-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                    >
                        Generate
                    </button>
                    <button
                        id="nav-recommend"
                        class="w-full text-left px-3 py-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                    >
                        Recommend
                    </button>
                    </nav>
                </aside>

                <!-- Main Content -->
                <main class="flex-1 flex flex-col">
                    <!-- Header -->
                    <header
                    class="p-4 flex justify-between items-center border-b border-gray-200 dark:border-gray-700"
                    >
                    <h1 class="text-2xl font-bold">Mov Flan</h1>
                    <button
                        id="theme-toggle"
                        class="px-3 py-2 rounded bg-gray-300 dark:bg-gray-700"
                    >
                        Toggle Theme
                    </button>
                    </header>

                    <!-- Content Sections -->
                    <section
                    id="generate-section"
                    class="flex-1 flex flex-col p-4 space-y-4"
                    >
                    <h2 class="text-xl font-semibold">Generate a Movie Title</h2>
                    <div
                        id="chat-generate"
                        class="flex-1 overflow-y-auto p-4 border rounded bg-white dark:bg-gray-800 space-y-2"
                    >
                        <!-- Pre-populated messages -->
                    </div>
                    <div class="flex space-x-2">
                        <textarea
                        id="description"
                        rows="2"
                        placeholder="Enter movie description..."
                        class="flex-1 p-2 border rounded dark:bg-gray-700"
                        ></textarea>
                        <button
                        onclick="generateTitle()"
                        class="px-4 py-2 bg-blue-600 text-white rounded"
                        >
                        Send
                        </button>
                    </div>
                    </section>

                    <section
                    id="recommend-section"
                    class="flex-1 flex-col p-4 space-y-4 hidden"
                    >
                    <h2 class="text-xl font-semibold">Recommend Movies</h2>
                    <div
                        id="chat-recommend"
                        class="flex-1 overflow-y-auto p-4 border rounded bg-white dark:bg-gray-800 space-y-2"
                    >
                        <!-- Pre-populated messages -->
                    </div>
                    <div class="flex space-x-2">
                        <input
                        id="movie-title"
                        type="text"
                        placeholder="Enter movie title..."
                        class="flex-1 p-2 border rounded dark:bg-gray-700"
                        />
                        <input
                        id="num-recommendations"
                        type="number"
                        min="1"
                        value="5"
                        class="w-24 p-2 border rounded dark:bg-gray-700"
                        />
                        <button
                        onclick="recommendMovie()"
                        class="px-4 py-2 bg-blue-600 text-white rounded"
                        >
                        Send
                        </button>
                    </div>
                    </section>
                </main>
                </div>

                <script>
                // Dark mode toggle
                const themeToggle = document.getElementById("theme-toggle");
                const userTheme = localStorage.getItem("theme");
                if (userTheme === "dark") document.documentElement.classList.add("dark");
                themeToggle.addEventListener("click", () => {
                    document.documentElement.classList.toggle("dark");
                    localStorage.setItem(
                    "theme",
                    document.documentElement.classList.contains("dark") ? "dark" : "light"
                    );
                });

                // Sidebar navigation
                const generateSection = document.getElementById("generate-section");
                const recommendSection = document.getElementById("recommend-section");
                document.getElementById("nav-generate").addEventListener("click", () => {
                    generateSection.classList.remove("hidden");
                    recommendSection.classList.add("hidden");
                });
                document.getElementById("nav-recommend").addEventListener("click", () => {
                    recommendSection.classList.remove("hidden");
                    generateSection.classList.add("hidden");
                });

                // Pre-populated chat data
                const chatGenerate = [
                    { sender: "user", text: "A fantasy movie about dragons and knights." },
                    { sender: "ai", text: 'How about "Dragons of the Silver Keep"?' },
                ];
                const chatRecommend = [
                    { sender: "user", text: "Recommend movies like Inception." },
                    {
                    sender: "ai",
                    text: "Here are some: Interstellar, Shutter Island, Tenet.",
                    },
                ];

                function renderChat(containerId, messages) {
                    const container = document.getElementById(containerId);
                    container.innerHTML = "";
                    messages.forEach((msg) => {
                    const div = document.createElement("div");
                    div.className = `p-2 rounded max-w-lg ${
                        msg.sender === "user"
                        ? "bg-blue-200 dark:bg-blue-700 self-end"
                        : "bg-gray-200 dark:bg-gray-600 self-start"
                    }`;
                    div.innerText = msg.text;
                    container.appendChild(div);
                    });
                }
                renderChat("chat-generate", chatGenerate);
                renderChat("chat-recommend", chatRecommend);

                // API calls with chat updates
                async function generateTitle() {
                    const desc = document.getElementById("description").value;
                    chatGenerate.push({ sender: "user", text: desc });
                    renderChat("chat-generate", chatGenerate);
                    const res = await fetch("/generate_title", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ description: desc }),
                    });
                    const data = await res.json();
                    chatGenerate.push({
                    sender: "ai",
                    text: data.suggested_title || data.detail || "Error",
                    });
                    renderChat("chat-generate", chatGenerate);
                }

                async function recommendMovie() {
                    const title = document.getElementById("movie-title").value;
                    const num = document.getElementById("num-recommendations").value;
                    chatRecommend.push({
                    sender: "user",
                    text: `${title} (${num} recommendations)`,
                    });
                    renderChat("chat-recommend", chatRecommend);
                    const res = await fetch("/recommend_movie", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        movie_title: title,
                        num_recommendations: parseInt(num),
                    }),
                    });
                    const data = await res.json();
                    chatRecommend.push({
                    sender: "ai",
                    text: data.recommended_movies
                        ? data.recommended_movies.join(", ")
                        : data.detail || "Error",
                    });
                    renderChat("chat-recommend", chatRecommend);
                }
                </script>
            </body>
        </html>
    """

# --- Main entry point for Uvicorn ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

