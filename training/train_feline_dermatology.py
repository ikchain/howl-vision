"""Train EfficientNetV2-S for feline dermatology classification.

4 classes: Flea_Allergy, Health, Ringworm, Scabies
Dataset: data/datasets/feline/feline/dermatology/feline_skin_splits/{train,valid,test}/

Existing checkpoint (vet_feline_dermatology.pt) was trained for only 4 epochs
(58.1% accuracy). This script trains from scratch with proper augmentation
and enough epochs to converge.

Usage:
    python training/train_feline_dermatology.py
    python training/train_feline_dermatology.py --epochs 50 --resume
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn as nn
from PIL import Image
from sklearn.metrics import (
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
)
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "datasets" / "feline" / "feline" / "dermatology" / "feline_skin_splits"
CHECKPOINT_DIR = PROJECT_ROOT / "data" / "models" / "vision"
CHECKPOINT_PATH = CHECKPOINT_DIR / "vet_feline_dermatology.pt"

CLASS_NAMES = ["Flea_Allergy", "Health", "Ringworm", "Scabies"]
INPUT_SIZE = 384
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class FolderDataset(Dataset):
    """ImageFolder-style dataset with class names matching folder names."""

    def __init__(self, root: Path, transform: T.Compose):
        self.samples: list[tuple[Path, int]] = []
        self.transform = transform
        for idx, cls_name in enumerate(CLASS_NAMES):
            cls_dir = root / cls_name
            if not cls_dir.is_dir():
                logger.warning("Missing class folder: %s", cls_dir)
                continue
            for img_path in sorted(cls_dir.iterdir()):
                if img_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                    self.samples.append((img_path, idx))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        return self.transform(img), label


def build_transforms(train: bool) -> T.Compose:
    if train:
        return T.Compose([
            T.RandomResizedCrop(INPUT_SIZE, scale=(0.7, 1.0)),
            T.RandomHorizontalFlip(),
            T.RandomVerticalFlip(),
            T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.05),
            T.RandomRotation(15),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
    return T.Compose([
        T.Resize((INPUT_SIZE, INPUT_SIZE)),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def wilson_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def run_evaluation(model: nn.Module, loader: DataLoader, device: torch.device, split: str) -> dict:
    model.eval()
    all_preds, all_labels = [], []
    total_loss = 0.0
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            logits = model(images)
            total_loss += criterion(logits, labels).item() * images.size(0)
            preds = logits.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    n = len(all_labels)
    acc = float(np.mean(all_preds == all_labels))
    f1_macro = float(f1_score(all_labels, all_preds, average="macro"))
    kappa = float(cohen_kappa_score(all_labels, all_preds))
    cm = confusion_matrix(all_labels, all_preds)

    acc_lo, acc_hi = wilson_ci(acc, n)
    f1_per_class = {}
    report = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=True)
    for cls_name in CLASS_NAMES:
        f1_per_class[cls_name] = report[cls_name]["f1-score"]

    logger.info(
        "%s -- Acc: %.1f%% [%.1f%%, %.1f%%] (n=%d), F1-macro: %.3f, Kappa: %.3f",
        split, acc * 100, acc_lo * 100, acc_hi * 100, n, f1_macro, kappa,
    )
    for cls_name in CLASS_NAMES:
        logger.info("  %s: F1=%.3f", cls_name, f1_per_class[cls_name])
    logger.info("Confusion matrix:\n%s", cm)

    return {
        "accuracy": acc,
        "accuracy_ci_95": [acc_lo, acc_hi],
        "f1_macro": f1_macro,
        "f1_per_class": f1_per_class,
        "cohen_kappa": kappa,
        "confusion_matrix": cm,
        "loss": total_loss / n,
        "n": n,
    }


def train(args: argparse.Namespace):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Device: %s", device)

    # Data
    train_ds = FolderDataset(DATA_DIR / "train", build_transforms(train=True))
    valid_ds = FolderDataset(DATA_DIR / "valid", build_transforms(train=False))
    test_ds = FolderDataset(DATA_DIR / "test", build_transforms(train=False))

    logger.info("Train: %d, Valid: %d, Test: %d", len(train_ds), len(valid_ds), len(test_ds))

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True)
    valid_loader = DataLoader(valid_ds, batch_size=args.batch_size, shuffle=False, num_workers=4, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=4, pin_memory=True)

    # Model
    model = timm.create_model(
        "tf_efficientnetv2_s.in21k_ft_in1k",
        pretrained=True,
        num_classes=len(CLASS_NAMES),
    )

    start_epoch = 0
    if args.resume and CHECKPOINT_PATH.exists():
        ckpt = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        start_epoch = ckpt.get("epoch", 0) + 1
        logger.info("Resumed from epoch %d", start_epoch)

    model.to(device)

    # Loss with class weights (dataset is roughly balanced, but small)
    class_counts = np.array([sum(1 for _, lbl in train_ds.samples if lbl == i) for i in range(len(CLASS_NAMES))])
    weights = 1.0 / (class_counts / class_counts.sum())
    weights = weights / weights.sum() * len(CLASS_NAMES)
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32).to(device))

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    scaler = GradScaler()

    best_f1 = 0.0
    patience_counter = 0

    for epoch in range(start_epoch, args.epochs):
        model.train()
        running_loss = 0.0
        t0 = time.perf_counter()

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            with autocast():
                logits = model(images)
                loss = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running_loss += loss.item() * images.size(0)

        scheduler.step()
        elapsed = time.perf_counter() - t0
        avg_loss = running_loss / len(train_ds)
        lr = scheduler.get_last_lr()[0]

        logger.info("Epoch %d/%d -- loss: %.4f, lr: %.2e, time: %.1fs", epoch + 1, args.epochs, avg_loss, lr, elapsed)

        # Validate
        metrics = run_evaluation(model, valid_loader, device, "Valid")

        if metrics["f1_macro"] > best_f1:
            best_f1 = metrics["f1_macro"]
            patience_counter = 0
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "scheduler_state_dict": scheduler.state_dict(),
                    "scaler_state_dict": scaler.state_dict(),
                    "metrics": {
                        "accuracy": metrics["accuracy"],
                        "f1_macro": metrics["f1_macro"],
                        "f1_per_class": metrics["f1_per_class"],
                        "confusion_matrix": metrics["confusion_matrix"].tolist(),
                        "loss": metrics["loss"],
                    },
                },
                CHECKPOINT_PATH,
            )
            logger.info("Saved best model (F1-macro: %.3f)", best_f1)
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info("Early stopping at epoch %d (patience=%d)", epoch + 1, args.patience)
                break

    # Final test set evaluation with best model
    logger.info("Loading best checkpoint for test evaluation...")
    ckpt = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    test_metrics = run_evaluation(model, test_loader, device, "Test")

    # Save test results
    results_path = PROJECT_ROOT / "training" / "feline_dermatology_results.json"
    results = {
        "model": "EfficientNetV2-S",
        "dataset": "feline_skin_splits",
        "num_classes": len(CLASS_NAMES),
        "class_names": CLASS_NAMES,
        "best_epoch": int(ckpt["epoch"]) + 1,
        "test": {
            "accuracy": test_metrics["accuracy"],
            "accuracy_ci_95": test_metrics["accuracy_ci_95"],
            "f1_macro": test_metrics["f1_macro"],
            "f1_per_class": test_metrics["f1_per_class"],
            "cohen_kappa": test_metrics["cohen_kappa"],
            "confusion_matrix": test_metrics["confusion_matrix"].tolist(),
            "n": test_metrics["n"],
        },
    }
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", results_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train feline dermatology classifier")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--resume", action="store_true", help="Resume from existing checkpoint")
    train(parser.parse_args())
