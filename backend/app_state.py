# Shared state for the application
# Import necessary types if you want stricter typing
from langchain_community.vectorstores.faiss import FAISS as VectorStore # Assuming FAISS is the only type used
from langchain.memory import ConversationBufferMemory

pdf_storage: dict[str, bytes] = {}
pdf_text_cache: dict[str, str] = {}
vector_stores: dict[str, VectorStore] = {}
chat_histories: dict[str, ConversationBufferMemory] = {}
