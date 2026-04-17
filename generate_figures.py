import os
import json
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import cv2
from PIL import Image
from torchvision import datasets
from recognizer import predict
from config import BASE_DIR, TRAIN_LOG_JSON
from matplotlib.patches import Rectangle, FancyArrow
from matplotlib import font_manager as fm

# 输出目录
FIG_DIR = os.path.join(BASE_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

def setup_chinese_font():
    cands = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                fm.fontManager.addfont(p)
                plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
                break
            except Exception:
                continue
    plt.rcParams["axes.unicode_minus"] = False

def apply_preprocess(img: Image.Image, mode: str) -> Image.Image:
    if mode == "none":
        return img
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if mode == "equalize":
        yuv = cv2.cvtColor(arr, cv2.COLOR_BGR2YUV)
        yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
        arr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
    elif mode == "gaussian":
        arr = cv2.GaussianBlur(arr, (5, 5), 1.2)
    elif mode == "sharpen":
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        arr = cv2.filter2D(arr, -1, kernel)
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

def dataset_distribution(root=os.path.join(BASE_DIR, "dataset")):
    dist = {}
    for split in ["train", "test"]:
        d = datasets.ImageFolder(os.path.join(root, split))
        counts = {cls: 0 for cls in d.classes}
        for _, target in d.samples:
            cls = d.classes[target]
            counts[cls] += 1
        dist[split] = counts
    # 绘制测试集分布
    test_counts = dist["test"]
    labels = list(test_counts.keys())
    values = [test_counts[k] for k in labels]
    plt.figure(figsize=(12, 5))
    plt.bar(range(len(labels)), values)
    plt.xticks(range(len(labels)), labels, rotation=90)
    plt.ylabel("count")
    plt.title("Dataset distribution (test)")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "dataset_distribution_test.png"))
    plt.close()
    return dist

def evaluate_modes(dataset_root=os.path.join(BASE_DIR, "dataset", "test")):
    ds = datasets.ImageFolder(dataset_root)
    class_names = ds.classes
    paths = [p for p, _ in ds.samples]
    targets = [t for _, t in ds.samples]
    modes = ["none", "equalize", "gaussian", "sharpen"]
    results = {}
    # 评估每种预处理模式
    for mode in modes:
        latencies = []
        correct = 0
        preds_idx = []
        gts_idx = []
        processed = 0
        for path, target in zip(paths, targets):
            try:
                with Image.open(path) as im:
                    img = im.convert("RGB")
            except Exception:
                # 跳过损坏或不可读图片
                continue
            img = apply_preprocess(img, mode)
            t0 = time.perf_counter()
            label, conf, breed, bconf = predict(img)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
            processed += 1
            # 预测索引映射（若标签不在类别列表中则跳过该样本）
            try:
                pred_idx = class_names.index(label)
                preds_idx.append(pred_idx)
                gts_idx.append(target)
                if pred_idx == target:
                    correct += 1
            except ValueError:
                # 标签不匹配，记录为错误但不加入混淆
                pass
        total = processed
        avg = float(np.mean(latencies)) if latencies else 0.0
        p95 = float(np.percentile(latencies, 95)) if latencies else 0.0
        thr = (len(latencies) / (sum(latencies)/1000.0)) if latencies else 0.0
        acc = correct / total if total else 0.0
        results[mode] = {
            "accuracy": acc,
            "avg_latency_ms": avg,
            "p95_latency_ms": p95,
            "throughput_img_per_sec": thr,
            "preds_idx": preds_idx,
            "gts_idx": gts_idx,
            "class_names": class_names
        }
    # 保存指标
    with open(os.path.join(FIG_DIR, "perf_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({m: {k: v for k, v in res.items() if k not in ["preds_idx","gts_idx","class_names"]} 
                   for m, res in results.items()}, f, ensure_ascii=False, indent=2)
    return results

def plot_confusion(res, mode="none", title_cn=None, outfile=None):
    data = res[mode]
    preds = np.array(data["preds_idx"])
    gts = np.array(data["gts_idx"])
    class_names = data["class_names"]
    n = len(class_names)
    cm = np.zeros((n, n), dtype=int)
    for p, g in zip(preds, gts):
        cm[g, p] += 1
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=False, cmap="Blues", fmt="d")
    if title_cn:
        plt.title(title_cn)
        plt.xlabel("预测 Predicted")
        plt.ylabel("真实 True")
    else:
        plt.title(f"Confusion Matrix ({mode})")
        plt.xlabel("Predicted")
        plt.ylabel("True")
    plt.tight_layout()
    out = outfile or os.path.join(FIG_DIR, f"confusion_{mode}.png")
    plt.savefig(out)
    plt.close()

def plot_latency_hist(res):
    # 读取原始 perf_benchmark 不保存所有样本时延；这里用重新评估得到的时延分布
    for mode, data in res.items():
        # 无原始列表，无法画直方图；这里仅画箱线图替代
        # 若需要直方图，可在 evaluate_modes 中返回 latencies 列表（此处权衡体积未保存）
        pass

def plot_mode_compare(res):
    modes = list(res.keys())
    accs = [res[m]["accuracy"] for m in modes]
    avgs = [res[m]["avg_latency_ms"] for m in modes]
    plt.figure(figsize=(10, 4))
    ax1 = plt.subplot(1, 2, 1)
    ax1.bar(modes, accs, color="#4c78a8")
    ax1.set_ylim(0, 1)
    ax1.set_title("Accuracy by Preprocess")
    ax1.tick_params(axis='x', rotation=20)
    ax2 = plt.subplot(1, 2, 2)
    ax2.bar(modes, avgs, color="#f58518")
    ax2.set_title("Avg Latency (ms) by Preprocess")
    ax2.tick_params(axis='x', rotation=20)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "preprocess_compare.png"))
    plt.close()

def plot_training_curves():
    if not os.path.exists(TRAIN_LOG_JSON):
        return
    with open(TRAIN_LOG_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    logs = data.get("logs", [])
    if not logs:
        return
    epochs = [l["epoch"] for l in logs]
    tr_loss = [l["train_loss"] for l in logs]
    va_loss = [l["val_loss"] for l in logs]
    tr_acc = [l["train_acc"] for l in logs]
    va_acc = [l["val_acc"] for l in logs]
    plt.figure(figsize=(10, 4))
    ax1 = plt.subplot(1, 2, 1)
    ax1.plot(epochs, tr_loss, label="Train Loss")
    ax1.plot(epochs, va_loss, label="Val Loss")
    ax1.set_title("Loss Curves")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.legend()
    ax2 = plt.subplot(1, 2, 2)
    ax2.plot(epochs, tr_acc, label="Train Acc")
    ax2.plot(epochs, va_acc, label="Val Acc")
    ax2.set_title("Accuracy Curves")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Acc (%)")
    ax2.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "training_curves.png"))
    plt.close()

def draw_architecture_overview():
    plt.figure(figsize=(10, 6))
    ax = plt.gca()
    ax.axis('off')
    # Layers
    ax.add_patch(Rectangle((0.5, 0.7), 9, 0.5, fill=False))
    ax.text(0.55, 1.15, "采集与交互层", fontsize=12)
    ax.add_patch(Rectangle((0.5, 0.35), 9, 0.5, fill=False))
    ax.text(0.55, 0.8, "推理服务层", fontsize=12)
    ax.add_patch(Rectangle((0.5, 0.05), 9, 0.25, fill=False))
    ax.text(0.55, 0.45, "数据与知识层", fontsize=12)
    # Components
    ax.add_patch(Rectangle((0.8, 0.75), 2.2, 0.3, facecolor="#1f77b4"))
    ax.text(0.9, 0.88, "UI (Streamlit)", color="white")
    ax.add_patch(Rectangle((3.4, 0.75), 2.2, 0.3, facecolor="#2ca02c"))
    ax.text(3.5, 0.88, "预处理 (OpenCV)", color="white")
    ax.add_patch(Rectangle((6.0, 0.75), 2.2, 0.3, facecolor="#ff7f0e"))
    ax.text(6.1, 0.88, "展示与历史", color="white")
    ax.add_patch(Rectangle((1.2, 0.4), 2.2, 0.3, facecolor="#9467bd"))
    ax.text(1.3, 0.53, "主类模型\nResNet18", color="white")
    ax.add_patch(Rectangle((3.8, 0.4), 2.2, 0.3, facecolor="#8c564b"))
    ax.text(3.9, 0.53, "品种模型\n条件触发", color="white")
    ax.add_patch(Rectangle((6.4, 0.4), 2.2, 0.3, facecolor="#e377c2"))
    ax.text(6.5, 0.53, "后处理\nsoftmax/置信度", color="white")
    ax.add_patch(Rectangle((2.0, 0.1), 2.6, 0.2, facecolor="#7f7f7f"))
    ax.text(2.1, 0.22, "SQLite 数据库", color="white")
    ax.add_patch(Rectangle((5.2, 0.1), 2.6, 0.2, facecolor="#bcbd22"))
    ax.text(5.3, 0.22, "品种信息 JSON", color="black")
    # Arrows
    ax.add_patch(FancyArrow(3.0, 0.9, 0.3, 0.0, width=0.02, head_width=0.08, color="white"))
    ax.add_patch(FancyArrow(5.6, 0.9, 0.3, 0.0, width=0.02, head_width=0.08, color="white"))
    ax.add_patch(FancyArrow(2.3, 0.7, 0.0, -0.25, width=0.02, head_width=0.08, color="black"))
    ax.add_patch(FancyArrow(3.9, 0.7, 0.0, -0.25, width=0.02, head_width=0.08, color="black"))
    ax.add_patch(FancyArrow(5.5, 0.7, 0.0, -0.25, width=0.02, head_width=0.08, color="black"))
    ax.add_patch(FancyArrow(4.9, 0.4, 0.0, -0.2, width=0.02, head_width=0.08, color="black"))
    ax.add_patch(FancyArrow(6.7, 0.4, 0.0, -0.2, width=0.02, head_width=0.08, color="black"))
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "architecture_overview.png"))
    plt.close()

def draw_recognition_flow():
    plt.figure(figsize=(10, 4))
    ax = plt.gca()
    ax.axis('off')
    boxes = [
        (0.5, "拍照/上传"),
        (1.8, "预处理\n(OpenCV)"),
        (3.1, "归一化\n(Resize/Normalize)"),
        (4.4, "主类模型\nResNet18"),
        (5.7, "条件品种模型"),
        (7.0, "后处理\nsoftmax/置信度"),
        (8.3, "知识匹配\nSQLite/JSON"),
    ]
    for x, text in boxes:
        ax.add_patch(Rectangle((x, 0.4), 1.0, 0.8, facecolor="#1f77b4"))
        ax.text(x+0.08, 0.8, text, color="white")
    for i in range(len(boxes)-1):
        x = boxes[i][0] + 1.0
        ax.add_patch(FancyArrow(x, 0.8, 0.7, 0.0, width=0.02, head_width=0.08, color="black"))
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "recognition_flow.png"))
    plt.close()

def plot_training_loss_curve():
    if not os.path.exists(TRAIN_LOG_JSON):
        return
    with open(TRAIN_LOG_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    logs = data.get("logs", [])
    if not logs:
        return
    epochs = [l["epoch"] for l in logs]
    tr_loss = [l["train_loss"] for l in logs]
    va_loss = [l["val_loss"] for l in logs]
    # 图4-1：训练损失曲线
    plt.figure(figsize=(8, 4))
    plt.plot(epochs, tr_loss, label="Train Loss")
    plt.plot(epochs, va_loss, label="Val Loss")
    plt.title("图4-1 模型训练损失变化曲线")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig4_1_train_loss.png"))
    plt.close()

def plot_training_acc_curve():
    if not os.path.exists(TRAIN_LOG_JSON):
        return
    with open(TRAIN_LOG_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    logs = data.get("logs", [])
    if not logs:
        return
    epochs = [l["epoch"] for l in logs]
    tr_acc = [l["train_acc"] for l in logs]
    va_acc = [l["val_acc"] for l in logs]
    # 图4-2：训练准确率曲线
    plt.figure(figsize=(8, 4))
    plt.plot(epochs, tr_acc, label="Train Acc")
    plt.plot(epochs, va_acc, label="Val Acc")
    plt.title("图4-2 模型训练准确率变化曲线")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig4_2_train_acc.png"))
    plt.close()

def main():
    setup_chinese_font()
    print("Generating figures...")
    dist = dataset_distribution()
    res = evaluate_modes()
    # 图4-3：混淆矩阵（无预处理）
    plot_confusion(
        res,
        mode="none",
        title_cn="图4-3 宠物分类混淆矩阵",
        outfile=os.path.join(FIG_DIR, "fig4_3_confusion_none.png"),
    )
    # 可选：其他预处理模式的混淆矩阵
    for m in ["equalize", "gaussian", "sharpen"]:
        if m in res:
            plot_confusion(res, mode=m, outfile=os.path.join(FIG_DIR, f"confusion_{m}.png"))
    plot_mode_compare(res)
    # 训练曲线（分图）
    plot_training_loss_curve()
    plot_training_acc_curve()
    plot_training_curves()
    draw_architecture_overview()
    draw_recognition_flow()
    try:
        files = [f for f in os.listdir(FIG_DIR) if f.lower().endswith(".png")]
        print("Saved figures:")
        for f in files:
            print(" -", os.path.join(FIG_DIR, f))
    except Exception:
        pass
    print(f"Figures saved to: {FIG_DIR}")

if __name__ == "__main__":
    main()
