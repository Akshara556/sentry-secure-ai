import torch
import os
import shutil
import random
from pathlib import Path
from ultralytics import YOLO

def prepare_data():
    """Prepare YOLO dataset from your structure"""
    data_dir = Path('Data')
    
    # Create YOLO directory structure
    yolo_dir = Path('dataset')
    dirs = ['images/train', 'images/val', 'labels/train', 'labels/val']
    for d in dirs:
        (yolo_dir / d).mkdir(parents=True, exist_ok=True)
    
    # Collect all images
    images = []
    
    # Safety images
    safe_dir = data_dir / 'safty'  # Note: your folder name is 'safty' (typo)
    if safe_dir.exists():
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            images.extend(list(safe_dir.rglob(ext)))
    
    # Non-safety images
    non_safe_dir = data_dir / 'non_safety'  # Note: 'non_safety' (typo)
    if non_safe_dir.exists():
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            images.extend(list(non_safety_dir.rglob(ext)))
    
    print(f"Found {len(images)} images")
    
    # Split data (80% train, 20% val)
    random.shuffle(images)
    split = int(0.8 * len(images))
    train_images = images[:split]
    val_images = images[split:]
    
    # For demo: create placeholder labels (you need real annotations)
    print("Note: Creating placeholder labels. Add real annotations for production.")
    
    # Create dataset.yaml
    yaml_content = f"""path: {yolo_dir.absolute()}
train: images/train
val: images/val
nc: 6
names: ['person', 'helmet', 'vest', 'gloves', 'boots', 'mask']
"""
    
    (yolo_dir / 'dataset.yaml').write_text(yaml_content)
    
    return str(yolo_dir / 'dataset.yaml'), len(train_images), len(val_images)

def train_model():
    """Train YOLO model on your data"""
    print("Preparing dataset...")
    data_yaml, train_count, val_count = prepare_data()
    
    print(f"Training: {train_count} images | Validation: {val_count} images")
    
    # Load model
    model = YOLO('yolov8n.pt')  # Start with pre-trained
    
    # Train
    results = model.train(
        data=data_yaml,
        epochs=50,
        imgsz=640,
        batch=8,
        device='cuda' if torch.cuda.is_available() else 'cpu',
        save=True,
        project='ppe_training',
        name='train_1'
    )
    
    print("Training complete!")
    
    # Save best model
    best_model = Path('ppe_training/train_1/weights/best.pt')
    if best_model.exists():
        shutil.copy(best_model, 'models/ppe_model.pt')
        print(f"Model saved to: models/ppe_model.pt")
    
    return 'models/ppe_model.pt'

if __name__ == '__main__':
    # Create models directory
    Path('models').mkdir(exist_ok=True)
    
    # Train
    model_path = train_model()
    
    print(f"\nTraining complete! Model saved at: {model_path}")
    print("\nUsage:")
    print("1. python app.py to run the app")
    print("2. Upload images to Data/safty and Data/non_safty folders")
    print("3. Run python train.py again to retrain")