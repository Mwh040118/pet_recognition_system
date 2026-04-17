import time
import os
import json
from statistics import mean
from PIL import Image
from torchvision import datasets
from recognizer import predict
from config import BASE_DIR

def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    k = int(round((p/100.0)*(len(values)-1)))
    return values[k]

def run(dataset_root=os.path.join(BASE_DIR, "dataset", "test")):
    ds = datasets.ImageFolder(dataset_root)
    class_names = ds.classes
    paths = [path for path, _ in ds.samples]
    targets = [target for _, target in ds.samples]

    latencies = []
    correct = 0
    total = len(paths)

    for path, target in zip(paths, targets):
        img = Image.open(path).convert("RGB")
        t0 = time.perf_counter()
        label, conf, breed, bconf = predict(img)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        if label == class_names[target]:
            correct += 1

    metrics = {
        "total_images": total,
        "accuracy": correct / total if total else 0.0,
        "avg_latency_ms": mean(latencies) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 95),
        "throughput_img_per_sec": (total / (sum(latencies)/1000.0)) if latencies else 0.0
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run()
