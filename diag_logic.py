import ai_client
import tts_generator
import inspect

print("--- AI Client Audit ---")
# Try to find the min_words value in validate_broadcast
source = inspect.getsource(ai_client.validate_broadcast)
print(f"validate_broadcast min_words check:\n{source}")

print("\n--- TTS Generator Audit ---")
source_guard = inspect.getsource(tts_generator._is_audio_valid)
print(f"_is_audio_valid source:\n{source_guard}")

print("\n--- Model Queues ---")
print(f"MODEL_SET_A: {ai_client.MODEL_SET_A}")
print(f"MODEL_SET_B: {ai_client.MODEL_SET_B}")
