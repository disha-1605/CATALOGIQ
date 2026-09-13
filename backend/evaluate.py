"""Standalone Root Cause Engine Evaluation Script for CatalogIQ.

Evaluates deterministic root-cause prediction against ground-truth labels
loaded from root_cause_ground_truth.csv and searches.csv. Computes overall accuracy,
confusion matrix, and per-class precision / recall / F1 metrics.
"""

import os
import pandas as pd
from typing import Dict, List, Any
from collections import defaultdict
from backend.seed_data import load_products_from_csv, load_searches_from_csv
from backend.search_analyzer import analyze_query_coverage

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CLASSES = ["ATTRIBUTE_GAP", "INVENTORY_GAP", "NO_CATALOG_GAP_DETECTED"]


def get_ground_truth_map() -> Dict[str, str]:
    """Load ground truth mappings from CSV."""
    gt_path = os.path.join(DATA_DIR, "root_cause_ground_truth.csv")
    s_path = os.path.join(DATA_DIR, "searches.csv")
    
    gt_df = pd.read_csv(gt_path)
    s_df = pd.read_csv(s_path)
    
    merged = pd.merge(s_df, gt_df, on="query_id")
    gt_map = {}
    for _, row in merged.iterrows():
        expected = str(row["expected_root_cause"])
        if expected == "NO_CATALOG_GAP":
            expected = "NO_CATALOG_GAP_DETECTED"
        gt_map[str(row["query"])] = expected
    return gt_map


def run_evaluation() -> Dict[str, Any]:
    """Execute evaluation and compute precision, recall, F1, and accuracy."""
    products = load_products_from_csv()
    ground_truth_labels = get_ground_truth_map()
    
    total = len(ground_truth_labels)
    correct_count = 0
    
    # Confusion matrix: matrix[ground_truth][predicted]
    confusion_matrix = {gt: {pred: 0 for pred in CLASSES} for gt in CLASSES}
    
    query_results = []
    
    for query_text, gt_label in ground_truth_labels.items():
        analysis = analyze_query_coverage(query_text, products)
        pred_label = analysis["root_cause"]
        
        confusion_matrix[gt_label][pred_label] += 1
        
        is_match = (pred_label == gt_label)
        if is_match:
            correct_count += 1
            
        query_results.append({
            "query": query_text,
            "ground_truth": gt_label,
            "predicted": pred_label,
            "relevant_count": analysis["total_relevant"],
            "coverage": analysis["catalog_coverage"],
            "correct": is_match,
        })

    accuracy = (correct_count / total) * 100.0 if total > 0 else 0.0

    # Per-class metrics
    class_metrics = {}
    for c in CLASSES:
        tp = confusion_matrix[c][c]
        fp = sum(confusion_matrix[other][c] for other in CLASSES if other != c)
        fn = sum(confusion_matrix[c][other] for other in CLASSES if other != c)
        
        precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        
        class_metrics[c] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": sum(confusion_matrix[c].values()),
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "f1_score": round(f1, 2),
        }

    return {
        "total_queries": total,
        "correct_predictions": correct_count,
        "accuracy_pct": round(accuracy, 2),
        "confusion_matrix": confusion_matrix,
        "class_metrics": class_metrics,
        "query_results": query_results,
    }


def print_evaluation_report(results: Dict[str, Any]):
    """Print formatted evaluation report."""
    print("=" * 75)
    print("CatalogIQ — Deterministic Root Cause Engine Evaluation")
    print("=" * 75)
    print(f"Total Evaluated Queries : {results['total_queries']}")
    print(f"Correct Predictions     : {results['correct_predictions']}")
    print(f"Overall Accuracy        : {results['accuracy_pct']}%\n")

    print("-" * 75)
    print(f"{'Class':<26} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
    print("-" * 75)
    for c, metrics in results["class_metrics"].items():
        print(f"{c:<26} | {metrics['precision']:>9.2f}% | {metrics['recall']:>9.2f}% | {metrics['f1_score']:>9.2f}% | {metrics['support']:>7}")
    print("-" * 75)

    print("\nConfusion Matrix (Rows: Ground Truth, Columns: Predicted):")
    print(f"{'':<26} | {'Attr Gap':<10} | {'Inv Gap':<10} | {'No Gap':<10}")
    print("-" * 65)
    for gt in CLASSES:
        row = results["confusion_matrix"][gt]
        print(f"{gt:<26} | {row['ATTRIBUTE_GAP']:>10} | {row['INVENTORY_GAP']:>10} | {row['NO_CATALOG_GAP_DETECTED']:>10}")
    print("-" * 65)

    misclassifications = [q for q in results["query_results"] if not q["correct"]]
    if misclassifications:
        print(f"\nMisclassified Queries ({len(misclassifications)}):")
        for m in misclassifications:
            print(f"  - '{m['query']}': Ground Truth = {m['ground_truth']}, Predicted = {m['predicted']} (Rel={m['relevant_count']}, Cov={m['coverage']})")
    else:
        print("\nAll 40 search queries predicted with exact ground truth alignment.")
    print("=" * 75)


if __name__ == "__main__":
    eval_results = run_evaluation()
    print_evaluation_report(eval_results)
