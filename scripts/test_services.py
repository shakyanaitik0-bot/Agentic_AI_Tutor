#!/usr/bin/env python3
"""
Test script to verify configuration and services are working correctly.

Usage:
    python scripts/test_services.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_config():
    """Test configuration loading"""
    print("\n" + "="*60)
    print("TEST 1: Configuration System")
    print("="*60)

    try:
        from app.core.config import settings

        print(f"[OK] Config loaded successfully")
        print(f"  App Name: {settings.app_name}")
        print(f"  Version: {settings.app_version}")
        print(f"  Environment: {settings.environment}")
        print(f"  Database: {settings.database_url}")
        print(f"  Default LLM: {settings.default_llm_provider}")
        print(f"  Embedding Model: {settings.embedding_model}")
        print(f"  Pinecone Index: {settings.pinecone_index_name}")

        # Test YAML access
        llm_temp = settings.get("llm.temperature")
        print(f"  LLM Temperature: {llm_temp}")

        # Test model retrieval
        openai_model = settings.get_llm_model("openai", "default")
        gemini_model = settings.get_llm_model("gemini", "default")
        print(f"  OpenAI Model: {openai_model}")
        print(f"  Gemini Model: {gemini_model}")

        # Check API key availability
        has_openai = settings.is_llm_available("openai")
        has_gemini = settings.is_llm_available("gemini")
        has_pinecone = bool(settings.pinecone_api_key)

        print(f"\n  API Key Status:")
        print(f"    OpenAI: {'[OK] Available' if has_openai else '[FAIL] Missing'}")
        print(f"    Gemini: {'[OK] Available' if has_gemini else '[FAIL] Missing'}")
        print(f"    Pinecone: {'[OK] Available' if has_pinecone else '[FAIL] Missing'}")

        return True

    except Exception as e:
        print(f"[FAIL] Config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_service():
    """Test LLM service with available providers"""
    print("\n" + "="*60)
    print("TEST 2: LLM Service")
    print("="*60)

    try:
        from app.core.config import settings
        from app.services.llm_service import LLMService

        # Determine which provider to test
        providers_to_test = []
        if settings.is_llm_available("openai"):
            providers_to_test.append("openai")
        if settings.is_llm_available("gemini"):
            providers_to_test.append("gemini")

        if not providers_to_test:
            print("[FAIL] No LLM providers available (missing API keys)")
            print("  Add OPENAI_API_KEY or GEMINI_API_KEY to .env file")
            return False

        for provider in providers_to_test:
            print(f"\nTesting {provider.upper()}...")

            # Create service
            llm = LLMService(provider=provider)
            print(f"  [OK] Service initialized: {llm}")

            # Test basic completion
            messages = [
                {"role": "user", "content": "Say 'Hello' in one word only"}
            ]

            print(f"  Testing completion...")
            response = llm.chat_completion(
                messages=messages,
                max_tokens=10,
                temperature=0.5
            )

            print(f"  [OK] Response received: {response[:50]}...")

            # Test token counting (OpenAI only)
            if provider == "openai":
                token_count = llm.count_tokens("This is a test message")
                print(f"  [OK] Token counting works: {token_count} tokens")

            # Get model info
            info = llm.get_model_info()
            print(f"  [OK] Model info: {info}")

        return True

    except Exception as e:
        print(f"[FAIL] LLM service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_embedding_service():
    """Test embedding service"""
    print("\n" + "="*60)
    print("TEST 3: Embedding Service")
    print("="*60)

    try:
        from app.core.config import settings
        from app.services.embedding_service import EmbeddingService

        if not settings.is_llm_available("openai"):
            print("[FAIL] OpenAI API key not available")
            print("  Add DEFAULT_OPENAI_API_KEY to .env file")
            return False

        # Create service
        embedder = EmbeddingService()
        print(f"[OK] Service initialized: {embedder}")

        # Get service info
        info = embedder.get_service_info()
        print(f"  Model: {info['model']}")
        print(f"  Dimension: {info['dimension']}")
        print(f"  Batch Size: {info['batch_size']}")

        # Test single embedding
        print("\n  Testing single text embedding...")
        text = "This is a test sentence for embedding"
        embedding = embedder.embed_text(text)
        print(f"  [OK] Embedding generated: dimension={len(embedding)}")

        # Test batch embedding
        print("\n  Testing batch embedding...")
        texts = [
            "First test sentence",
            "Second test sentence",
            "Third test sentence"
        ]

        embeddings = embedder.embed_batch(texts)
        print(f"  [OK] Batch embeddings generated: {len(embeddings)} texts")

        # Test cost estimation
        cost_info = embedder.estimate_cost(texts)
        print(f"\n  Cost Estimation:")
        print(f"    Texts: {cost_info['text_count']}")
        print(f"    Estimated Tokens: {cost_info['estimated_tokens']}")
        print(f"    Estimated Cost: ${cost_info['cost_usd']:.6f}")

        return True

    except Exception as e:
        print(f"[FAIL] Embedding service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    """Test database connectivity"""
    print("\n" + "="*60)
    print("TEST 4: Database Connectivity")
    print("="*60)

    try:
        from app.core.database import check_db_connection, get_db_session
        # Import all models to resolve relationships
        from app.models.student import Student
        from app.models.session import Session, Message
        from app.models.progress import Progress

        # Test connection
        if check_db_connection():
            print("[OK] Database connection successful")
        else:
            print("[FAIL] Database connection failed")
            return False

        # Test query
        db = get_db_session()
        try:
            student_count = db.query(Student).count()
            print(f"[OK] Database query successful: {student_count} students found")
            return True
        finally:
            db.close()

    except Exception as e:
        print(f"[FAIL] Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AGENTIC AI TUTOR - SERVICE VERIFICATION")
    print("="*60)

    results = {
        "Configuration": test_config(),
        "Database": test_database(),
        "LLM Service": test_llm_service(),
        "Embedding Service": test_embedding_service()
    }

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, passed in results.items():
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"  {test_name:.<40} {status}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n[OK] All tests passed! Services are ready to use.")
        return 0
    else:
        print("\n[FAIL] Some tests failed. Please check the errors above.")
        print("\nCommon issues:")
        print("  1. Missing API keys in .env file")
        print("  2. Database not initialized (run: python scripts/init_db.py --seed)")
        print("  3. config.yaml not found in project root")
        return 1


if __name__ == "__main__":
    sys.exit(main())