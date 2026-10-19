import numpy as np

class DistanceMetrics:
    """
    Tập hợp các độ đo khoảng cách và độ tương đồng giữa các histogram đặc trưng.
    Hỗ trợ cả so sánh từng cặp và tính toán ma trận vector hóa (batch).
    """

    SUPPORTED_METRICS = {
        'euclidean': 'Khoảng cách Euclidean (L2)',
        'manhattan': 'Khoảng cách Manhattan (L1)',
        'chi_square': 'Khoảng cách Chi-Square (χ²)',
        'intersection': 'Histogram Intersection (Giao thoa)',
        'cosine': 'Khoảng cách Cosine',
        'bhattacharyya': 'Khoảng cách Bhattacharyya',
        'correlation': 'Hệ số tương quan (Correlation)'
    }

    @staticmethod
    def compute_batch_distances(query_vec, dataset_matrix, metric='euclidean'):
        """
        Tính toán khoảng cách từ vector truy vấn đến toàn bộ ma trận dataset bằng NumPy vectorization.
        query_vec: shape (D,)
        dataset_matrix: shape (N, D)
        Trả về:
            distances: mảng 1D độ dài N (giá trị càng nhỏ càng tương đồng)
            similarities: mảng 1D độ dài N (%) giá trị trong [0, 100]
        """
        metric = metric.lower()
        eps = 1e-10

        # Đảm bảo kiểu dữ liệu float32
        q = np.asarray(query_vec, dtype=np.float32)
        M = np.asarray(dataset_matrix, dtype=np.float32)

        if metric == 'euclidean':
            # L2: sqrt(sum((M - q)^2, axis=1))
            diff = M - q
            distances = np.sqrt(np.sum(diff * diff, axis=1))
            # Cho normalized L1 vectors, max L2 distance là sqrt(2) ≈ 1.414
            max_dist = np.sqrt(2.0)
            similarities = np.clip((1.0 - (distances / max_dist)) * 100.0, 0.0, 100.0)

        elif metric == 'manhattan':
            # L1: sum(|M - q|, axis=1)
            diff = np.abs(M - q)
            distances = np.sum(diff, axis=1)
            # Max L1 distance giữa 2 probability vectors là 2.0
            similarities = np.clip((1.0 - (distances / 2.0)) * 100.0, 0.0, 100.0)

        elif metric == 'chi_square':
            # Chi-square: 0.5 * sum((M - q)^2 / (M + q + eps))
            diff = M - q
            denominator = M + q + eps
            distances = 0.5 * np.sum((diff * diff) / denominator, axis=1)
            # Max chi-square cho normalized vectors là 1.0
            similarities = np.clip((1.0 - distances) * 100.0, 0.0, 100.0)

        elif metric == 'intersection':
            # Histogram intersection: sum(min(M, q))
            # Kết quả là độ tương đồng trong [0, 1]
            inter = np.sum(np.minimum(M, q), axis=1)
            distances = 1.0 - inter
            similarities = np.clip(inter * 100.0, 0.0, 100.0)

        elif metric == 'cosine':
            # Cosine similarity: (M . q) / (||M|| * ||q||)
            q_norm = np.linalg.norm(q) + eps
            M_norm = np.linalg.norm(M, axis=1) + eps
            dot = np.dot(M, q)
            cos_sim = dot / (M_norm * q_norm)
            cos_sim = np.clip(cos_sim, -1.0, 1.0)
            distances = 1.0 - cos_sim
            similarities = np.clip(cos_sim * 100.0, 0.0, 100.0)

        elif metric == 'bhattacharyya':
            # Bhattacharyya coefficient: sum(sqrt(M * q))
            bc = np.sum(np.sqrt(np.maximum(0.0, M * q)), axis=1)
            bc = np.clip(bc, 0.0, 1.0)
            # Distance = sqrt(1 - BC)
            distances = np.sqrt(np.maximum(0.0, 1.0 - bc))
            similarities = np.clip(bc * 100.0, 0.0, 100.0)

        elif metric == 'correlation':
            # Pearson correlation
            q_mean = q - np.mean(q)
            q_std = np.linalg.norm(q_mean) + eps
            
            M_mean = M - np.mean(M, axis=1, keepdims=True)
            M_std = np.linalg.norm(M_mean, axis=1) + eps
            
            corr = np.dot(M_mean, q_mean) / (M_std * q_std)
            corr = np.clip(corr, -1.0, 1.0)
            distances = 1.0 - corr
            similarities = np.clip(((corr + 1.0) / 2.0) * 100.0, 0.0, 100.0)

        else:
            # Dự phòng Euclidean
            diff = M - q
            distances = np.sqrt(np.sum(diff * diff, axis=1))
            similarities = np.clip((1.0 - (distances / np.sqrt(2.0))) * 100.0, 0.0, 100.0)

        return distances, similarities
