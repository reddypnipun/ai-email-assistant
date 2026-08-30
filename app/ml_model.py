import joblib
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "spam_model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")

try:
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    print("✅ ML Model and Vectorizer loaded successfully!")
except Exception as e:
    print(f"⚠️ Failed to load ML model files: {e}")
    model, vectorizer = None, None

def predict_spam(clean_email_text: str) -> bool:
    """Classifies clean email text. Returns True if Spam, False if Not Spam."""
    if not model or not vectorizer or not clean_email_text:
        return False
        
    try:
        text_vector = vectorizer.transform([clean_email_text])
        
        prediction = model.predict(text_vector)
        
        is_spam = bool(prediction[0] == 1 or str(prediction[0]).lower() == 'spam')
        return is_spam
    except Exception as e:
        print(f"ML Model Error: {e}")
        return False 