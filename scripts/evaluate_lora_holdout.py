#!/usr/bin/env python3
"""
scripts/evaluate_lora_holdout.py
Adversarial Out-of-Sample Holdout Evaluation for Bayesian Pivot LoRA Model.

Evaluates the trained MLX LoRA adapter against data/training/valid.jsonl (204 unseen trades).
Computes:
- Win Detection Rate (Sensitivity on genuine alpha)
- Trap Veto Rate (Specificity on retail traps / noise)
- Continuous Probability Calibration (MAE between continuous scores)
- Confusion Matrix across [FLOW_GO, SHADOW_OBSERVATION, REJECTED]
- Formats 5 qualitative case studies showing model reasoning.
"""

import json
import re
import sys
import time
from pathlib import Path
import numpy as np

# MLX LM
try:
    from mlx_lm import load, generate
except ImportError:
    print("Error: mlx_lm not found. Run with ./venv_train/bin/python", file=sys.stderr)
    sys.exit(1)

def extract_json_payload(raw_text: str) -> dict:
    """Extract and parse JSON object from raw LLM output text with resilient regex fallback."""
    # Try direct parse
    try:
        return json.loads(raw_text.strip())
    except Exception:
        pass
    
    # Try finding first complete { ... }
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
            
    # Resilient Token Scanning (Tier 2 Fallback)
    score_match = re.search(r'"score"\s*:\s*([0-9.]+)', raw_text)
    verdict_match = re.search(r'"verdict"\s*:\s*"([^"]+)"', raw_text)
    risk_match = re.search(r'"risk_multiplier"\s*:\s*([0-9.]+)', raw_text)
    reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', raw_text)

    if score_match and verdict_match:
        return {
            "score": float(score_match.group(1)),
            "verdict": verdict_match.group(1),
            "reasoning": reasoning_match.group(1) if reasoning_match else "Recovered via token scanner",
            "risk_multiplier": float(risk_match.group(1)) if risk_match else 0.0,
            "risk_level": "LOW" if float(score_match.group(1)) >= 7.5 else "HIGH"
        }

    # Fallback default if generation was interrupted before producing tokens
    return {
        "score": 5.0,
        "verdict": "SHADOW_OBSERVATION",
        "reasoning": "Output parsing fallback: " + raw_text[:80].replace("\n", " "),
        "risk_multiplier": 0.0,
        "risk_level": "MEDIUM"
    }

def main():
    model_id = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
    adapter_path = "adapters/bayesian-pivot-lora"
    val_data_path = Path("data/training/valid.jsonl")

    if not Path(adapter_path).exists():
        print(f"Error: Adapter path {adapter_path} does not exist. Has training finished?", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("BAYESIAN PIVOT LORA: OUT-OF-SAMPLE HOLDOUT BENCHMARK")
    print(f"Base Model:    {model_id}")
    print(f"Adapter:       {adapter_path}")
    print(f"Validation:    {val_data_path}")
    print("=" * 70)

    # 1. Load Model + Adapter
    print("\n[1/4] Loading quantized base model and LoRA adapter weights onto Apple Silicon M4 GPU...")
    t0 = time.time()
    model, tokenizer = load(model_id, adapter_path=adapter_path)
    print(f"Model loaded in {time.time() - t0:.2f}s.")

    # 2. Load Holdout Data
    with open(val_data_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    print(f"[2/4] Loaded {len(records)} out-of-sample holdout records from valid.jsonl.")

    # 3. Evaluate Each Record
    print("\n[3/4] Running zero-shot inference across all 204 holdout setups...")
    
    y_true_verdicts = []
    y_pred_verdicts = []
    y_true_scores = []
    y_pred_scores = []
    evaluations = []

    t_start_eval = time.time()
    for idx, rec in enumerate(records):
        messages = rec["messages"]
        # System + User
        prompt_msgs = [m for m in messages if m["role"] != "assistant"]
        ground_truth_raw = [m["content"] for m in messages if m["role"] == "assistant"][0]
        gt_obj = json.loads(ground_truth_raw)

        # Apply chat template
        prompt = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)

        # Generate response
        response_text = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=250,
            verbose=False
        )

        pred_obj = extract_json_payload(response_text)

        gt_score = float(gt_obj.get("score", 5.0))
        pred_score = float(pred_obj.get("score", 5.0))
        gt_verdict = gt_obj.get("verdict", "SHADOW_OBSERVATION")
        pred_verdict = pred_obj.get("verdict", "SHADOW_OBSERVATION")

        y_true_verdicts.append(gt_verdict)
        y_pred_verdicts.append(pred_verdict)
        y_true_scores.append(gt_score)
        y_pred_scores.append(pred_score)

        evaluations.append({
            "index": idx,
            "prompt_snippet": prompt_msgs[1]["content"][:120].replace("\n", " "),
            "ground_truth": gt_obj,
            "predicted": pred_obj,
            "score_delta": round(pred_score - gt_score, 2)
        })

        if (idx + 1) % 25 == 0 or (idx + 1) == len(records):
            elapsed = time.time() - t_start_eval
            rate = (idx + 1) / elapsed
            print(f"  Processed {idx + 1}/{len(records)} holdouts ({rate:.1f} trades/sec)...", flush=True)

    # 4. Compute Statistical & Financial Performance Metrics
    print("\n[4/4] Computing Validation Statistics & Forensic Audit...")

    y_true_scores = np.array(y_true_scores)
    y_pred_scores = np.array(y_pred_scores)
    score_mae = float(np.mean(np.abs(y_pred_scores - y_true_scores)))
    score_corr = float(np.corrcoef(y_true_scores, y_pred_scores)[0, 1])

    # Confusion matrix
    verdict_labels = ["FLOW_GO", "SHADOW_OBSERVATION", "REJECTED"]
    conf_matrix = {t: {p: 0 for p in verdict_labels} for t in verdict_labels}
    for yt, yp in zip(y_true_verdicts, y_pred_verdicts):
        yt_clean = yt if yt in verdict_labels else "SHADOW_OBSERVATION"
        yp_clean = yp if yp in verdict_labels else "SHADOW_OBSERVATION"
        conf_matrix[yt_clean][yp_clean] += 1

    # Win detection (Sensitivity / Recall on FLOW_GO)
    total_true_wins = sum(conf_matrix["FLOW_GO"].values())
    caught_wins = conf_matrix["FLOW_GO"]["FLOW_GO"]
    win_recall = (caught_wins / total_true_wins * 100.0) if total_true_wins > 0 else 0.0

    # Trap veto (Specificity / Recall on REJECTED)
    total_true_traps = sum(conf_matrix["REJECTED"].values())
    vetoed_traps = conf_matrix["REJECTED"]["REJECTED"]
    trap_veto_recall = (vetoed_traps / total_true_traps * 100.0) if total_true_traps > 0 else 0.0

    # False Positive Rate (Calling a toxic trap FLOW_GO)
    toxic_false_alarms = conf_matrix["REJECTED"]["FLOW_GO"]
    toxic_leakage_rate = (toxic_false_alarms / total_true_traps * 100.0) if total_true_traps > 0 else 0.0

    # Overall Verdict Accuracy
    total_correct = sum(conf_matrix[lbl][lbl] for lbl in verdict_labels)
    total_evals = len(y_true_verdicts)
    accuracy = (total_correct / total_evals * 100.0)

    print("\n" + "=" * 70)
    print("BAYESIAN PIVOT LORA: STATISTICAL HOLDOUT REPORT CARD")
    print("=" * 70)
    print(f"Total Holdout Trades Evaluated:  {total_evals}")
    print(f"Overall Categorical Accuracy:    {accuracy:.1f}% ({total_correct}/{total_evals})")
    print(f"Trap Veto Rate (True Traps):     {trap_veto_recall:.1f}% ({vetoed_traps}/{total_true_traps})")
    print(f"Toxic Leakage Rate (Traps->GO):  {toxic_leakage_rate:.1f}% ({toxic_false_alarms}/{total_true_traps})")
    print(f"Win Detection Rate (True Wins):  {win_recall:.1f}% ({caught_wins}/{total_true_wins})")
    print(f"Continuous Score MAE:            {score_mae:.2f} points (out of 10.0)")
    print(f"Continuous Correlation (r):      {score_corr:.3f}")
    print("-" * 70)
    print("CONFUSION MATRIX (Ground Truth rows -> Predicted columns):")
    print(f"{'Actual \\ Pred':<20} | {'FLOW_GO':<10} | {'SHADOW':<10} | {'REJECTED':<10} | {'Total':<6}")
    print("-" * 70)
    for row in verdict_labels:
        total_row = sum(conf_matrix[row].values())
        print(f"{row:<20} | {conf_matrix[row]['FLOW_GO']:<10} | {conf_matrix[row]['SHADOW_OBSERVATION']:<10} | {conf_matrix[row]['REJECTED']:<10} | {total_row:<6}")
    print("=" * 70)

    # 5. Show 5 Sample Qualitative Forensic Evaluations
    print("\nSAMPLE QUALITATIVE FORENSIC CASE STUDIES (5 UNSEEN TRADES):")
    print("-" * 70)
    samples_to_show = [0, int(len(records)*0.25), int(len(records)*0.5), int(len(records)*0.75), len(records)-1]
    for s_idx in samples_to_show:
        e = evaluations[s_idx]
        print(f"\n[Case #{s_idx + 1}] Setup: {e['prompt_snippet']}")
        print(f"  Ground Truth: Score {e['ground_truth']['score']:.1f} | Verdict {e['ground_truth']['verdict']} | Risk {e['ground_truth']['risk_multiplier']}x")
        print(f"  Predicted:    Score {e['predicted']['score']:.1f} | Verdict {e['predicted']['verdict']} | Risk {e['predicted']['risk_multiplier']}x")
        print(f"  Reasoning:    \"{e['predicted']['reasoning']}\"")
        match_str = "EXACT MATCH" if e['ground_truth']['verdict'] == e['predicted']['verdict'] else "DISCREPANCY"
        print(f"  Alignment:    {match_str} (Delta: {e['score_delta']:+0.2f})")

    # Save results to JSON
    summary_report = {
        "model_id": model_id,
        "adapter_path": adapter_path,
        "total_evals": total_evals,
        "accuracy_pct": round(accuracy, 2),
        "trap_veto_recall_pct": round(trap_veto_recall, 2),
        "toxic_leakage_pct": round(toxic_leakage_rate, 2),
        "win_recall_pct": round(win_recall, 2),
        "score_mae": round(score_mae, 3),
        "score_correlation": round(score_corr, 3),
        "confusion_matrix": conf_matrix,
        "evaluations": evaluations
    }

    report_path = Path("data/training/holdout_evaluation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)
    print(f"\nDetailed evaluation report saved to: {report_path.resolve()}")

if __name__ == "__main__":
    main()
