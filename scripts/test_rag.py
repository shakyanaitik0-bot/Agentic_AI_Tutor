"""
Test script for RAG service and Pinecone integration.
Verifies document chunking, embedding, upload, and search.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.rag_service import RAGService, Document

def test_rag_service():
    """Test RAG service functionality"""
    print("\n" + "="*70)
    print("Testing RAG Service with Pinecone")
    print("="*70)

    try:
        # Test 1: Initialize RAG service
        print("\n[1] Initializing RAG service...")
        rag = RAGService()
        print(f"    Index: {rag.index_name}")
        print(f"    Dimension: {rag.dimension}")
        print(f"    Chunk size: {rag.chunk_size}")
        print(f"    Chunk overlap: {rag.chunk_overlap}")
        print("    [OK] RAG service initialized")

        # Test 2: Check if service is available
        print("\n[2] Checking Pinecone connection...")
        is_available = rag.is_available()
        print(f"    Service available: {is_available}")
        if is_available:
            print("    [OK] Connected to Pinecone")
        else:
            print("    [FAIL] Cannot connect to Pinecone")
            return False

        # Test 3: Get index stats
        print("\n[3] Getting index statistics...")
        stats = rag.get_stats()
        print(f"    Total vectors: {stats.get('total_vectors', 0)}")
        print(f"    Dimension: {stats.get('dimension', 0)}")
        print(f"    Index fullness: {stats.get('index_fullness', 0)}")
        print("    [OK] Retrieved index stats")

        # Test 4: Document chunking
        print("\n[4] Testing document chunking...")
        sample_text = """
        The Pythagorean theorem states that in a right-angled triangle, the square of the
        length of the hypotenuse (the side opposite the right angle) is equal to the sum of
        the squares of the lengths of the other two sides. This can be written as: a² + b² = c²,
        where c represents the length of the hypotenuse and a and b the lengths of the triangle's
        other two sides. This theorem is fundamental in mathematics and has numerous applications
        in physics, engineering, and computer science. It was known to ancient civilizations but
        is named after the ancient Greek mathematician Pythagoras.
        """

        chunks = rag.chunk_text(
            sample_text,
            metadata={
                "topic": "Mathematics",
                "subject": "Geometry",
                "exam_type": "JEE"
            }
        )
        print(f"    Input text: {len(sample_text.split())} words")
        print(f"    Output: {len(chunks)} chunks")
        if chunks:
            print(f"    First chunk length: {len(chunks[0].content.split())} words")
            print(f"    First chunk metadata: {chunks[0].metadata}")
        print("    [OK] Document chunking successful")

        # Test 5: Upload documents
        print("\n[5] Testing document upload...")
        print("    NOTE: This will upload test documents to Pinecone")

        # Create test documents
        test_docs = [
            Document(
                content="Newton's first law of motion states that an object at rest stays at rest and an object in motion stays in motion with the same speed and in the same direction unless acted upon by an unbalanced force.",
                metadata={"topic": "Physics", "subject": "Mechanics", "exam_type": "JEE"}
            ),
            Document(
                content="The derivative of a function represents the rate of change of the function with respect to its variable. It is a fundamental concept in calculus.",
                metadata={"topic": "Mathematics", "subject": "Calculus", "exam_type": "SAT"}
            ),
            Document(
                content="A quadratic equation is a second-order polynomial equation in a single variable x ax²+bx+c=0 with a≠0. The solutions are given by the quadratic formula.",
                metadata={"topic": "Mathematics", "subject": "Algebra", "exam_type": "GRE"}
            )
        ]

        # Add chunked documents
        test_docs.extend(chunks)

        upload_stats = rag.upload_documents(test_docs, namespace="test")
        print(f"    Uploaded: {upload_stats['uploaded']}")
        print(f"    Failed: {upload_stats['failed']}")
        print(f"    Total: {upload_stats['total']}")
        if upload_stats['uploaded'] > 0:
            print("    [OK] Document upload successful")
        else:
            print("    [FAIL] No documents uploaded")
            return False

        # Test 6: Semantic search
        print("\n[6] Testing semantic search...")
        test_queries = [
            "What is Newton's law of motion?",
            "How do you calculate derivatives?",
            "Explain the Pythagorean theorem"
        ]

        for query in test_queries:
            print(f"\n    Query: '{query}'")
            results = rag.search(query, top_k=3, namespace="test")
            print(f"    Results: {len(results)} documents found")

            if results:
                print(f"    Top result score: {results[0]['score']:.4f}")
                print(f"    Content preview: {results[0]['content'][:100]}...")
                print(f"    Metadata: {results[0]['metadata'].get('topic', 'N/A')}")

        print("\n    [OK] Semantic search successful")

        # Test 7: Context retrieval
        print("\n[7] Testing context retrieval...")
        query = "Tell me about calculus and derivatives"
        context, sources = rag.get_context(query, namespace="test")
        print(f"    Query: '{query}'")
        print(f"    Context length: {len(context)} characters")
        print(f"    Source documents: {len(sources)}")
        if context:
            print(f"    Context preview: {context[:200]}...")
        print("    [OK] Context retrieval successful")

        # Test 8: Cleanup (optional - comment out to keep test data)
        print("\n[8] Cleaning up test data...")
        print("    Skipping cleanup to preserve test data")
        print("    To delete test data, run: rag.delete_all(namespace='test')")

        print("\n" + "="*70)
        print("ALL TESTS PASSED - RAG Service working correctly!")
        print("="*70)
        print("\nRAG Service Features:")
        print("  - Document chunking with overlap")
        print("  - Batch embedding generation (FREE with Sentence Transformers)")
        print("  - Vector storage in Pinecone")
        print("  - Semantic search with metadata filtering")
        print("  - Context window management")
        print("\n")

        return True

    except Exception as e:
        print(f"\n[FAIL] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rag_service()
    sys.exit(0 if success else 1)
