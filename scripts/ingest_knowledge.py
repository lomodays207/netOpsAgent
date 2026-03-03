
import os
import sys
import glob

# Add src to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from rag.document_processor import DocumentProcessor
from rag.vector_store import get_vector_store

def ingest_knowledge():
    print("Initializing RAG components...")
    doc_processor = DocumentProcessor()
    vector_store = get_vector_store()
    
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "knowledge")
    
    if not os.path.exists(knowledge_dir):
        print(f"Knowledge directory not found: {knowledge_dir}")
        return

    txt_files = glob.glob(os.path.join(knowledge_dir, "*.txt"))
    
    if not txt_files:
        print(f"No TXT files found in {knowledge_dir}")
        return
        
    print(f"Found {len(txt_files)} documents to ingest.")
    
    for file_path in txt_files:
        filename = os.path.basename(file_path)
        print(f"Processing {filename}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc_id, chunks, metadatas = doc_processor.process_text_file(
                file_content=content.encode('utf-8'), # process_text_file expects bytes
                filename=filename
            )
            
            # Check if document already exists (simple check by doc_id prefix in persistence might be complex without ID tracking, 
            # here we just add, duplicates might happen if not managed. 
            # ideally we should check or clear. For this script, we'll just add.)
            
            vector_store.add_documents(
                texts=chunks,
                metadatas=metadatas,
                doc_id=doc_id
            )
            print(f"Successfully ingested {len(chunks)} chunks from {filename}")
            
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print("\nIngestion complete.")
    print(f"Total chunks in vector store: {vector_store.collection.count()}")

if __name__ == "__main__":
    ingest_knowledge()
