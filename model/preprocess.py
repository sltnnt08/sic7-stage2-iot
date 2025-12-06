import pandas as pd
import glob
import os
from datetime import datetime

# ===============================
# Configuration
# ===============================
INPUT_FOLDER = "model/dataset/"  # Folder containing CSV files
OUTPUT_FILE = "model/dataset/combined_labeled.csv"  # Output file

# Labeling criteria (customize these thresholds)
LABELING_RULES = {
    "Panas": lambda row: row['temp'] >= 28,
    "Hangat": lambda row: row['temp'] >= 25,
    "Dingin": lambda row: row['temp'] < 25,
}

# ===============================
# Functions
# ===============================

def load_and_combine_csv(folder_path, columns=['timestamp', 'temp', 'hum']):
    """
    Load all CSV files from folder and combine them
    
    Args:
        folder_path: Path to folder containing CSV files
        columns: List of columns to keep
    
    Returns:
        Combined DataFrame
    """
    print(f"🔍 Searching for CSV files in: {folder_path}")
    
    # Find all CSV files
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    
    if not csv_files:
        print(f"⚠️ No CSV files found in {folder_path}")
        return None
    
    print(f"📁 Found {len(csv_files)} CSV file(s):")
    for f in csv_files:
        print(f"   - {os.path.basename(f)}")
    
    # Load and combine all CSV files
    dfs = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            print(f"✅ Loaded: {os.path.basename(file)} ({len(df)} rows)")
            dfs.append(df)
        except Exception as e:
            print(f"❌ Error loading {os.path.basename(file)}: {e}")
    
    if not dfs:
        print("❌ No valid CSV files loaded")
        return None
    
    # Combine all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"\n✅ Combined {len(dfs)} file(s) into {len(combined_df)} rows")
    
    # Keep only specified columns (if they exist)
    available_cols = [col for col in columns if col in combined_df.columns]
    if available_cols:
        combined_df = combined_df[available_cols]
        print(f"📋 Kept columns: {', '.join(available_cols)}")
    
    return combined_df


def remove_columns(df, columns_to_remove=['prediction', 'predict', 'status']):
    """
    Remove specified columns from dataframe
    
    Args:
        df: Input DataFrame
        columns_to_remove: List of column names to remove
    
    Returns:
        DataFrame with columns removed
    """
    if df is None:
        return None
    
    cols_removed = []
    for col in columns_to_remove:
        if col in df.columns:
            df = df.drop(columns=[col])
            cols_removed.append(col)
    
    if cols_removed:
        print(f"🗑️ Removed columns: {', '.join(cols_removed)}")
    else:
        print(f"ℹ️ No columns to remove (none found)")
    
    return df


def label_data(df, rules=LABELING_RULES):
    """
    Label data based on criteria
    
    Args:
        df: Input DataFrame with 'temp' and 'hum' columns
        rules: Dictionary of label_name: condition_function
    
    Returns:
        DataFrame with 'label' column added
    """
    if df is None:
        return None
    
    print("\n🏷️ Labeling data based on criteria:")
    
    def assign_label(row):
        # Check each rule in order (except 'Normal' which is default)
        for label, condition in rules.items():
            if label != "Normal" and condition(row):
                return label
        return "Normal"
    
    df['label'] = df.apply(assign_label, axis=1)
    
    # Print label distribution
    label_counts = df['label'].value_counts()
    print("\n📊 Label distribution:")
    for label, count in label_counts.items():
        percentage = (count / len(df)) * 100
        print(f"   {label}: {count} ({percentage:.1f}%)")
    
    return df


def clean_data(df):
    """
    Clean data: remove duplicates, handle missing values, sort by timestamp
    
    Args:
        df: Input DataFrame
    
    Returns:
        Cleaned DataFrame
    """
    if df is None:
        return None
    
    print("\n🧹 Cleaning data...")
    original_rows = len(df)
    
    # Remove duplicates
    df = df.drop_duplicates()
    if len(df) < original_rows:
        print(f"   Removed {original_rows - len(df)} duplicate rows")
    
    # Handle missing values
    missing_before = df.isnull().sum().sum()
    if missing_before > 0:
        print(f"   Found {missing_before} missing values")
        df = df.dropna()
        print(f"   Dropped rows with missing values")
    
    # Sort by timestamp if available
    if 'timestamp' in df.columns:
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            print(f"   Sorted by timestamp")
        except:
            print(f"   ⚠️ Could not parse timestamp column")
    
    # Reset index
    df = df.reset_index(drop=True)
    
    print(f"✅ Cleaned data: {len(df)} rows remaining")
    return df


def save_data(df, output_path):
    """
    Save DataFrame to CSV
    
    Args:
        df: DataFrame to save
        output_path: Path to output file
    """
    if df is None:
        print("❌ No data to save")
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"\n💾 Saved to: {output_path}")
    print(f"   Total rows: {len(df)}")
    print(f"   Columns: {', '.join(df.columns)}")


def display_sample(df, n=5):
    """
    Display sample of data
    
    Args:
        df: DataFrame to display
        n: Number of rows to show
    """
    if df is None:
        return
    
    print(f"\n📋 Sample data (first {n} rows):")
    print(df.head(n).to_string(index=False))


# ===============================
# Main Function
# ===============================

def main():
    """
    Main preprocessing pipeline
    """
    print("=" * 60)
    print("🚀 Data Preprocessing Script")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Load and combine CSV files
    print("STEP 1: Loading and combining CSV files")
    print("-" * 60)
    df = load_and_combine_csv(INPUT_FOLDER, columns=['timestamp', 'temp', 'hum'])
    
    if df is None:
        print("\n❌ Preprocessing failed: No data loaded")
        return
    
    # Step 2: Remove unwanted columns
    print("\n" + "=" * 60)
    print("STEP 2: Removing unwanted columns")
    print("-" * 60)
    df = remove_columns(df, columns_to_remove=['prediction', 'predict', 'status', 'pot'])
    
    # Step 3: Clean data
    print("\n" + "=" * 60)
    print("STEP 3: Cleaning data")
    print("-" * 60)
    df = clean_data(df)
    
    # Step 4: Label data
    print("\n" + "=" * 60)
    print("STEP 4: Labeling data")
    df = label_data(df)
    
    # Step 5: Save result
    print("\n" + "=" * 60)
    print("STEP 5: Saving result")
    print("-" * 60)
    save_data(df, OUTPUT_FILE)
    
    # Display sample
    display_sample(df, n=10)
    
    print("\n" + "=" * 60)
    print("✅ Preprocessing completed successfully!")
    print("=" * 60)


# ===============================
# Alternative: Custom labeling
# ===============================

def custom_labeling():
    """
    Example with custom labeling criteria
    """
    # Define your own criteria
    CUSTOM_RULES = {
        "Sangat Panas": lambda row: row['temp'] >= 35,
        "Panas": lambda row: row['temp'] >= 30 and row['temp'] < 35,
        "Hangat": lambda row: row['temp'] >= 25 and row['temp'] < 30,
        "Dingin": lambda row: row['temp'] >= 20 and row['temp'] < 25,
        "Sangat Dingin": lambda row: row['temp'] < 20,
    }
    
    print("🎨 Using custom labeling rules...")
    df = load_and_combine_csv(INPUT_FOLDER)
    df = remove_columns(df)
    df = clean_data(df)
    df = label_data(df, rules=CUSTOM_RULES)
    save_data(df, "model/dataset/custom_labeled.csv")


# ===============================
# Run Script
# ===============================

if __name__ == "__main__":
    # Option 1: Use default labeling
    main()
    
    # Option 2: Use custom labeling (uncomment to use)
    # custom_labeling()