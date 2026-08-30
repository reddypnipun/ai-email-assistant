import joblib
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import LabelEncoder 
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.naive_bayes import MultinomialNB

print("1. Loading dataset from Kaggle CSV...")
df = pd.read_csv('email.csv')

# Drop any rows where Message or Category are completely missing
df.dropna(subset=['Message', 'Category'], inplace=True)

# Delete the rows containing the broken metadata text
df = df[df['Category'] != '{"mode":"full"']

# Split columns after cleaning the DataFrame
emails = df['Message']
labels = df['Category']

# Encode the clean labels
lb = LabelEncoder()
y = lb.fit_transform(labels)

print(f"Loaded {len(emails)} emails. Preparing data...")

# Vectorize and split
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(emails)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("2. Training the Machine Learning Model...")
classifier = MultinomialNB()
classifier.fit(X_train, y_train)

pred = classifier.predict(X_test)
print(f"Accuracy: {accuracy_score(y_test, pred)}")
print(f"Confusion matrix:\n{confusion_matrix(y_test, pred)}")
print(f"Precision: {precision_score(y_test, pred)}")
print(f"Recall: {recall_score(y_test, pred)}")
print(f"F1 Score: {f1_score(y_test, pred)}") 

print("3. Saving the model...")
joblib.dump(classifier, 'spam_model.pkl')
joblib.dump(vectorizer, 'vectorizer.pkl')

print("SUCCESS! Model trained on real Kaggle data and saved.")
