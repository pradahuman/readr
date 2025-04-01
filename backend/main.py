from flask import Flask, request, jsonify, abort, Response
from flask_cors import CORS
import os
import io
import logging # For better logging
import traceback # For detailed error logging
from PyPDF2 import PdfReader


# Langchain Imports
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Enable CORS for the entire app (adjust origins for production)

# In-memory storage (temporary, replace with proper storage later)
pdf_storage = {}
pdf_text_cache = {} # Keep raw text cache for potential non-AI uses
vector_stores = {} # Store FAISS vector stores (or retrievers)
chat_histories = {} # Store conversation histories

# --- Environment Variable Check --- 
# Ensure Google API Key is set
if not os.environ.get("GOOGLE_API_KEY"):
    logger.warning("GOOGLE_API_KEY environment variable not set. Chat functionality will likely fail.")

@app.route("/upload", methods=['POST'])
def upload_pdf():
    """
    Handles PDF file uploads.
    Temporarily stores the file, extracts text using PyPDF2, and caches it.
    """
    if 'file' not in request.files:
        abort(400, description="No file part in the request")
    file = request.files['file']
    if file.filename == '':
        abort(400, description="No selected file")

    if file and file.content_type == "application/pdf":
        # Simple temporary storage using a dictionary (replace later)
        pdf_id = file.filename  # Using filename as ID for now (not robust)
        content = file.read()
        pdf_storage[pdf_id] = content

        # --- PDF Parsing Logic --- 
        try:
            pdf_stream = io.BytesIO(content)
            reader = PdfReader(pdf_stream)
            num_pages = len(reader.pages)
            extracted_text = ""
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                extracted_text += page.extract_text() or "" # Add empty string if extraction fails

            pdf_text_cache[pdf_id] = extracted_text
            logger.info(f"Extracted {len(extracted_text)} characters from {num_pages} pages for PDF: {pdf_id}")

            # --- Langchain Processing --- 
            try:
                logger.info(f"Starting Langchain processing for {pdf_id}...")
                # 1. Split text into chunks
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, 
                    chunk_overlap=200, 
                    length_function=len
                )
                documents = text_splitter.split_text(text=extracted_text)
                logger.info(f"Split text into {len(documents)} documents.")

                # 2. Create embeddings and vector store
                # Use Google's embedding model
                embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001") 
                
                # Create FAISS vector store from documents and embeddings
                vector_store = FAISS.from_texts(documents, embedding=embeddings)
                vector_stores[pdf_id] = vector_store # Store the whole store for now
                logger.info(f"Created and stored FAISS vector store for {pdf_id}.")

                # 3. Initialize chat history for this PDF
                chat_histories[pdf_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
                logger.info(f"Initialized chat history for {pdf_id}.")

            except Exception as e:
                logger.error(f"Langchain processing failed for {pdf_id}: {e}")
                logger.error(traceback.format_exc()) # Log detailed traceback
                # Decide how to handle: maybe upload succeeds but chat is disabled?
                # For now, let upload succeed but log the error.
                # We could optionally remove the pdf_id from vector_stores if needed.
                pass # Allow upload to complete even if embedding fails

        except Exception as e:
            # Handle potential PyPDF2 errors
            logger.error(f"Error processing PDF {pdf_id} with PyPDF2: {e}")
            logger.error(traceback.format_exc()) # Log detailed traceback
            abort(500, description=f"Could not process PDF file: {e}")

        # Log success and return PDF ID
        logger.info(f"Successfully uploaded and processed PDF: {pdf_id}, size: {len(content)} bytes")
        return jsonify({"message": "PDF uploaded and processed successfully", "pdf_id": pdf_id}), 200
    else:
        abort(400, description="Invalid file type or file not provided. Please upload a PDF.")

@app.route("/pdf/<string:pdf_id>/page/<int:page_num>", methods=['GET'])
def get_pdf_page(pdf_id: str, page_num: int):
    """
    Retrieves a specific page of a PDF.
    (Implementation pending - might return rendered image or text layer)
    """
    if pdf_id not in pdf_storage:
        abort(404, description="PDF not found")

    # TODO: Implement page retrieval/rendering logic
    print(f"Request for page {page_num} of PDF: {pdf_id}") # Basic logging
    return jsonify({"pdf_id": pdf_id, "page_num": page_num, "content": f"Content for page {page_num} (placeholder)"})

@app.route("/pdf/<string:pdf_id>/raw", methods=['GET'])
def get_raw_pdf(pdf_id: str):
    """Serves the raw PDF content stored in memory."""
    if pdf_id not in pdf_storage:
        abort(404, description="PDF not found")

    pdf_content = pdf_storage[pdf_id]
    return Response(pdf_content, mimetype='application/pdf')

@app.route("/pdf/<string:pdf_id>/search", methods=['GET'])
def search_pdf(pdf_id: str):
    """
    Searches for text within the PDF.
    (Requires text extraction implemented in /upload)
    """
    query = request.args.get('query')
    if pdf_id not in pdf_storage:
        abort(404, description="PDF not found")
    if not query:
        abort(400, description="Search query parameter 'query' is required.")

    # TODO: Implement search logic using pdf_text_cache
    print(f"Search query '{query}' in PDF: {pdf_id}") # Basic logging
    return jsonify({"pdf_id": pdf_id, "query": query, "results": f"Search results for '{query}' (placeholder)"})

@app.route("/chat", methods=['POST'])
def chat_with_pdf():
    """
    Handles chat messages for a specific PDF.
    Retrieves context using the vector store and generates a response using Gemini.
    """
    data = request.get_json()
    if not data or 'pdf_id' not in data or 'query' not in data:
        abort(400, description="Missing 'pdf_id' or 'query' in request body")

    pdf_id = data['pdf_id']
    user_query = data['query']

    logger.info(f"Received chat query for PDF '{pdf_id}': '{user_query}'")

    # --- Validate Inputs --- 
    if pdf_id not in vector_stores:
        logger.warning(f"Chat request for unknown or unprocessed PDF: {pdf_id}")
        abort(404, description=f"PDF '{pdf_id}' not found or not processed for chat.")
    if pdf_id not in chat_histories:
        # Should not happen if upload succeeded, but good practice to check
        logger.error(f"Chat history missing for processed PDF: {pdf_id}. Re-initializing.")
        chat_histories[pdf_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    # --- Prepare Langchain Components --- 
    try:
        vector_store = vector_stores[pdf_id]
        chat_history = chat_histories[pdf_id]

        # Initialize the Google Chat Model (ensure GOOGLE_API_KEY is set)
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro-exp-03-25", temperature=0.3, convert_system_message_to_human=True)

        # Create the Conversational Retrieval Chain
        # This chain combines the LLM, the retriever (from the vector store), and memory
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vector_store.as_retriever(),
            memory=chat_history,
            return_source_documents=False # Set to True if you want to see source chunks
        )

        # --- Get AI Response --- 
        logger.info(f"Running query against ConversationalRetrievalChain for {pdf_id}...")
        result = qa_chain({"question": user_query})
        ai_response = result['answer']
        logger.info(f"Received AI response for {pdf_id}: '{ai_response[:100]}...'") # Log first 100 chars

        return jsonify({"pdf_id": pdf_id, "query": user_query, "answer": ai_response})

    except Exception as e:
        logger.error(f"Error during chat processing for PDF {pdf_id}: {e}")
        logger.error(traceback.format_exc()) # Log detailed traceback
        abort(500, description="An error occurred while processing the chat request.")

@app.route("/")
def home():
    return "Welcome to the PDF Chat App!"

if __name__ == "__main__":
    # Use port 8000 to match the previous setup, enable debug mode
    app.run(host="0.0.0.0", port=8000, debug=True)
