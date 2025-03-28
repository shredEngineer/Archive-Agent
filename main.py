import sys
import os
import json
import hashlib
import openai
from pathlib import Path
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from qdrant_client.http.exceptions import UnexpectedResponse

# === Config ===
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = "text-embedding-3-small"
COLLECTION_NAME = "archiveagent-md"
QDRANT_URL = "http://localhost:6333"
SNAPSHOT_PATH = "snapshot.json"

# === Init & Check Qdrant Connection Early ===
try:
	print(f"[🔌] Connecting to Qdrant at {QDRANT_URL}...")
	client = QdrantClient(url=QDRANT_URL)
	client.get_collections()
	print("[✓] Qdrant is up and reachable.")
except Exception as e:
	print(f"[!] Could not connect to Qdrant at {QDRANT_URL}: {e}")
	print("[💡] Tip: Run it via Docker → sudo docker run -p 6333:6333 qdrant/qdrant")
	sys.exit(1)

# === Qdrant Setup ===
def ensure_collection():
	try:
		if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
			print("[+] Creating Qdrant collection...")
			client.create_collection(
				collection_name=COLLECTION_NAME,
				vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
			)
	except UnexpectedResponse as e:
		print(f"[!] Failed to ensure collection: {e}")
		sys.exit(1)

# === Snapshot Handling ===
def load_snapshot():
	if not os.path.exists(SNAPSHOT_PATH):
		return {}
	with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
		return json.load(f)

def save_snapshot(snapshot):
	with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
		json.dump(snapshot, f, indent=2)

def compute_file_hash(path):
	with open(path, "rb") as f:
		return hashlib.sha256(f.read()).hexdigest()

def file_metadata(path):
	p = Path(path)
	stat = p.stat()
	return {
		"filename": p.name,
		"path": str(p.resolve()),
		"mtime": stat.st_mtime,
		"size": stat.st_size,
		"hash": compute_file_hash(p),
	}

def has_changed(meta, old_meta):
	return not old_meta or meta["hash"] != old_meta.get("hash")

# === Core Functions ===
def load_file_text(path):
	with open(path, "r", encoding="utf-8") as f:
		return f.read()

def embed_text(text):
	response = openai.embeddings.create(
		input=text,
		model=MODEL
	)
	return response.data[0].embedding

def compute_id(text):
	return int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)

def store_embedding(embedding, metadata):
	point = PointStruct(
		id=compute_id(metadata['content']),
		vector=embedding,
		payload=metadata
	)
	client.upsert(collection_name=COLLECTION_NAME, points=[point])

# === Main ===
def main(file_path):
	print(f"\n[+] Checking file: {file_path}")

	snapshot = load_snapshot()
	meta = file_metadata(file_path)
	old_meta = snapshot.get(meta["path"])

	if not has_changed(meta, old_meta):
		print("[✓] No change detected. Skipping embedding.")
		return

	print("[+] Change detected. Embedding and storing...")
	text = load_file_text(file_path)

	ensure_collection()
	embedding = embed_text(text)

	metadata = meta.copy()
	metadata["content"] = text
	store_embedding(embedding, metadata)

	snapshot[meta["path"]] = meta
	save_snapshot(snapshot)

	print(f"[✓] Done. Vector stored. ID: {compute_id(text)}")
	print(f"[🧠] Embedding preview: {embedding[:8]} ... (dim {len(embedding)})")

if __name__ == "__main__":
	if len(sys.argv) != 2:
		print("Usage: python main.py <path-to-md-file>")
		print("💡 You can try:")
		print("   python main.py Example.md")
		sys.exit(1)

	try:
		main(sys.argv[1])
	except Exception as e:
		print(f"[!] Error: {e}")
		sys.exit(1)
