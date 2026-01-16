print("Starting component verification...")

# 1. Check torch and CUDA
try:
    import torch

    print(f"[PASS] torch imported. Version: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"[PASS] CUDA is available. Device: {torch.cuda.get_device_name(0)}")
    else:
        print("[WARNING] CUDA is NOT available.")
except ImportError as e:
    print(f"[FAIL] torch import failed: {e}")

# 2. Check transformers
try:
    import transformers

    print(f"[PASS] transformers imported. Version: {transformers.__version__}")
except ImportError as e:
    print(f"[FAIL] transformers import failed: {e}")

# 3. Check accelerate
try:
    import accelerate

    print(f"[PASS] accelerate imported. Version: {accelerate.__version__}")
except ImportError as e:
    print(f"[FAIL] accelerate import failed: {e}")

# 4. Check sentence_transformers
try:
    import sentence_transformers
    from sentence_transformers import SentenceTransformer

    print(f"[PASS] sentence_transformers imported. Version: {sentence_transformers.__version__}")
except ImportError as e:
    print(f"[FAIL] sentence_transformers import failed: {e}")

# 5. Check langchain_community
try:
    import langchain_community
    from langchain_community.llms import HuggingFacePipeline

    print(f"[PASS] langchain_community imported. Version: {langchain_community.__version__}")
except ImportError as e:
    print(f"[FAIL] langchain_community import failed: {e}")

# 6. Check huggingface_hub
try:
    import huggingface_hub

    print(f"[PASS] huggingface_hub imported. Version: {huggingface_hub.__version__}")
except ImportError as e:
    print(f"[FAIL] huggingface_hub import failed: {e}")

print("Verification complete.")
