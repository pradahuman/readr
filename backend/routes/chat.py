from flask import Blueprint, request, jsonify, abort
import logging
import traceback

# Langchain Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory # For type hint or potential re-init

# Assuming these are accessible from the main app context or a shared module.
# Import shared state from app_state.py
from app_state import vector_stores, chat_histories

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat_bp', __name__)

@chat_bp.route("/chat", methods=['POST'])
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
        logger.error(f"Chat history missing for processed PDF: {pdf_id}. Chat may not work correctly.")
        # Potentially abort or try re-initializing memory - for now, log error and proceed
        # chat_histories[pdf_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        # abort(404, description=f"Chat history for PDF '{pdf_id}' is missing.")
        # For robustness, let's retrieve memory or use a default if missing
        chat_history = chat_histories.get(pdf_id, ConversationBufferMemory(memory_key="chat_history", return_messages=True))
    else:
        chat_history = chat_histories[pdf_id]

    # --- Prepare Langchain Components ---
    try:
        vector_store = vector_stores[pdf_id]

        # TODO: Ensure LLM is initialized properly (e.g., in main app or shared config)
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro-exp-03-25", temperature=0.3, convert_system_message_to_human=True)

        # Create the Conversational Retrieval Chain
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vector_store.as_retriever(),
            memory=chat_history,
            return_source_documents=False
        )

        # --- Get AI Response ---
        logger.info(f"Running query against ConversationalRetrievalChain for {pdf_id}...")
        result = qa_chain({"question": user_query})
        ai_response = result.get('answer', "Sorry, I could not generate a response.") # Use .get for safety
        logger.info(f"Received AI response for {pdf_id}: '{ai_response[:100]}...'")

        return jsonify({"pdf_id": pdf_id, "query": user_query, "answer": ai_response})

    except Exception as e:
        # Log the exception type and the full traceback for better debugging
        logger.error(f"Error type: {type(e).__name__} during chat processing for PDF {pdf_id}: {e}")
        logger.error(traceback.format_exc())
        # Return a JSON error response instead of letting Flask return HTML
        return jsonify({
            "error": "An internal error occurred while processing the chat request.",
            "details": str(e) # Optionally include limited error details
            }), 500
