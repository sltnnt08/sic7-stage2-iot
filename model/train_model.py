import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

DATASET_PATH = "model/dataset/preprocessed_data.csv"
MODEL_DIR = "model/models"

os.makedirs(MODEL_DIR, exist_ok=True)

def load_dataset():
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")
    df = pd.read_csv(DATASET_PATH)
    df = df.dropna(subset=["temp", "hum", "label"])
    return df

def train_models(X_train, y_train):
    models = {
        "decision_tree": DecisionTreeClassifier(),
        "knn": KNeighborsClassifier(n_neighbors=5),
        "random_forest": RandomForestClassifier(n_estimators=100)
    }

    for name, model in models.items():
        model.fit(X_train, y_train)
        joblib.dump(model, f"{MODEL_DIR}/model_{name}.pkl")
        print(f"[+] Saved {name} → model_{name}.pkl")

    return models

def evaluate_models(models, X_test, y_test):
    accuracies = {}

    for name, model in models.items():
        preds = model.predict(X_test)
        acc = accuracy_score(y_test, preds)
        accuracies[name] = acc

        print(f"\n=== {name.upper()} ===")
        print("Accuracy:", acc)
        print(classification_report(y_test, preds))

    return accuracies


def main():
    df = load_dataset()
    X = df[["temp", "hum"]].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    models = train_models(X_train, y_train)
    accuracies = evaluate_models(models, X_test, y_test)

    print("\nTraining completed.")

if __name__ == "__main__":
    main()
