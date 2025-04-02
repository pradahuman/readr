from flask import Blueprint, request, jsonify, abort
import io
import logging
import traceback
from PyPDF2 import PdfReader

# Langchain Imports (assuming shared setup or re-initialization if needed)
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory

# Import shared state from app_state.py
from app_state import pdf_storage, pdf_text_cache, vector_stores, chat_histories

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload_bp', __name__)

@upload_bp.route("/upload", methods=['POST'])
def upload_pdf():
    """
    Handles PDF file uploads.
    Temporarily stores the file, extracts text using PyPDF2, and caches it.
    Initiates Langchain processing for vector store and chat history.
    """
    if 'file' not in request.files:
        abort(400, description="No file part in the request")
    file = request.files['file']
    if file.filename == '':
        abort(400, description="No selected file")

    if file and file.content_type == "application/pdf":
        pdf_id = file.filename  # Using filename as ID (not robust)
        try:
            content = file.read()
            pdf_storage[pdf_id] = content
            logger.info(f"Received PDF: {pdf_id}, size: {len(content)} bytes")

            # --- PDF Parsing Logic ---
            extracted_text = ""
            num_pages = 0
            try:
                pdf_stream = io.BytesIO(content)
                reader = PdfReader(pdf_stream)
                num_pages = len(reader.pages)
                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    extracted_text += page.extract_text() or "" # Add empty string if extraction fails
                pdf_text_cache[pdf_id] = extracted_text
                logger.info(f"Extracted {len(extracted_text)} characters from {num_pages} pages for PDF: {pdf_id}")
            except Exception as pdf_err:
                logger.error(f"Error processing PDF {pdf_id} with PyPDF2: {pdf_err}")
                logger.error(traceback.format_exc())
                abort(500, description=f"Could not process PDF file: {pdf_err}")


            # --- Langchain Processing ---
            try:
                logger.info(f"Starting Langchain processing for {pdf_id}...")
                # 1. Split text
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, chunk_overlap=200, length_function=len
                )
                documents = text_splitter.split_text(text=extracted_text)
                logger.info(f"Split text into {len(documents)} documents.")

                # 2. Embeddings and Vector Store
                # TODO: Ensure embeddings are initialized properly (e.g., in main app or shared config)
                embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
                vector_store = FAISS.from_texts(documents, embedding=embeddings)
                vector_stores[pdf_id] = vector_store
                logger.info(f"Created and stored FAISS vector store for {pdf_id}.")

                # 3. Initialize Chat History
                chat_histories[pdf_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
                logger.info(f"Initialized chat history for {pdf_id}.")

            except Exception as e:
                logger.error(f"Langchain processing failed for {pdf_id}: {e}")
                logger.error(traceback.format_exc())
                # Clean up potentially partially stored data if processing fails
                pdf_storage.pop(pdf_id, None)
                pdf_text_cache.pop(pdf_id, None)
                vector_stores.pop(pdf_id, None)
                chat_histories.pop(pdf_id, None)
                abort(500, description=f"Failed to process PDF for Langchain integration: {e}")

            logger.info(f"Successfully processed and stored PDF for chat: {pdf_id}")
            return jsonify({
                "message": "PDF uploaded and processed successfully.",
                "pdf_id": pdf_id,
                "num_pages": num_pages,
                "char_count": len(extracted_text),
                # Indicate if AI features are likely ready (basic check)
                "ai_features_enabled": pdf_id in vector_stores and pdf_id in chat_histories
                }), 200

        except Exception as e:
             logger.error(f"Unexpected error during upload for {pdf_id}: {e}")
             logger.error(traceback.format_exc())
             # Clean up potentially partially processed data
             pdf_storage.pop(pdf_id, None)
             pdf_text_cache.pop(pdf_id, None)
             vector_stores.pop(pdf_id, None)
             chat_histories.pop(pdf_id, None)
             abort(500, description=f"An unexpected server error occurred during upload: {e}")

    else:
        abort(400, description="Invalid file type or file not provided. Please upload a PDF.")
