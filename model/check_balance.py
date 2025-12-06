import pandas as pd

# Load data
df = pd.read_csv('model/dataset/preprocessed_data.csv')

# Display stats
print(f"📊 Total: {len(df):,} rows\n")
print("=" * 50)
print("Distribution:")
print("=" * 50)

counts = df['label'].value_counts()
for label in counts.index:
    count = counts[label]
    pct = (count / len(df)) * 100
    bar = '█' * int(pct / 2)
    print(f"{label:10s}: {count:6,} ({pct:5.1f}%) {bar}")

print("\n" + "=" * 50)

# Check balance
max_count = counts.max()
min_count = counts.min()
ratio = max_count / min_count

print(f"\nBalance Ratio: {ratio:.2f}x")
if ratio <= 1.5:
    print("✅ BALANCED - Class distribution is good!")
elif ratio <= 3:
    print("⚠️  SLIGHTLY IMBALANCED - Consider balancing")
else:
    print("❌ HIGHLY IMBALANCED - Need balancing!")
