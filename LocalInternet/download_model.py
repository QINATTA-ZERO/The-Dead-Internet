from fastembed import TextEmbedding
import os

# Get absolute path to the data/nexus_cache directory
current_dir = os.path.dirname(os.path.abspath(__file__))
cache_path = os.path.join(current_dir, "data", "nexus_cache")
os.makedirs(cache_path, exist_ok=True)

# Set cache dir for fastembed
os.environ["FASTEMBED_CACHE_PATH"] = cache_path

print(f"Downloading model to {cache_path}...")
# This will download the model into the specified directory
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
print("Download complete.")