import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
import joblib
import os

os.makedirs(".", exist_ok=True)

df = pd.read_csv("../MileStone1/banking_chatbot_dataset_large.csv")
df = df.dropna(subset=['query','intent'])
X = df['query'].astype(str)
y = df['intent'].astype(str)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)

vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1,2))
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

model = LogisticRegression(max_iter=2000, C=1.0)
model.fit(X_train_vec, y_train)

preds = model.predict(X_test_vec)
print(classification_report(y_test, preds, zero_division=0))

joblib.dump(model, "intent_model.pkl")
joblib.dump(vectorizer, "vectorizer.pkl")
print("Saved intent_model.pkl and vectorizer.pkl")
