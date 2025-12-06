import os
import sys
import joblib
import numpy as np

MODEL_PATH = "model/models/model_random_forest.pkl"

def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    return joblib.load(MODEL_PATH)

def predict(temp, hum):
    """
    Prediksi label berdasarkan suhu dan kelembaban
    
    Args:
        temp: Suhu dalam Celsius
        hum: Kelembaban dalam persen
    
    Returns:
        str: Label prediksi ('Panas', 'Normal', atau 'Dingin')
    """
    model = load_model()
    X = np.array([[temp, hum]])
    prediction = model.predict(X)[0]
    return prediction

def main():
    # Load model
    print("Loading model from:", MODEL_PATH)
    model = load_model()
    print("✓ Model loaded successfully\n")
    
    # Interactive mode atau command line args
    if len(sys.argv) == 3:
        # Mode: python predict.py <temp> <hum>
        try:
            temp = float(sys.argv[1])
            hum = float(sys.argv[2])
            result = predict(temp, hum)
            print(f"Input: temp={temp}°C, hum={hum}%")
            print(f"Prediction: {result}")
        except ValueError:
            print("Error: Temperature and humidity must be numbers")
            sys.exit(1)
    else:
        # Interactive mode
        print("=== Smart Comfort Prediction ===")
        print("Enter temperature and humidity to predict comfort level")
        print("Type 'quit' to exit\n")
        
        while True:
            try:
                temp_input = input("Temperature (°C): ")
                if temp_input.lower() == 'quit':
                    break
                    
                hum_input = input("Humidity (%): ")
                if hum_input.lower() == 'quit':
                    break
                
                temp = float(temp_input)
                hum = float(hum_input)
                
                result = predict(temp, hum)
                print(f"→ Prediction: {result}")
                print("-" * 40)
                
            except ValueError:
                print("Error: Please enter valid numbers\n")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break

if __name__ == "__main__":
    main()
