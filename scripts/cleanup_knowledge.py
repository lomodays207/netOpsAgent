
import sys
import os

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), "src"))

from rag.vector_store import get_vector_store
from rag.document_processor import DocumentProcessor

def cleanup():
    print("Initializing...")
    vector_store = get_vector_store()
    doc_processor = DocumentProcessor()
    
    # List docs
    docs = vector_store.list_documents()
    print(f"Found {len(docs)} documents.")
    
    target_filename = "test_knowledge.txt"
    
    for doc in docs:
        if doc['filename'] == target_filename:
            print(f"Deleting {doc['filename']} (ID: {doc['doc_id']})...")
            # Delete from vector store
            vector_store.delete_by_doc_id(doc['doc_id'])
            # Delete file
            doc_processor.delete_file(doc['doc_id'])

    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup()
