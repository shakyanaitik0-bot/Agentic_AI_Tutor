"""
Test script for Sentence Transformers embedding service.
Verifies free local embeddings are working correctly.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.embedding_service import EmbeddingService

def test_sentence_transformers():
    """Test Sentence Transformers embedding service"""
    print("\n" + "="*70)
    print("Testing Sentence Transformers Embedding Service")
    print("="*70)

    try:
        # Initialize embedding service (will use sentence-transformers from config)
        print("\n[1] Initializing embedding service...")
        embedder = EmbeddingService()
        print(f"    Provider: {embedder.provider}")
        print(f"    Model: {embedder.model}")
        print(f"    Dimension: {embedder.get_embedding_dimension()}")
        print("    [OK] Service initialized")

        # Get service info
        print("\n[2] Service information:")
        info = embedder.get_service_info()
        for key, value in info.items():
            print(f"    {key}: {value}")

        # Test single embedding
        print("\n[3] Testing single text embedding...")
        test_text = "What is the Pythagorean theorem?"
        embedding = embedder.embed_text(test_text)
        print(f"    Input: '{test_text}'")
        print(f"    Embedding dimension: {len(embedding)}")
        print(f"    First 5 values: {embedding[:5]}")
        print("    [OK] Single embedding generated")

        # Test batch embedding
        print("\n[4] Testing batch embedding...")
        test_texts = [
            "What is Newton's first law of motion?",
            "Explain the concept of derivatives in calculus",
            "What are the properties of quadratic equations?"
        ]
        embeddings = embedder.embed_batch(test_texts)
        print(f"    Input: {len(test_texts)} texts")
        print(f"    Output: {len(embeddings)} embeddings")
        print(f"    Each embedding dimension: {len(embeddings[0])}")
        print("    [OK] Batch embedding generated")

        # Test cost estimation
        print("\n[5] Testing cost estimation...")
        cost_info = embedder.estimate_cost(test_texts)
        print(f"    Model: {cost_info['model']}")
        print(f"    Provider: {cost_info['provider']}")
        print(f"    Text count: {cost_info['text_count']}")
        print(f"    Estimated tokens: {cost_info['estimated_tokens']}")
        print(f"    Cost (USD): ${cost_info['cost_usd']}")
        print(f"    Note: {cost_info['note']}")
        print("    [OK] Cost estimation successful")

        # Test availability
        print("\n[6] Testing service availability...")
        is_available = embedder.is_available()
        print(f"    Service available: {is_available}")
        if is_available:
            print("    [OK] Service is ready to use")
        else:
            print("    [FAIL] Service not available")
            return False

        print("\n" + "="*70)
        print("ALL TESTS PASSED - Sentence Transformers working correctly!")
        print("="*70)
        print("\nKey Benefits:")
        print("  - Completely FREE (runs locally, no API calls)")
        print("  - Fast embedding generation")
        print("  - 384-dimensional vectors (compatible with Pinecone)")
        print("  - No rate limits or quotas")
        print("  - Works offline")
        print("\n")

        return True

    except Exception as e:
        print(f"\n[FAIL] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sentence_transformers()
    sys.exit(0 if success else 1)
