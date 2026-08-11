import joblib
import os

class HybridSpamFlagger:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        vec_path = os.path.join(base_dir, 'vectorizer.pkl') 
        model_path = os.path.join(base_dir, 'spam_model.pkl')

        try:
            self.vectorizer = joblib.load(vec_path)
            self.classifier = joblib.load(model_path)
            self.ml_ready = True
            print("✅ ML Models loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading ML Models: {e}")
            self.ml_ready = False

    def analyze(self, text: str, sender: str) -> dict:
        if not self.ml_ready:
            return {"is_spam": False, "reason": "ML Model unavailable - check file paths"}

        text_vector = self.vectorizer.transform([text])
        
        prediction = self.classifier.predict(text_vector)
        
        if prediction[0] == 1:
            return {"is_spam": True, "reason": "Machine Learning Flag"}
        
        return {"is_spam": False, "reason": "Clean Email"}