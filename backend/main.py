from flask import Flask, request, jsonify, abort, Response
from flask_cors import CORS
import os
import io
import logging # For better logging
import traceback # For detailed error logging
from PyPDF2 import PdfReader
from dotenv import load_dotenv # Import dotenv

# Load environment variables from .env file at the very start
load_dotenv()

# Langchain Imports (Only those needed globally or for shared state)
# Models might be initialized here and passed or accessed via app context
# from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferMemory
from langchain.vectorstores.base import VectorStore # For type hint
from langchain.chains import ConversationalRetrievalChain # For type hint

# Import shared state
from app_state import pdf_storage, pdf_text_cache, vector_stores, chat_histories

# Import Blueprints
from routes.upload import upload_bp
from routes.chat import chat_bp

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Enable CORS for the entire app (adjust origins for production)

# --- Environment Variable Check --- 
# Ensure Google API Key is set (Now checks after dotenv load)
if not os.getenv("GOOGLE_API_KEY"):
    logger.warning("GOOGLE_API_KEY environment variable not set. Chat functionality will likely fail.")

# --- Register Blueprints ---
app.register_blueprint(upload_bp)
app.register_blueprint(chat_bp)

# --- Remaining Routes (defined directly in main.py) ---

@app.route("/pdf/<string:pdf_id>/page/<int:page_num>", methods=['GET'])
def get_pdf_page(pdf_id: str, page_num: int):
    if pdf_id not in pdf_storage:
        abort(404, description="PDF not found")

    # TODO: Implement page retrieval/rendering logic
    logger.info(f"Request for page {page_num} of PDF: {pdf_id}") # Basic logging
    return jsonify({"pdf_id": pdf_id, "page_num": page_num, "content": f"Content for page {page_num} (placeholder)"})

@app.route("/pdf/<string:pdf_id>/raw", methods=['GET'])
def get_raw_pdf(pdf_id: str):
    if pdf_id not in pdf_storage:
        abort(404, description="PDF not found")

    pdf_content = pdf_storage.get(pdf_id)
    if pdf_content:
        return Response(pdf_content, mimetype='application/pdf')
    else:
        abort(404, description=f"PDF content for ID '{pdf_id}' is missing.") # Robustness check

@app.route("/pdf/<string:pdf_id>/search", methods=['GET']) # Or POST if preferred
def search_pdf(pdf_id: str):
    if pdf_id not in pdf_text_cache:
        abort(404, description=f"Text cache for PDF ID '{pdf_id}' not found. Was it uploaded?")

    query = request.args.get('query') # Use request.args for GET
    # If using POST: data = request.get_json(); query = data.get('query')

    if not query:
        abort(400, description="Search query parameter 'query' is required.")

    full_text = pdf_text_cache.get(pdf_id, "")

    # Basic case-insensitive search (Consider more advanced options)
    occurrences = []
    start_index = 0
    MAX_OCCURRENCES = 100 # Limit results
    while True:
        index = full_text.lower().find(query.lower(), start_index)
        if index == -1:
            break
        # Add context
        context_start = max(0, index - 50)
        context_end = min(len(full_text), index + len(query) + 50)
        context = full_text[context_start:context_end]
        occurrences.append({
            "index": index,
            "context": context.strip()
        })
        start_index = index + 1

        if len(occurrences) >= MAX_OCCURRENCES:
             logger.warning(f"Search for '{query}' in {pdf_id} hit result limit ({MAX_OCCURRENCES}).")
             break

    logger.info(f"Found {len(occurrences)} occurrences of '{query}' in {pdf_id}")
    return jsonify({"pdf_id": pdf_id, "query": query, "occurrences": occurrences})


@app.route("/")
def home():
    """Basic health check or welcome endpoint."""
    return jsonify(message="Readr Backend API is running.")


if __name__ == "__main__":
    # Use port 8000, enable debug mode for development
    app.run(host="0.0.0.0", port=8000, debug=True)
