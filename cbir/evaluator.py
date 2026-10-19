import time
import numpy as np
from .metrics import DistanceMetrics

class DatasetEvaluator:
    """
    Module kiểm thử, đánh giá hiệu năng và độ chính xác của hệ thống CBIR.
    Tính toán Precision@K, mAP, độ trễ truy vấn và so sánh giữa các độ đo khoảng cách.
    """

    def __init__(self, indexer):
        self.indexer = indexer

    def run_benchmark(self, num_samples=30, top_k=10, metric='chi_square'):
        """
        Đánh giá tốc độ truy vấn (latency & throughput) trên tập dữ liệu đã đánh chỉ mục.
        """
        if self.indexer.features is None or len(self.indexer.features) == 0:
            return {'status': 'error', 'message': 'Chưa nạp chỉ mục dữ liệu.'}

        N = len(self.indexer.features)
        sample_count = min(num_samples, N)
        # Lấy mẫu ngẫu nhiên hoặc đều đặn
        step = max(1, N // sample_count)
        sample_indices = list(range(0, N, step))[:sample_count]

        latencies = []
        for idx in sample_indices:
            q_vec = self.indexer.features[idx]
            t0 = time.perf_counter()
            _ = self.indexer.search(q_vec, top_k=top_k, metric=metric)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0) # ms

        latencies = np.array(latencies)
        avg_latency = float(np.mean(latencies))
        min_latency = float(np.min(latencies))
        max_latency = float(np.max(latencies))
        p95_latency = float(np.percentile(latencies, 95))
        throughput = round(1000.0 / avg_latency if avg_latency > 0 else 0, 1)

        return {
            'status': 'success',
            'dataset_size': N,
            'feature_dim': int(self.indexer.features.shape[1]),
            'num_queries_tested': len(sample_indices),
            'avg_latency_ms': round(avg_latency, 3),
            'min_latency_ms': round(min_latency, 3),
            'max_latency_ms': round(max_latency, 3),
            'p95_latency_ms': round(p95_latency, 3),
            'queries_per_second': throughput,
            'metric_used': metric
        }

    def evaluate_precision_at_k(self, top_k=5, metric='chi_square', max_eval_images=50):
        """
        Tính toán Precision@K dựa trên cấu trúc danh mục (thư mục con) của dataset.
        Nếu dataset có các thư mục con (ví dụ: blue_ocean, green_forest,...),
        ảnh cùng danh mục được xem là ground-truth tương đồng.
        """
        if self.indexer.features is None or len(self.indexer.features) == 0:
            return {'status': 'error', 'message': 'Chưa nạp chỉ mục dữ liệu.'}

        categories = np.array(self.indexer.categories)
        unique_cats = np.unique(categories)

        if len(unique_cats) <= 1:
            return {
                'status': 'warning',
                'message': 'Bộ dữ liệu hiện tại không chia danh mục theo thư mục con. Hãy tổ chức ảnh vào các thư mục như dataset/bien, dataset/rung để tính Precision@K.',
                'unique_categories': list(unique_cats)
            }

        N = len(self.indexer.features)
        sample_indices = np.linspace(0, N - 1, min(N, max_eval_images), dtype=int)

        precisions = []
        category_stats = {cat: [] for cat in unique_cats}

        for idx in sample_indices:
            q_vec = self.indexer.features[idx]
            true_cat = categories[idx]

            # Tìm kiếm top K+1 (bỏ qua chính ảnh truy vấn ở vị trí đầu nếu trùng)
            results = self.indexer.search(q_vec, top_k=top_k + 1, metric=metric)
            # Bỏ ảnh có cùng index với truy vấn nếu có
            filtered = [r for r in results if r['index'] != idx][:top_k]
            if not filtered:
                filtered = results[:top_k]

            matches = sum(1 for r in filtered if r['category'] == true_cat)
            p_k = matches / len(filtered) if filtered else 0.0

            precisions.append(p_k)
            category_stats[true_cat].append(p_k)

        mean_precision = float(np.mean(precisions)) * 100.0

        per_cat_summary = {}
        for cat, vals in category_stats.items():
            if vals:
                per_cat_summary[cat] = {
                    'count_tested': len(vals),
                    'precision_pct': round(float(np.mean(vals)) * 100.0, 1)
                }

        return {
            'status': 'success',
            'top_k': top_k,
            'metric': metric,
            'total_evaluated': len(sample_indices),
            'mean_precision_pct': round(mean_precision, 2),
            'per_category': per_cat_summary
        }

    def compare_metrics(self, query_vec, top_k=5):
        """
        So sánh kết quả trả về của tất cả các độ đo khoảng cách cho cùng một ảnh truy vấn.
        """
        if self.indexer.features is None:
            return {}

        comparison = {}
        for metric_id, metric_name in DistanceMetrics.SUPPORTED_METRICS.items():
            t0 = time.perf_counter()
            results = self.indexer.search(query_vec, top_k=top_k, metric=metric_id)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

            comparison[metric_id] = {
                'metric_name': metric_name,
                'latency_ms': elapsed_ms,
                'results': results
            }

        return comparison
